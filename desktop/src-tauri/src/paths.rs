//! Install root (replaceable binaries) and data root (mutable state), kept apart.
use std::path::{Path, PathBuf};

use serde_json::Value;
use sha2::{Digest, Sha256};

pub struct Paths {
    pub install_root: PathBuf,
    pub data_root: PathBuf,
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

    pub fn manifest_sha256(&self) -> Option<String> {
        std::fs::read(self.install_root.join("manifest.json")).ok().map(|b| format!("{:x}", Sha256::digest(&b)))
    }
}
