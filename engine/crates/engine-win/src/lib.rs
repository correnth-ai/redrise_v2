//! Windows adapters for the Engine ports. All `unsafe` Win32 access of the
//! Engine is confined to this crate.
#![cfg(windows)]

mod guard;
mod hooks;
mod inject;
mod session;
mod util;
mod window;

pub use guard::{WinInputGuard, ENGINE_TAG};
pub use hooks::{probe_hooks, WinInputSource};
pub use inject::WinInjector;
pub use session::WinSession;
pub use window::{foreground_window, WinWindows};

use std::path::Path;
use std::time::Instant;

use engine_core::ports::{FileProbe, Pacer};

/// Must run before any coordinate is read or injected so capture and replay
/// both use physical pixels.
pub fn init_dpi_awareness() -> bool {
    use windows_sys::Win32::UI::HiDpi::{
        SetProcessDpiAwarenessContext, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2,
    };
    unsafe { SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2) != 0 }
}

pub struct StdFiles;
impl FileProbe for StdFiles {
    fn exists(&self, p: &Path) -> bool {
        p.exists()
    }
    fn parent_exists(&self, p: &Path) -> bool {
        p.parent().map(|d| d.is_dir()).unwrap_or(false)
    }
}

pub struct StdPacer(Instant);
impl Default for StdPacer {
    fn default() -> Self {
        Self(Instant::now())
    }
}
impl Pacer for StdPacer {
    fn sleep_ms(&self, ms: u64) {
        std::thread::sleep(std::time::Duration::from_millis(ms));
    }
    fn now_ms(&self) -> u64 {
        self.0.elapsed().as_millis() as u64
    }
}
