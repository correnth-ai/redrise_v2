//! Read-only access to this station's own runner credential in the Windows vault
//! (written by the Runner at join, `redrise_contracts.vault`, target `RedRise/<ns>/runner-token`).
//! Used only to prove at sign-in which station the session runs on (TEAM-ACCOUNTS-20261108):
//! the value goes to the pinned team server and is never shown, logged or stored by the app.
use windows_sys::Win32::Security::Credentials::{CredFree, CredReadW, CREDENTIALW, CRED_TYPE_GENERIC};

/// Same namespace rule as `Paths::test_args("redrise_runner")`: an isolated test instance uses its own.
fn namespace() -> String {
    match (std::env::var("REDRISE_TEST_VAULT"), std::env::var("REDRISE_DATA_ROOT")) {
        (Ok(ns), Ok(data)) if !ns.is_empty() && !data.is_empty() => format!("{ns}-station"),
        _ => "station".into(),
    }
}

/// The runner token of this station, or None when this computer has not joined a team (or the vault fails).
pub fn station_token() -> Option<String> {
    let target: Vec<u16> = format!("RedRise/{}/runner-token", namespace()).encode_utf16().chain(Some(0)).collect();
    unsafe {
        let mut p: *mut CREDENTIALW = std::ptr::null_mut();
        if CredReadW(target.as_ptr(), CRED_TYPE_GENERIC, 0, &mut p) == 0 || p.is_null() {
            return None;
        }
        let c = &*p;
        let blob = std::slice::from_raw_parts(c.CredentialBlob, c.CredentialBlobSize as usize);
        let units: Vec<u16> = blob.chunks_exact(2).map(|b| u16::from_le_bytes([b[0], b[1]])).collect();
        CredFree(p as _);
        String::from_utf16(&units).ok().filter(|s| !s.is_empty())
    }
}
