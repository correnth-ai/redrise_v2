//! Low-level keyboard/mouse hooks as an `InputSource`.
//!
//! The hook callbacks do O(1) work and never block: they read window
//! identity, translate the key with `ToUnicodeEx` (no keyboard-state change)
//! and `try_send` into the bounded channel. Stop posts `WM_QUIT` to the hook
//! thread, which unhooks and drops the only `EventTx` (end of stream).
use std::cell::RefCell;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc;
use std::sync::Arc;
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

use engine_core::model::{MouseButton, RawEvent, RawKind, WindowRef};
use engine_core::ports::{EventTx, InputSource, Offer, RunningSource, SourceStats};
use windows_sys::Win32::Foundation::{LPARAM, LRESULT, POINT, WPARAM};
use windows_sys::Win32::System::LibraryLoader::GetModuleHandleW;
use windows_sys::Win32::System::Threading::GetCurrentThreadId;
use windows_sys::Win32::UI::Input::KeyboardAndMouse::{
    GetKeyState, GetKeyboardLayout, SendInput, ToUnicodeEx, INPUT, INPUT_0, INPUT_KEYBOARD,
    KEYBDINPUT, KEYEVENTF_KEYUP,
};
use windows_sys::Win32::UI::WindowsAndMessaging::{
    CallNextHookEx, GetAncestor, GetForegroundWindow, GetMessageW, GetWindowThreadProcessId,
    PostThreadMessageW, SetWindowsHookExW, UnhookWindowsHookEx, WindowFromPoint, GA_ROOT,
    KBDLLHOOKSTRUCT, LLKHF_EXTENDED, LLKHF_INJECTED, LLKHF_LOWER_IL_INJECTED, LLMHF_INJECTED,
    LLMHF_LOWER_IL_INJECTED, MSG, MSLLHOOKSTRUCT, WH_KEYBOARD_LL, WH_MOUSE_LL, WM_KEYDOWN,
    WM_LBUTTONDOWN, WM_LBUTTONUP, WM_MBUTTONDOWN, WM_MBUTTONUP, WM_MOUSEWHEEL, WM_QUIT,
    WM_RBUTTONDOWN, WM_RBUTTONUP, WM_SYSKEYDOWN, WM_XBUTTONDOWN, WM_XBUTTONUP,
};

use crate::window::window_ref;

pub struct WinInputSource {
    /// Lower-case process image of the authorized surface, e.g. `excel.exe`.
    pub target_process: String,
    /// Lab-only: record OS-injected input (synthetic operator).
    pub accept_injected: bool,
}

struct HookState {
    tx: EventTx,
    target: String,
    accept_injected: bool,
    started: Instant,
    stats: SourceStats,
    held: [bool; 256],
    writer_gone: bool,
    /// Set when our own liveness probe key reaches this hook.
    probe_seen: Arc<AtomicBool>,
    /// Pending UTF-16 high surrogate from a VK_PACKET pair.
    high_surrogate: Option<u16>,
}

thread_local! {
    static STATE: RefCell<Option<HookState>> = const { RefCell::new(None) };
}

fn is_injected_kb(flags: u32) -> bool {
    flags & (LLKHF_INJECTED | LLKHF_LOWER_IL_INJECTED) != 0
}

fn is_injected_mouse(flags: u32) -> bool {
    flags & (LLMHF_INJECTED | LLMHF_LOWER_IL_INJECTED) != 0
}

/// Admission common to both hooks: injected filter and target filter.
fn admit(st: &mut HookState, injected: bool, window: &Option<WindowRef>) -> bool {
    if injected && !st.accept_injected {
        st.stats.injected_ignored += 1;
        return false;
    }
    match window {
        Some(w) if w.process_image == st.target => {
            if injected {
                st.stats.injected_accepted += 1;
            }
            true
        }
        _ => {
            st.stats.filtered_out += 1;
            false
        }
    }
}

fn translate(vk: u32, scan: u32, held: &[bool; 256]) -> (Option<String>, bool) {
    unsafe {
        let mut state = [0u8; 256];
        for (i, h) in held.iter().enumerate() {
            if *h {
                state[i] = 0x80;
            }
        }
        // Generic modifier slots derived from left/right.
        for (generic, l, r) in [
            (0x10usize, 0xA0usize, 0xA1usize),
            (0x11, 0xA2, 0xA3),
            (0x12, 0xA4, 0xA5),
        ] {
            if held[l] || held[r] || held[generic] {
                state[generic] = 0x80;
            }
        }
        if GetKeyState(0x14) & 1 != 0 {
            state[0x14] = 0x01; // caps lock toggled
        }
        let fg = GetForegroundWindow();
        let thread = GetWindowThreadProcessId(fg, std::ptr::null_mut());
        let hkl = GetKeyboardLayout(thread);
        let mut buf = [0u16; 8];
        // Flag 0x4: do not change keyboard state (Windows 10 1607+).
        let n = ToUnicodeEx(
            vk,
            scan,
            state.as_ptr(),
            buf.as_mut_ptr(),
            buf.len() as i32,
            0x4,
            hkl,
        );
        if n < 0 {
            (None, true)
        } else if n == 0 {
            (None, false)
        } else {
            (Some(String::from_utf16_lossy(&buf[..n as usize])), false)
        }
    }
}

fn offer(st: &mut HookState, kind: RawKind, window: WindowRef) {
    let ev = RawEvent {
        seq: 0,
        t_us: st.started.elapsed().as_micros() as u64,
        kind,
        window,
    };
    if st.tx.offer(ev) == Offer::WriterGone {
        st.writer_gone = true;
    }
}

unsafe extern "system" fn kb_proc(code: i32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    if code >= 0 {
        let k = &*(lp as *const KBDLLHOOKSTRUCT);
        let down = wp as u32 == WM_KEYDOWN || wp as u32 == WM_SYSKEYDOWN;
        STATE.with(|s| {
            if let Some(st) = s.borrow_mut().as_mut() {
                if k.vkCode == PROBE_VK as u32 && is_injected_kb(k.flags) {
                    st.probe_seen.store(true, Ordering::SeqCst);
                    return; // liveness probe: never recorded
                }
                let vk = (k.vkCode & 0xFF) as usize;
                st.held[vk] = down;
                let window = window_ref(GetForegroundWindow());
                if !admit(st, is_injected_kb(k.flags), &window) {
                    return;
                }
                // VK_PACKET (0xE7): Unicode input (IME, remote tools, injected
                // text) carries the UTF-16 unit in the scan code.
                let (ch, dead) = if !down {
                    (None, false)
                } else if k.vkCode == 0xE7 {
                    let unit = k.scanCode as u16;
                    if (0xD800..=0xDBFF).contains(&unit) {
                        // First half of a pair: folded into the next event.
                        st.high_surrogate = Some(unit);
                        return;
                    }
                    let units: Vec<u16> =
                        st.high_surrogate.take().into_iter().chain([unit]).collect();
                    (String::from_utf16(&units).ok(), false)
                } else {
                    translate(k.vkCode, k.scanCode, &st.held)
                };
                let kind = RawKind::Key {
                    vk: k.vkCode as u16,
                    scan: k.scanCode as u16,
                    down,
                    extended: k.flags & LLKHF_EXTENDED != 0,
                    ch,
                    dead,
                };
                offer(st, kind, window.expect("admitted"));
            }
        });
    }
    CallNextHookEx(std::ptr::null_mut(), code, wp, lp)
}

unsafe extern "system" fn mouse_proc(code: i32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    if code >= 0 {
        let m = &*(lp as *const MSLLHOOKSTRUCT);
        let msg = wp as u32;
        let (button, down) = match msg {
            WM_LBUTTONDOWN => (Some(MouseButton::Left), true),
            WM_LBUTTONUP => (Some(MouseButton::Left), false),
            WM_RBUTTONDOWN => (Some(MouseButton::Right), true),
            WM_RBUTTONUP => (Some(MouseButton::Right), false),
            WM_MBUTTONDOWN => (Some(MouseButton::Middle), true),
            WM_MBUTTONUP => (Some(MouseButton::Middle), false),
            WM_XBUTTONDOWN => (Some(MouseButton::Other), true),
            WM_XBUTTONUP => (Some(MouseButton::Other), false),
            _ => (None, false),
        };
        if button.is_some() || msg == WM_MOUSEWHEEL {
            STATE.with(|s| {
                if let Some(st) = s.borrow_mut().as_mut() {
                    let root = GetAncestor(
                        WindowFromPoint(POINT {
                            x: m.pt.x,
                            y: m.pt.y,
                        }),
                        GA_ROOT,
                    );
                    let window = window_ref(root);
                    if !admit(st, is_injected_mouse(m.flags), &window) {
                        return;
                    }
                    let kind = match button {
                        Some(b) => RawKind::Mouse {
                            button: b,
                            down,
                            x: m.pt.x,
                            y: m.pt.y,
                        },
                        None => RawKind::Wheel {
                            delta: ((m.mouseData >> 16) as u16 as i16) as i32,
                            x: m.pt.x,
                            y: m.pt.y,
                        },
                    };
                    offer(st, kind, window.expect("admitted"));
                }
            });
        }
    }
    CallNextHookEx(std::ptr::null_mut(), code, wp, lp)
}

struct Running {
    probe_seen: Arc<AtomicBool>,
    thread_id: u32,
    handle: JoinHandle<Result<SourceStats, String>>,
}

impl InputSource for WinInputSource {
    fn spawn(self: Box<Self>, tx: EventTx) -> Result<Box<dyn RunningSource>, String> {
        let (ready_tx, ready_rx) = mpsc::channel::<Result<u32, String>>();
        let target = self.target_process.to_lowercase();
        let accept = self.accept_injected;
        let probe_seen = Arc::new(AtomicBool::new(false));
        let probe_for_hook = probe_seen.clone();
        let handle = std::thread::Builder::new()
            .name("rr-hooks".into())
            .spawn(move || unsafe {
                STATE.with(|s| {
                    *s.borrow_mut() = Some(HookState {
                        tx,
                        target,
                        accept_injected: accept,
                        started: Instant::now(),
                        stats: SourceStats::default(),
                        held: [false; 256],
                        writer_gone: false,
                        probe_seen: probe_for_hook,
                        high_surrogate: None,
                    })
                });
                let hmod = GetModuleHandleW(std::ptr::null());
                let kb = SetWindowsHookExW(WH_KEYBOARD_LL, Some(kb_proc), hmod, 0);
                let ms = SetWindowsHookExW(WH_MOUSE_LL, Some(mouse_proc), hmod, 0);
                if kb.is_null() || ms.is_null() {
                    if !kb.is_null() {
                        UnhookWindowsHookEx(kb);
                    }
                    if !ms.is_null() {
                        UnhookWindowsHookEx(ms);
                    }
                    let _ = ready_tx.send(Err("SetWindowsHookExW failed".into()));
                    STATE.with(|s| s.borrow_mut().take());
                    return Err("hooks not installed".into());
                }
                let _ = ready_tx.send(Ok(GetCurrentThreadId()));
                let mut msg: MSG = std::mem::zeroed();
                // GetMessageW blocks; returns 0 on WM_QUIT, -1 on error.
                let rc = loop {
                    let r = GetMessageW(&mut msg, std::ptr::null_mut(), 0, 0);
                    if r <= 0 {
                        break r;
                    }
                };
                UnhookWindowsHookEx(kb);
                UnhookWindowsHookEx(ms);
                let st = STATE.with(|s| s.borrow_mut().take()).expect("state");
                let stats = st.stats.clone();
                drop(st); // drops EventTx: end of stream
                if rc < 0 {
                    Err("GetMessageW failed".into())
                } else {
                    Ok(stats)
                }
            })
            .map_err(|e| e.to_string())?;
        match ready_rx.recv_timeout(Duration::from_secs(5)) {
            Ok(Ok(thread_id)) => Ok(Box::new(Running {
                probe_seen,
                thread_id,
                handle,
            })),
            Ok(Err(e)) => Err(e),
            Err(_) => Err("hook thread did not report readiness".into()),
        }
    }
}

impl RunningSource for Running {
    /// Injects one F24 tap and expects this capture's own hook to see it
    /// within 500 ms; detects hooks silently removed by Windows.
    fn check_liveness(&self) -> Result<(), String> {
        self.probe_seen.store(false, Ordering::SeqCst);
        send_probe_key();
        let t0 = Instant::now();
        while !self.probe_seen.load(Ordering::SeqCst) {
            if t0.elapsed() > Duration::from_millis(500) {
                return Err("keyboard hook did not observe the liveness probe".into());
            }
            std::thread::sleep(Duration::from_millis(5));
        }
        Ok(())
    }
    fn request_stop(&self) {
        unsafe {
            PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0);
        }
    }
    fn join(self: Box<Self>) -> Result<SourceStats, String> {
        self.handle
            .join()
            .map_err(|_| "hook thread panicked".to_string())?
    }
}

static PROBE_SEEN: AtomicBool = AtomicBool::new(false);
pub(crate) const PROBE_VK: u16 = 0x87; // VK_F24: not bound by common applications

unsafe extern "system" fn probe_proc(code: i32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    if code >= 0 {
        let k = &*(lp as *const KBDLLHOOKSTRUCT);
        if k.vkCode == PROBE_VK as u32 {
            PROBE_SEEN.store(true, Ordering::SeqCst);
        }
    }
    CallNextHookEx(std::ptr::null_mut(), code, wp, lp)
}

/// Hook-liveness probe: installs a keyboard hook, injects one F24 tap and
/// expects the callback within `timeout`. Detects environments where LL
/// hooks are not delivered (spec C12) before a capture is attempted.
pub fn probe_hooks(timeout: Duration) -> Result<u64, String> {
    PROBE_SEEN.store(false, Ordering::SeqCst);
    let done = Arc::new(AtomicBool::new(false));
    let (tid_tx, tid_rx) = mpsc::channel();
    let h = std::thread::spawn(move || unsafe {
        let hook = SetWindowsHookExW(
            WH_KEYBOARD_LL,
            Some(probe_proc),
            GetModuleHandleW(std::ptr::null()),
            0,
        );
        let _ = tid_tx.send((GetCurrentThreadId(), !hook.is_null()));
        if hook.is_null() {
            return;
        }
        let mut msg: MSG = std::mem::zeroed();
        while GetMessageW(&mut msg, std::ptr::null_mut(), 0, 0) > 0 {}
        UnhookWindowsHookEx(hook);
    });
    let (tid, ok) = tid_rx
        .recv_timeout(Duration::from_secs(5))
        .map_err(|_| "probe thread did not start")?;
    if !ok {
        let _ = h.join();
        return Err("SetWindowsHookExW failed".into());
    }
    let t0 = Instant::now();
    send_probe_key();
    while !PROBE_SEEN.load(Ordering::SeqCst) && t0.elapsed() < timeout {
        std::thread::sleep(Duration::from_millis(5));
    }
    let seen = PROBE_SEEN.load(Ordering::SeqCst);
    done.store(true, Ordering::SeqCst);
    unsafe {
        PostThreadMessageW(tid, WM_QUIT, 0, 0);
    }
    let _ = h.join();
    if seen {
        Ok(t0.elapsed().as_millis() as u64)
    } else {
        Err(format!("hook callback not observed within {timeout:?}"))
    }
}

pub(crate) fn send_probe_key() {
    let mk = |flags| INPUT {
        r#type: INPUT_KEYBOARD,
        Anonymous: INPUT_0 {
            ki: KEYBDINPUT {
                wVk: PROBE_VK,
                wScan: 0,
                dwFlags: flags,
                time: 0,
                dwExtraInfo: crate::guard::ENGINE_TAG,
            },
        },
    };
    let inputs = [mk(0), mk(KEYEVENTF_KEYUP)];
    unsafe {
        SendInput(2, inputs.as_ptr(), std::mem::size_of::<INPUT>() as i32);
    }
}
