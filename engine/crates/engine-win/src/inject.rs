//! `SendInput` injector. Every call is one atomic batch; partial acceptance
//! is reported, never treated as success. Every input carries `ENGINE_TAG`
//! so the replay guard can tell it from anyone else's.
use engine_core::model::MouseButton;
use engine_core::ports::{InjectError, InputInjector, Modifiers};

use crate::guard::ENGINE_TAG;
use windows_sys::Win32::Foundation::CloseHandle;
use windows_sys::Win32::System::Threading::{
    OpenProcess, WaitForInputIdle, PROCESS_QUERY_INFORMATION, PROCESS_SYNCHRONIZE,
};
use windows_sys::Win32::UI::Input::KeyboardAndMouse::{
    GetAsyncKeyState, MapVirtualKeyW, SendInput, INPUT, INPUT_0, INPUT_KEYBOARD, INPUT_MOUSE,
    KEYBDINPUT, KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE, MAPVK_VK_TO_VSC,
    MOUSEEVENTF_ABSOLUTE, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, MOUSEEVENTF_MOVE,
    MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP, MOUSEEVENTF_VIRTUALDESK, MOUSEINPUT,
};
use windows_sys::Win32::UI::WindowsAndMessaging::{GetForegroundWindow, GetWindowThreadProcessId};
use windows_sys::Win32::UI::WindowsAndMessaging::{
    GetSystemMetrics, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN, SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN,
};

pub struct WinInjector;

const VK_LSHIFT: u16 = 0xA0;
const VK_LCONTROL: u16 = 0xA2;
const VK_LMENU: u16 = 0xA4;
const VK_LWIN: u16 = 0x5B;
const MOD_HOLD: std::time::Duration = std::time::Duration::from_millis(30);

fn extended(vk: u16) -> bool {
    matches!(
        vk,
        0x21..=0x28 | 0x2D | 0x2E | 0x5B | 0x5C | 0x6F | 0x90 | 0xA3 | 0xA5
    )
}

fn key_input(vk: u16, up: bool) -> INPUT {
    let scan = unsafe { MapVirtualKeyW(vk as u32, MAPVK_VK_TO_VSC) } as u16;
    let mut flags = if up { KEYEVENTF_KEYUP } else { 0 };
    if extended(vk) {
        flags |= KEYEVENTF_EXTENDEDKEY;
    }
    INPUT {
        r#type: INPUT_KEYBOARD,
        Anonymous: INPUT_0 {
            ki: KEYBDINPUT {
                wVk: vk,
                wScan: scan,
                dwFlags: flags,
                time: 0,
                dwExtraInfo: ENGINE_TAG,
            },
        },
    }
}

fn unicode_input(unit: u16, up: bool) -> INPUT {
    let flags = KEYEVENTF_UNICODE | if up { KEYEVENTF_KEYUP } else { 0 };
    INPUT {
        r#type: INPUT_KEYBOARD,
        Anonymous: INPUT_0 {
            ki: KEYBDINPUT {
                wVk: 0,
                wScan: unit,
                dwFlags: flags,
                time: 0,
                dwExtraInfo: ENGINE_TAG,
            },
        },
    }
}

fn mouse_input(dx: i32, dy: i32, flags: u32) -> INPUT {
    INPUT {
        r#type: INPUT_MOUSE,
        Anonymous: INPUT_0 {
            mi: MOUSEINPUT {
                dx,
                dy,
                mouseData: 0,
                dwFlags: flags,
                time: 0,
                dwExtraInfo: ENGINE_TAG,
            },
        },
    }
}

fn send(inputs: &[INPUT]) -> Result<(), InjectError> {
    let n = unsafe {
        SendInput(
            inputs.len() as u32,
            inputs.as_ptr(),
            std::mem::size_of::<INPUT>() as i32,
        )
    };
    if n as usize == inputs.len() {
        Ok(())
    } else {
        Err(InjectError::Partial {
            sent: inputs.len() as u32,
            accepted: n,
        })
    }
}

/// Waits (bounded, 1 s) until the foreground app has processed its pending
/// input. Without it, under CPU load Windows 11 Notepad dropped or duplicated
/// characters right after a word ("RedRise!EEstamos lllizes"); measured
/// 6/8 correct without, 24/24 with (lab A/B, full CPU load).
fn wait_target_idle() {
    unsafe {
        let mut pid = 0u32;
        GetWindowThreadProcessId(GetForegroundWindow(), &mut pid);
        let h = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_SYNCHRONIZE, 0, pid);
        if !h.is_null() {
            WaitForInputIdle(h, 1000);
            CloseHandle(h);
        }
    }
}

fn mod_vks(m: Modifiers) -> Vec<u16> {
    let mut v = Vec::new();
    if m.ctrl {
        v.push(VK_LCONTROL);
    }
    if m.alt {
        v.push(VK_LMENU);
    }
    if m.shift {
        v.push(VK_LSHIFT);
    }
    if m.win {
        v.push(VK_LWIN);
    }
    v
}

impl InputInjector for WinInjector {
    fn click(&self, button: MouseButton, x: i32, y: i32) -> Result<(), InjectError> {
        let (down, up) = match button {
            MouseButton::Left => (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
            MouseButton::Right => (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
            other => {
                return Err(InjectError::Other(format!(
                    "{other:?} button not supported"
                )))
            }
        };
        let (vx, vy, vw, vh) = unsafe {
            (
                GetSystemMetrics(SM_XVIRTUALSCREEN),
                GetSystemMetrics(SM_YVIRTUALSCREEN),
                GetSystemMetrics(SM_CXVIRTUALSCREEN),
                GetSystemMetrics(SM_CYVIRTUALSCREEN),
            )
        };
        let nx = ((x - vx) as i64 * 65535 / (vw.max(2) - 1) as i64) as i32;
        let ny = ((y - vy) as i64 * 65535 / (vh.max(2) - 1) as i64) as i32;
        let abs = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK;
        send(&[
            mouse_input(nx, ny, MOUSEEVENTF_MOVE | abs),
            mouse_input(nx, ny, down | abs),
            mouse_input(nx, ny, up | abs),
        ])
    }

    fn key(&self, vk: u16, mods: Modifiers) -> Result<(), InjectError> {
        // Modifiers are pressed in their own batch and held briefly: some UI
        // frameworks sample modifier state asynchronously and would otherwise
        // see a bare key (observed: Ctrl+N typed "n" in Windows 11 Notepad).
        let mv = mod_vks(mods);
        if mv.is_empty() {
            return send(&[key_input(vk, false), key_input(vk, true)]);
        }
        let downs: Vec<INPUT> = mv.iter().map(|m| key_input(*m, false)).collect();
        let ups: Vec<INPUT> = mv.iter().rev().map(|m| key_input(*m, true)).collect();
        send(&downs)?;
        std::thread::sleep(MOD_HOLD);
        let r = send(&[key_input(vk, false), key_input(vk, true)]);
        std::thread::sleep(MOD_HOLD);
        let up = send(&ups);
        r.and(up)
    }

    fn type_char(&self, ch: char) -> Result<(), InjectError> {
        let mut buf = [0u16; 2];
        let units = ch.encode_utf16(&mut buf);
        let mut inputs = Vec::new();
        for u in units.iter() {
            inputs.push(unicode_input(*u, false));
            inputs.push(unicode_input(*u, true));
        }
        let r = send(&inputs);
        wait_target_idle();
        r
    }

    fn release_modifiers(&self) {
        let held: Vec<INPUT> = [0xA0u16, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C]
            .iter()
            .filter(|vk| unsafe { GetAsyncKeyState(**vk as i32) } < 0)
            .map(|vk| key_input(*vk, true))
            .collect();
        if !held.is_empty() {
            let _ = send(&held);
        }
    }
}
