//! Raw captured events and window identity.
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(deny_unknown_fields)]
pub struct Rect {
    pub left: i32,
    pub top: i32,
    pub right: i32,
    pub bottom: i32,
}

/// Identity of the foreground top-level window when an event happened.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WindowRef {
    pub pid: u32,
    /// Lower-case executable file name, e.g. `excel.exe`.
    pub process_image: String,
    pub class: String,
    pub title: String,
    pub rect: Rect,
}

impl WindowRef {
    pub fn same_surface(&self, other: &WindowRef) -> bool {
        self.process_image == other.process_image && self.class == other.class
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MouseButton {
    Left,
    Right,
    Middle,
    Other,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case", deny_unknown_fields)]
pub enum RawKind {
    Key {
        vk: u16,
        scan: u16,
        down: bool,
        extended: bool,
        /// Character produced by the active layout, if any (informative for
        /// modified keys; authoritative for plain text runs).
        ch: Option<String>,
        /// The key is a dead key (accent composition); compiler refuses it.
        dead: bool,
    },
    Mouse {
        button: MouseButton,
        down: bool,
        x: i32,
        y: i32,
    },
    Wheel {
        delta: i32,
        x: i32,
        y: i32,
    },
    // Browser surface (trusted DOM events from the browser adapter).
    BrowserGoto {
        url: String,
    },
    BrowserClick {
        selector: String,
    },
    BrowserFill {
        selector: String,
        value: String,
    },
    BrowserPress {
        selector: String,
        key: String,
    },
    /// Something the user did that the recorder cannot represent.
    BrowserUnsupported {
        reason: String,
    },
}

/// Process image used for browser-surface window identities.
pub const BROWSER_SURFACE: &str = "redrise-browser";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RawEvent {
    /// Gap-free sequence assigned by the producer.
    pub seq: u64,
    /// Monotonic microseconds since capture start.
    pub t_us: u64,
    pub kind: RawKind,
    pub window: WindowRef,
}
