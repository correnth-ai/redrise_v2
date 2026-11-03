//! Foreign-input guard for native replays: low-level hooks that note the
//! first key or button press the Engine did not send itself (a person, or
//! another program). Every `SendInput` of the Engine carries `ENGINE_TAG` in
//! `dwExtraInfo`; pointer movement alone is ignored. The callbacks only read
//! the event and set a flag: no key identity or text is kept.
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc, Mutex};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

use engine_core::ports::InterferenceMonitor;
use windows_sys::Win32::Foundation::{LPARAM, LRESULT, WPARAM};
use windows_sys::Win32::System::LibraryLoader::GetModuleHandleW;
use windows_sys::Win32::System::Threading::GetCurrentThreadId;
use windows_sys::Win32::UI::WindowsAndMessaging::{
    CallNextHookEx, GetMessageW, PostThreadMessageW, SetWindowsHookExW, UnhookWindowsHookEx,
    KBDLLHOOKSTRUCT, LLKHF_INJECTED, LLKHF_LOWER_IL_INJECTED, LLMHF_INJECTED,
    LLMHF_LOWER_IL_INJECTED, MSG, MSLLHOOKSTRUCT, WH_KEYBOARD_LL, WH_MOUSE_LL, WM_KEYDOWN,
    WM_LBUTTONDOWN, WM_MBUTTONDOWN, WM_MOUSEHWHEEL, WM_MOUSEWHEEL, WM_QUIT, WM_RBUTTONDOWN,
    WM_SYSKEYDOWN, WM_XBUTTONDOWN,
};

use crate::hooks::{send_probe_key, PROBE_VK};

/// `dwExtraInfo` of every input the Engine injects ("RREN").
pub const ENGINE_TAG: usize = 0x5252_454E;

static FIRST: Mutex<Option<String>> = Mutex::new(None);
static PROBE_SEEN: AtomicBool = AtomicBool::new(false);

fn note(what: &str, injected: bool) {
    let mut first = FIRST.lock().unwrap_or_else(|e| e.into_inner());
    if first.is_none() {
        let source = if injected {
            "another program"
        } else {
            "hardware"
        };
        *first = Some(format!("{what} input from {source} during the run"));
    }
}

unsafe extern "system" fn kb_proc(code: i32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    if code >= 0 && (wp as u32 == WM_KEYDOWN || wp as u32 == WM_SYSKEYDOWN) {
        let k = &*(lp as *const KBDLLHOOKSTRUCT);
        if k.dwExtraInfo == ENGINE_TAG {
            if k.vkCode == PROBE_VK as u32 {
                PROBE_SEEN.store(true, Ordering::SeqCst);
            }
        } else {
            note(
                "keyboard",
                k.flags & (LLKHF_INJECTED | LLKHF_LOWER_IL_INJECTED) != 0,
            );
        }
    }
    CallNextHookEx(std::ptr::null_mut(), code, wp, lp)
}

unsafe extern "system" fn mouse_proc(code: i32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    let press = matches!(
        wp as u32,
        WM_LBUTTONDOWN
            | WM_RBUTTONDOWN
            | WM_MBUTTONDOWN
            | WM_XBUTTONDOWN
            | WM_MOUSEWHEEL
            | WM_MOUSEHWHEEL
    );
    if code >= 0 && press {
        let m = &*(lp as *const MSLLHOOKSTRUCT);
        if m.dwExtraInfo != ENGINE_TAG {
            note(
                "mouse",
                m.flags & (LLMHF_INJECTED | LLMHF_LOWER_IL_INJECTED) != 0,
            );
        }
    }
    CallNextHookEx(std::ptr::null_mut(), code, wp, lp)
}

/// One guard per process (the hook state is static).
pub struct WinInputGuard {
    error: Option<String>,
    thread_id: u32,
    handle: Option<JoinHandle<()>>,
}

impl WinInputGuard {
    /// Installs the hooks and proves they receive input with one tagged F24
    /// tap. Never fails here: an unarmed guard reports through `ready()`.
    pub fn start() -> Self {
        *FIRST.lock().unwrap_or_else(|e| e.into_inner()) = None;
        PROBE_SEEN.store(false, Ordering::SeqCst);
        let (tx, rx) = mpsc::channel::<Result<u32, String>>();
        let handle = std::thread::Builder::new()
            .name("rr-guard".into())
            .spawn(move || unsafe {
                let hmod = GetModuleHandleW(std::ptr::null());
                let kb = SetWindowsHookExW(WH_KEYBOARD_LL, Some(kb_proc), hmod, 0);
                let ms = SetWindowsHookExW(WH_MOUSE_LL, Some(mouse_proc), hmod, 0);
                if kb.is_null() || ms.is_null() {
                    for h in [kb, ms] {
                        if !h.is_null() {
                            UnhookWindowsHookEx(h);
                        }
                    }
                    let _ = tx.send(Err("SetWindowsHookExW failed".into()));
                    return;
                }
                let _ = tx.send(Ok(GetCurrentThreadId()));
                let mut msg: MSG = std::mem::zeroed();
                while GetMessageW(&mut msg, std::ptr::null_mut(), 0, 0) > 0 {}
                UnhookWindowsHookEx(kb);
                UnhookWindowsHookEx(ms);
            });
        let handle = match handle {
            Ok(h) => h,
            Err(e) => {
                return Self {
                    error: Some(e.to_string()),
                    thread_id: 0,
                    handle: None,
                }
            }
        };
        let mut guard = Self {
            error: None,
            thread_id: 0,
            handle: Some(handle),
        };
        match rx.recv_timeout(Duration::from_secs(5)) {
            Ok(Ok(tid)) => guard.thread_id = tid,
            Ok(Err(e)) => guard.error = Some(e),
            Err(_) => {
                guard.error = Some("guard thread did not report readiness".into());
                guard.handle = None; // detached: no thread id to stop it with
            }
        }
        if guard.error.is_none() {
            send_probe_key();
            let t0 = Instant::now();
            while !PROBE_SEEN.load(Ordering::SeqCst) {
                if t0.elapsed() > Duration::from_millis(500) {
                    guard.error = Some("input guard did not observe its probe".into());
                    break;
                }
                std::thread::sleep(Duration::from_millis(5));
            }
        }
        guard
    }
}

impl InterferenceMonitor for WinInputGuard {
    fn ready(&self) -> Result<(), String> {
        match &self.error {
            Some(e) => Err(e.clone()),
            None => Ok(()),
        }
    }
    fn observed(&self) -> Option<String> {
        FIRST.lock().unwrap_or_else(|e| e.into_inner()).clone()
    }
}

impl Drop for WinInputGuard {
    fn drop(&mut self) {
        if self.thread_id != 0 {
            unsafe {
                PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0);
            }
        }
        if let Some(h) = self.handle.take() {
            let _ = h.join();
        }
    }
}
