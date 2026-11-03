//! Ports (small interfaces). Domain code depends only on these traits;
//! platform adapters implement them.
use std::path::Path;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::mpsc::{SyncSender, TrySendError};
use std::sync::Arc;

use crate::model::{MouseButton, RawEvent, WindowRef};

// ---------------------------------------------------------------- capture

/// Non-blocking handle a producer uses to offer events. Never blocks, so an
/// OS hook callback can call it. Not `Clone`: exactly one producer owns it,
/// and it assigns gap-free sequence numbers to accepted events only.
pub struct EventTx {
    tx: SyncSender<RawEvent>,
    next_seq: u64,
    dropped: Arc<AtomicU64>,
    writer_gone: Arc<AtomicBool>,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Offer {
    Accepted,
    /// Channel full; counted, and the recording becomes lossy.
    Dropped,
    /// Writer ended (failure or stop); producer should stop.
    WriterGone,
}

impl EventTx {
    pub fn new(
        tx: SyncSender<RawEvent>,
        dropped: Arc<AtomicU64>,
        writer_gone: Arc<AtomicBool>,
    ) -> Self {
        Self {
            tx,
            next_seq: 0,
            dropped,
            writer_gone,
        }
    }

    /// Offers an event; its `seq` is overwritten with the next sequence.
    pub fn offer(&mut self, mut ev: RawEvent) -> Offer {
        ev.seq = self.next_seq;
        match self.tx.try_send(ev) {
            Ok(()) => {
                self.next_seq += 1;
                Offer::Accepted
            }
            Err(TrySendError::Full(_)) => {
                self.dropped.fetch_add(1, Ordering::Relaxed);
                Offer::Dropped
            }
            Err(TrySendError::Disconnected(_)) => {
                self.writer_gone.store(true, Ordering::Relaxed);
                Offer::WriterGone
            }
        }
    }
}

#[derive(Debug, Default, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct SourceStats {
    pub filtered_out: u64,
    pub injected_ignored: u64,
    pub injected_accepted: u64,
}

/// Starts producing events into `tx`. The source owns the only `EventTx`;
/// dropping it (when the producer ends) is the end-of-stream signal.
pub trait InputSource {
    fn spawn(self: Box<Self>, tx: EventTx) -> Result<Box<dyn RunningSource>, String>;
}

pub trait RunningSource: Send {
    /// Idempotent, non-blocking stop request.
    fn request_stop(&self);
    /// Confirms the producer still delivers events (called before stop).
    /// `Err` marks the recording `source_stale`. Default: no check available.
    fn check_liveness(&self) -> Result<(), String> {
        Ok(())
    }
    /// Blocks until the producer ended; `Err` means the producer failed.
    fn join(self: Box<Self>) -> Result<SourceStats, String>;
}

/// Durable sink of one recording.
pub trait RecordingWriter: Send {
    fn write(&mut self, ev: &RawEvent) -> std::io::Result<()>;
    /// Events durably accepted so far.
    fn count(&self) -> u64;
    /// Flush and seal with the given manifest status.
    fn seal(
        self: Box<Self>,
        summary: &crate::recording::Summary,
    ) -> std::io::Result<crate::recording::Manifest>;
}

// ---------------------------------------------------------------- execution

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, serde::Serialize, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Modifiers {
    #[serde(default)]
    pub ctrl: bool,
    #[serde(default)]
    pub shift: bool,
    #[serde(default)]
    pub alt: bool,
    #[serde(default)]
    pub win: bool,
}

impl Modifiers {
    pub fn any(&self) -> bool {
        self.ctrl || self.shift || self.alt || self.win
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum InjectError {
    /// The OS accepted fewer inputs than sent.
    Partial {
        sent: u32,
        accepted: u32,
    },
    Other(String),
}

pub trait WindowInspector {
    fn foreground(&self) -> Option<WindowRef>;
    /// Try to bring a top-level window of `process_image`/`class` forward.
    fn activate(&self, process_image: &str, class: &str) -> bool;
    /// Root owner of the foreground window: the top-level window itself, or
    /// the window that owns a dialog. Needed only for bound runs.
    fn foreground_root(&self) -> Option<u64> {
        None
    }
    /// Try to bring exactly this top-level window forward.
    fn activate_window(&self, _root: u64) -> bool {
        false
    }
}

pub trait InputInjector {
    fn click(&self, button: MouseButton, x: i32, y: i32) -> Result<(), InjectError>;
    fn key(&self, vk: u16, mods: Modifiers) -> Result<(), InjectError>;
    /// Types one character (layout-independent).
    fn type_char(&self, ch: char) -> Result<(), InjectError>;
    /// Releases any modifier currently held. Must be safe to call anytime.
    fn release_modifiers(&self);
}

/// Watches, during a native run, for input the Engine did not send itself (a
/// person or another program). Pointer movement alone is not interference.
pub trait InterferenceMonitor {
    /// `Err` when the monitor could not be armed; the run is then refused.
    fn ready(&self) -> Result<(), String>;
    /// First foreign input observed since the monitor was armed, if any.
    fn observed(&self) -> Option<String>;
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct Readiness {
    pub platform: String,
    pub interactive_desktop: bool,
    pub detail: Vec<String>,
}

pub trait SessionProbe {
    fn readiness(&self) -> Readiness;
    /// `Some(false)` when the target process runs at a higher integrity level
    /// than the Engine (input would be silently blocked by UIPI).
    fn can_drive_process(&self, pid: u32) -> Option<bool>;
}

pub trait FileProbe {
    fn exists(&self, path: &Path) -> bool;
    fn parent_exists(&self, path: &Path) -> bool;
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BrowserError {
    pub code: String,
    pub detail: String,
    /// The action may have reached the page (e.g. click dispatched, then error).
    pub partial: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BrowserState {
    pub url: String,
    pub title: String,
}

/// Browser surface driven through the packaged adapter. Each call is one
/// attempt; implementations never retry.
pub trait BrowserDriver {
    fn state(&self) -> Result<BrowserState, BrowserError>;
    fn goto(&self, url: &str) -> Result<(), BrowserError>;
    fn click(&self, selector: &str) -> Result<(), BrowserError>;
    fn fill(&self, selector: &str, value: &str) -> Result<(), BrowserError>;
    fn press(&self, selector: &str, key: &str) -> Result<(), BrowserError>;
}

/// `scheme://host[:port]` of a URL (no path), used as the browser surface id.
pub fn url_origin(url: &str) -> String {
    match url.find("://") {
        Some(i) => {
            let rest = &url[i + 3..];
            let end = rest.find(['/', '?', '#']).unwrap_or(rest.len());
            format!("{}://{}", &url[..i], &rest[..end])
        }
        None => url.to_string(),
    }
}

pub trait Pacer {
    fn sleep_ms(&self, ms: u64);
    fn now_ms(&self) -> u64;
}

/// Cooperative cancellation shared with the executor.
#[derive(Clone, Default)]
pub struct CancelToken(Arc<AtomicBool>);

impl CancelToken {
    pub fn cancel(&self) {
        self.0.store(true, Ordering::SeqCst);
    }
    pub fn is_cancelled(&self) -> bool {
        self.0.load(Ordering::SeqCst)
    }
}
