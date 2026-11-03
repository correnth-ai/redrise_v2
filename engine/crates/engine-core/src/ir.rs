//! Versioned intermediate representation (procedure). Closed action set; no
//! scripts. Unknown fields and versions are rejected on load.
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::model::{MouseButton, Rect};
use crate::ports::Modifiers;
use crate::recording::hex;

pub const IR_VERSION: u32 = 1;
/// IR v2 = v1 + browser actions (category `browser` only).
pub const IR_VERSION_BROWSER: u32 = 2;
pub const CATEGORY_WINDOWS: &str = "windows";
pub const CATEGORY_BROWSER: &str = "browser";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Procedure {
    pub ir_version: u32,
    pub category: String,
    pub platform: String,
    pub source: SourceRef,
    pub target_process: String,
    #[serde(default)]
    pub params: Vec<ParamSpec>,
    pub steps: Vec<Step>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SourceRef {
    pub recording_id: String,
    pub events_sha256: String,
    pub input_origin: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ParamSpec {
    pub name: String,
    pub role: ParamRole,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ParamRole {
    /// A file path the procedure writes to; must not exist before the run.
    OutputPath,
    Text,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WindowMatch {
    pub process_image: String,
    pub class: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Step {
    pub id: u32,
    /// Inclusive raw-event sequence range this step was compiled from.
    pub from_seq: [u64; 2],
    pub expect: WindowMatch,
    pub action: Action,
    /// Delivering this step may persist an external effect (e.g. a save).
    #[serde(default)]
    pub effectful: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case", deny_unknown_fields)]
pub enum Action {
    Click {
        button: MouseButton,
        rel_x: i32,
        rel_y: i32,
        window_rect: Rect,
    },
    Key {
        vk: u16,
        #[serde(default)]
        mods: Modifiers,
    },
    TypeText {
        text: TextValue,
    },
    // IR v2 — browser category only.
    BrowserGoto {
        url: String,
    },
    BrowserClick {
        selector: String,
    },
    BrowserFill {
        selector: String,
        text: TextValue,
    },
    BrowserPress {
        selector: String,
        key: String,
    },
}

impl Action {
    pub fn is_browser(&self) -> bool {
        matches!(
            self,
            Action::BrowserGoto { .. }
                | Action::BrowserClick { .. }
                | Action::BrowserFill { .. }
                | Action::BrowserPress { .. }
        )
    }

    fn text(&self) -> Option<&TextValue> {
        match self {
            Action::TypeText { text } | Action::BrowserFill { text, .. } => Some(text),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", deny_unknown_fields)]
pub enum TextValue {
    Literal(String),
    Param(String),
}

#[derive(Debug, PartialEq, Eq)]
pub enum IrError {
    Parse(String),
    UnsupportedVersion(u32),
    Invalid(String),
}

impl Procedure {
    pub fn to_canonical_json(&self) -> Vec<u8> {
        serde_json::to_vec_pretty(self).expect("procedure serializes")
    }

    pub fn sha256(&self) -> String {
        hex(&Sha256::digest(self.to_canonical_json()))
    }

    pub fn from_json(bytes: &[u8]) -> Result<Self, IrError> {
        #[derive(Deserialize)]
        struct Probe {
            ir_version: u32,
        }
        let probe: Probe =
            serde_json::from_slice(bytes).map_err(|e| IrError::Parse(e.to_string()))?;
        if probe.ir_version != IR_VERSION && probe.ir_version != IR_VERSION_BROWSER {
            return Err(IrError::UnsupportedVersion(probe.ir_version));
        }
        let p: Procedure =
            serde_json::from_slice(bytes).map_err(|e| IrError::Parse(e.to_string()))?;
        p.validate()?;
        Ok(p)
    }

    pub fn validate(&self) -> Result<(), IrError> {
        if self.steps.is_empty() {
            return Err(IrError::Invalid("procedure has no steps".into()));
        }
        let browser = self.category == CATEGORY_BROWSER;
        let expected_version = if browser {
            IR_VERSION_BROWSER
        } else {
            IR_VERSION
        };
        if self.ir_version != expected_version || !(browser || self.category == CATEGORY_WINDOWS) {
            return Err(IrError::Invalid(format!(
                "category {} requires ir_version {expected_version}",
                self.category
            )));
        }
        for (i, s) in self.steps.iter().enumerate() {
            if s.id != i as u32 {
                return Err(IrError::Invalid(format!(
                    "step ids must be 0..n, got {} at {i}",
                    s.id
                )));
            }
            if s.action.is_browser() != browser {
                return Err(IrError::Invalid(format!(
                    "step {i} action does not belong to category {}",
                    self.category
                )));
            }
            match s.action.text() {
                Some(TextValue::Param(name)) if !self.params.iter().any(|p| &p.name == name) => {
                    return Err(IrError::Invalid(format!(
                        "step {i} references undeclared param {name}"
                    )));
                }
                Some(TextValue::Literal(t))
                    if t.chars().any(char::is_control)
                        || (t.is_empty() && matches!(s.action, Action::TypeText { .. })) =>
                {
                    return Err(IrError::Invalid(format!(
                        "step {i} literal text empty or has control chars"
                    )));
                }
                _ => {}
            }
            if let Action::BrowserGoto { url } = &s.action {
                if !(url.starts_with("http://") || url.starts_with("https://")) {
                    return Err(IrError::Invalid(format!("step {i} goto must be http(s)")));
                }
            }
        }
        Ok(())
    }
}
