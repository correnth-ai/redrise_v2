//! Session readiness: interactive input desktop and UIPI integrity check.
use engine_core::ports::{Readiness, SessionProbe};
use engine_core::PLATFORM_WINDOWS_X64;
use windows_sys::Win32::Foundation::{CloseHandle, HANDLE};
use windows_sys::Win32::Security::{
    GetSidSubAuthority, GetSidSubAuthorityCount, GetTokenInformation, TokenIntegrityLevel,
    TOKEN_MANDATORY_LABEL, TOKEN_QUERY,
};
use windows_sys::Win32::System::StationsAndDesktops::{
    CloseDesktop, GetUserObjectInformationW, OpenInputDesktop, UOI_NAME,
};
use windows_sys::Win32::System::Threading::{
    GetCurrentProcess, OpenProcess, OpenProcessToken, PROCESS_QUERY_LIMITED_INFORMATION,
};

use crate::util::from_wide;

pub struct WinSession;

/// Name of the desktop receiving input; `None` when it cannot be opened
/// (locked workstation, secure desktop, or non-interactive session).
pub fn input_desktop_name() -> Option<String> {
    unsafe {
        let d = OpenInputDesktop(0, 0, 0x0001 /* DESKTOP_READOBJECTS */);
        if d.is_null() {
            return None;
        }
        let mut buf = [0u16; 128];
        let mut needed = 0u32;
        let ok = GetUserObjectInformationW(
            d as HANDLE,
            UOI_NAME,
            buf.as_mut_ptr().cast(),
            (buf.len() * 2) as u32,
            &mut needed,
        );
        CloseDesktop(d);
        if ok == 0 {
            return None;
        }
        let len = buf.iter().position(|c| *c == 0).unwrap_or(buf.len());
        Some(from_wide(&buf, len))
    }
}

fn token_integrity(process: HANDLE) -> Option<u32> {
    unsafe {
        let mut token: HANDLE = std::ptr::null_mut();
        if OpenProcessToken(process, TOKEN_QUERY, &mut token) == 0 {
            return None;
        }
        let mut buf = [0u8; 256];
        let mut len = 0u32;
        let ok = GetTokenInformation(
            token,
            TokenIntegrityLevel,
            buf.as_mut_ptr().cast(),
            buf.len() as u32,
            &mut len,
        );
        CloseHandle(token);
        if ok == 0 {
            return None;
        }
        let label = &*(buf.as_ptr() as *const TOKEN_MANDATORY_LABEL);
        let sid = label.Label.Sid;
        let count = *GetSidSubAuthorityCount(sid) as u32;
        Some(*GetSidSubAuthority(sid, count - 1))
    }
}

pub fn own_integrity() -> Option<u32> {
    unsafe { token_integrity(GetCurrentProcess()) }
}

impl SessionProbe for WinSession {
    fn readiness(&self) -> Readiness {
        let mut detail = Vec::new();
        let name = input_desktop_name();
        let interactive = match &name {
            Some(n) if n.eq_ignore_ascii_case("Default") => true,
            Some(n) => {
                detail.push(format!("input desktop is '{n}' (secure desktop or locked)"));
                false
            }
            None => {
                detail.push(
                    "input desktop not accessible (locked session or non-interactive)".into(),
                );
                false
            }
        };
        if let Some(il) = own_integrity() {
            detail.push(format!("engine integrity rid=0x{il:04X}"));
        }
        Readiness {
            platform: PLATFORM_WINDOWS_X64.into(),
            interactive_desktop: interactive,
            detail,
        }
    }

    fn can_drive_process(&self, pid: u32) -> Option<bool> {
        let ours = own_integrity()?;
        unsafe {
            let h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid);
            if h.is_null() {
                return Some(false);
            }
            let theirs = token_integrity(h);
            CloseHandle(h);
            // Token not readable from our level: treat as higher (UIPI risk).
            Some(theirs.map(|t| t <= ours).unwrap_or(false))
        }
    }
}
