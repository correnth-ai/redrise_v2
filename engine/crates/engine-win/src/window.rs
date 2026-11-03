//! Window identity (process image, class, title, rect) and activation.
use std::collections::HashMap;
use std::sync::Mutex;
use std::time::{Duration, Instant};

use engine_core::model::{Rect, WindowRef};
use engine_core::ports::WindowInspector;
use windows_sys::Win32::Foundation::{CloseHandle, HWND, LPARAM, RECT};
use windows_sys::Win32::System::Threading::{
    AttachThreadInput, GetCurrentThreadId, OpenProcess, QueryFullProcessImageNameW,
    PROCESS_NAME_WIN32, PROCESS_QUERY_LIMITED_INFORMATION,
};
use windows_sys::Win32::UI::WindowsAndMessaging::{
    EnumWindows, GetAncestor, GetClassNameW, GetForegroundWindow, GetWindowRect, GetWindowTextW,
    GetWindowThreadProcessId, IsIconic, IsWindow, IsWindowVisible, SetForegroundWindow, ShowWindow,
    GA_ROOTOWNER, SW_RESTORE,
};

use crate::util::from_wide;

/// pid -> (image, cached at). Short TTL so a reused pid is re-resolved.
static IMAGES: Mutex<Option<HashMap<u32, (String, Instant)>>> = Mutex::new(None);
const IMAGE_TTL: Duration = Duration::from_secs(5);

pub fn process_image(pid: u32) -> String {
    if let Some((s, at)) = IMAGES
        .lock()
        .unwrap()
        .get_or_insert_with(HashMap::new)
        .get(&pid)
    {
        if at.elapsed() < IMAGE_TTL {
            return s.clone();
        }
    }
    let name = unsafe {
        let h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid);
        if h.is_null() {
            return String::new();
        }
        let mut buf = [0u16; 1024];
        let mut len = buf.len() as u32;
        let ok = QueryFullProcessImageNameW(h, PROCESS_NAME_WIN32, buf.as_mut_ptr(), &mut len);
        CloseHandle(h);
        if ok == 0 {
            return String::new();
        }
        let full = from_wide(&buf, len as usize);
        full.rsplit(['\\', '/']).next().unwrap_or("").to_lowercase()
    };
    IMAGES
        .lock()
        .unwrap()
        .get_or_insert_with(HashMap::new)
        .insert(pid, (name.clone(), Instant::now()));
    name
}

pub fn window_ref(hwnd: HWND) -> Option<WindowRef> {
    if hwnd.is_null() {
        return None;
    }
    unsafe {
        let mut pid = 0u32;
        GetWindowThreadProcessId(hwnd, &mut pid);
        let mut class = [0u16; 256];
        let cl = GetClassNameW(hwnd, class.as_mut_ptr(), class.len() as i32);
        let mut title = [0u16; 512];
        let tl = GetWindowTextW(hwnd, title.as_mut_ptr(), title.len() as i32);
        let mut r: RECT = std::mem::zeroed();
        GetWindowRect(hwnd, &mut r);
        Some(WindowRef {
            pid,
            process_image: process_image(pid),
            class: from_wide(&class, cl.max(0) as usize),
            title: from_wide(&title, tl.max(0) as usize),
            rect: Rect {
                left: r.left,
                top: r.top,
                right: r.right,
                bottom: r.bottom,
            },
        })
    }
}

pub fn foreground_window() -> Option<WindowRef> {
    unsafe { window_ref(GetForegroundWindow()) }
}

pub struct WinWindows;

struct Find<'a> {
    image: &'a str,
    class: &'a str,
    found: HWND,
}

unsafe extern "system" fn enum_cb(hwnd: HWND, lp: LPARAM) -> i32 {
    let f = &mut *(lp as *mut Find);
    if IsWindowVisible(hwnd) == 0 {
        return 1;
    }
    if let Some(w) = window_ref(hwnd) {
        if w.process_image == f.image && w.class == f.class {
            f.found = hwnd;
            return 0;
        }
    }
    1
}

impl WindowInspector for WinWindows {
    fn foreground(&self) -> Option<WindowRef> {
        foreground_window()
    }

    fn activate(&self, process_image: &str, class: &str) -> bool {
        let mut f = Find {
            image: process_image,
            class,
            found: std::ptr::null_mut(),
        };
        unsafe {
            EnumWindows(Some(enum_cb), &mut f as *mut Find as LPARAM);
            !f.found.is_null() && bring_forward(f.found)
        }
    }

    fn foreground_root(&self) -> Option<u64> {
        unsafe {
            let fg = GetForegroundWindow();
            if fg.is_null() {
                return None;
            }
            let root = GetAncestor(fg, GA_ROOTOWNER);
            Some(if root.is_null() { fg } else { root } as usize as u64)
        }
    }

    fn activate_window(&self, root: u64) -> bool {
        let hwnd = root as usize as HWND;
        unsafe { IsWindow(hwnd) != 0 && bring_forward(hwnd) }
    }
}

unsafe fn bring_forward(hwnd: HWND) -> bool {
    if IsIconic(hwnd) != 0 {
        ShowWindow(hwnd, SW_RESTORE);
    }
    // Foreground lock: attach to the current foreground thread so the
    // request is honoured, then detach.
    let fg = GetForegroundWindow();
    let fg_thread = GetWindowThreadProcessId(fg, std::ptr::null_mut());
    let me = GetCurrentThreadId();
    let attached = fg_thread != 0 && fg_thread != me && AttachThreadInput(me, fg_thread, 1) != 0;
    let ok = SetForegroundWindow(hwnd) != 0;
    if attached {
        AttachThreadInput(me, fg_thread, 0);
    }
    ok
}
