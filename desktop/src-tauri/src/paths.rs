//! Install root (replaceable binaries) and data root (mutable state), kept apart.
use std::path::{Path, PathBuf};

use serde_json::Value;
use sha2::{Digest, Sha256};

pub struct Paths {
    pub install_root: PathBuf,
    pub data_root: PathBuf,
}

/// The real Documents folder of this user, as the Runner resolves it (OneDrive included).
pub fn documents() -> PathBuf {
    use windows_sys::Win32::System::Com::CoTaskMemFree;
    use windows_sys::Win32::UI::Shell::{FOLDERID_Documents, SHGetKnownFolderPath};
    unsafe {
        let mut p: *mut u16 = std::ptr::null_mut();
        let hr = SHGetKnownFolderPath(&FOLDERID_Documents, 0, std::ptr::null_mut(), &mut p);
        if hr != 0 || p.is_null() {
            return PathBuf::from(std::env::var_os("USERPROFILE").unwrap_or_default()).join("Documents");
        }
        let mut n = 0;
        while *p.add(n) != 0 {
            n += 1;
        }
        let s = String::from_utf16_lossy(std::slice::from_raw_parts(p, n));
        CoTaskMemFree(p as _);
        PathBuf::from(s)
    }
}

fn local_app_data() -> PathBuf {
    use windows_sys::Win32::System::Com::CoTaskMemFree;
    use windows_sys::Win32::UI::Shell::{FOLDERID_LocalAppData, SHGetKnownFolderPath};
    unsafe {
        let mut p: *mut u16 = std::ptr::null_mut();
        let hr = SHGetKnownFolderPath(&FOLDERID_LocalAppData, 0, std::ptr::null_mut(), &mut p);
        if hr != 0 || p.is_null() {
            return PathBuf::from(std::env::var_os("LOCALAPPDATA").unwrap_or_default());
        }
        let mut n = 0;
        while *p.add(n) != 0 {
            n += 1;
        }
        let s = String::from_utf16_lossy(std::slice::from_raw_parts(p, n));
        CoTaskMemFree(p as _);
        PathBuf::from(s)
    }
}

fn read_json(p: &Path) -> Option<Value> {
    std::fs::read(p).ok().and_then(|b| serde_json::from_slice(&b).ok())
}

impl Paths {
    pub fn resolve() -> Self {
        // Installed: <install>\RedRise.exe next to runtime\, engine\, runner\.
        let exe_dir = std::env::current_exe().ok().and_then(|p| p.parent().map(PathBuf::from)).unwrap_or_default();
        let install_root = if exe_dir.join("runtime").join("python").join("python.exe").is_file() {
            exe_dir
        } else {
            std::env::var_os("REDRISE_INSTALL_ROOT").map(PathBuf::from).unwrap_or(exe_dir) // development only
        };
        let data_root = std::env::var_os("REDRISE_DATA_ROOT")
            .map(PathBuf::from) // testing only
            .unwrap_or_else(|| local_app_data().join("RedRise"));
        Self { install_root, data_root }
    }

    /// Testing only. An isolated instance needs REDRISE_TEST_VAULT and REDRISE_DATA_ROOT together: the Core and
    /// the Runner resolve their own data folder, so without --data-root they would use the installed app's.
    pub fn test_args(module: &str) -> Vec<String> {
        let role = match module {
            "redrise_core" => "host",
            "redrise_runner" => "station",
            _ => return vec![],
        };
        match (std::env::var("REDRISE_TEST_VAULT"), std::env::var("REDRISE_DATA_ROOT")) {
            (Ok(ns), Ok(data)) if !ns.is_empty() && !data.is_empty() =>
                vec!["--vault-namespace".into(), format!("{ns}-{role}"), "--data-root".into(), data],
            _ => vec![],
        }
    }

    pub fn python(&self) -> PathBuf {
        self.install_root.join("runtime").join("python").join("python.exe")
    }

    pub fn host_config(&self) -> Option<Value> {
        read_json(&self.data_root.join("host").join("host.json"))
    }

    pub fn connection(&self) -> Option<Value> {
        read_json(&self.data_root.join("agent").join("connection.json"))
    }

    pub fn agent_status(&self) -> Option<Value> {
        read_json(&self.data_root.join("agent").join("status.json"))
    }

    /// Role chosen in the installer wizard for a computer not set up yet (`install/setup-intent.json`, schema
    /// redrise.setup-intent/1, server|station). Not a secret and grants nothing: it only picks the first-open flow.
    pub fn setup_intent(&self) -> Option<String> {
        let v = read_json(&self.data_root.join("install").join("setup-intent.json"))?;
        let role = v.get("role")?.as_str()?;
        (v.get("schema").and_then(Value::as_str) == Some("redrise.setup-intent/1") && matches!(role, "server" | "station"))
            .then(|| role.to_string())
    }

    /// Once the configuration is done, the intent is consumed (kept beside, renamed): reopening never asks again.
    pub fn consume_setup_intent(&self) {
        let dir = self.data_root.join("install");
        let _ = std::fs::rename(dir.join("setup-intent.json"), dir.join("setup-intent.consumed.json"));
    }

    pub fn manifest_sha256(&self) -> Option<String> {
        std::fs::read(self.install_root.join("manifest.json")).ok().map(|b| format!("{:x}", Sha256::digest(&b)))
    }
}
