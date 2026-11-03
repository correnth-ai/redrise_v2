//! Recording -> procedure. Deterministic; refuses ambiguous or unsupported
//! input with diagnostics instead of inventing steps.
use std::collections::BTreeMap;

use serde::Serialize;

use crate::ir::{
    Action, ParamRole, ParamSpec, Procedure, SourceRef, Step, TextValue, WindowMatch,
    CATEGORY_BROWSER, CATEGORY_WINDOWS, IR_VERSION, IR_VERSION_BROWSER,
};
use crate::model::{MouseButton, RawEvent, RawKind, WindowRef, BROWSER_SURFACE};
use crate::ports::Modifiers;
use crate::recording::Manifest;

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Diagnostic {
    pub code: &'static str,
    pub seq: Option<u64>,
    pub message: String,
}

fn diag(code: &'static str, seq: Option<u64>, message: impl Into<String>) -> Diagnostic {
    Diagnostic {
        code,
        seq,
        message: message.into(),
    }
}

/// Declared parameter: the literal typed during the demonstration.
#[derive(Debug, Clone)]
pub struct ParamDecl {
    pub name: String,
    pub role: ParamRole,
    pub literal: String,
}

pub const VK_RETURN: u16 = 0x0D;
const VK_S: u16 = 0x53;
const VK_PACKET: u16 = 0xE7;
/// Maximum pointer travel between down and up still treated as a click.
const CLICK_SLOP_PX: i32 = 4;
const DIALOG_CLASS: &str = "#32770";

fn modifier_of(vk: u16) -> Option<u8> {
    match vk {
        0x10 | 0xA0 | 0xA1 => Some(0), // shift
        0x11 | 0xA2 | 0xA3 => Some(1), // ctrl
        0x12 | 0xA4 | 0xA5 => Some(2), // alt
        0x5B | 0x5C => Some(3),        // win
        _ => None,
    }
}

#[derive(Default)]
struct ModState {
    shift: u8,
    ctrl: u8,
    alt: u8,
    win: u8,
}

impl ModState {
    fn apply(&mut self, which: u8, down: bool, vk: u16) {
        // Track left/right/generic separately via a bitmask per modifier.
        let bit = match vk {
            0xA0 | 0xA2 | 0xA4 | 0x5B => 1,
            0xA1 | 0xA3 | 0xA5 | 0x5C => 2,
            _ => 4,
        };
        let slot = match which {
            0 => &mut self.shift,
            1 => &mut self.ctrl,
            2 => &mut self.alt,
            _ => &mut self.win,
        };
        if down {
            *slot |= bit
        } else {
            *slot &= !bit
        }
    }
    fn mods(&self) -> Modifiers {
        Modifiers {
            shift: self.shift != 0,
            ctrl: self.ctrl != 0,
            alt: self.alt != 0,
            win: self.win != 0,
        }
    }
}

struct Builder {
    steps: Vec<Step>,
    text: String,
    text_window: Option<WindowRef>,
    text_from: u64,
    text_to: u64,
}

impl Builder {
    fn push(&mut self, from: u64, to: u64, window: &WindowRef, action: Action) {
        self.flush();
        let id = self.steps.len() as u32;
        self.steps.push(Step {
            id,
            from_seq: [from, to],
            expect: matcher(window),
            action,
            effectful: false,
        });
    }
    fn add_char(&mut self, seq: u64, window: &WindowRef, ch: &str) {
        if let Some(w) = &self.text_window {
            if !w.same_surface(window) {
                self.flush();
            }
        }
        if self.text_window.is_none() {
            self.text_window = Some(window.clone());
            self.text_from = seq;
        }
        self.text.push_str(ch);
        self.text_to = seq;
    }
    fn flush(&mut self) {
        if let Some(w) = self.text_window.take() {
            let id = self.steps.len() as u32;
            let text = std::mem::take(&mut self.text);
            self.steps.push(Step {
                id,
                from_seq: [self.text_from, self.text_to],
                expect: matcher(&w),
                action: Action::TypeText {
                    text: TextValue::Literal(text),
                },
                effectful: false,
            });
        }
    }
}

fn matcher(w: &WindowRef) -> WindowMatch {
    WindowMatch {
        process_image: w.process_image.clone(),
        class: w.class.clone(),
    }
}

fn printable(ch: &str) -> bool {
    !ch.is_empty() && !ch.chars().any(char::is_control)
}

pub fn compile(
    manifest: &Manifest,
    events: &[RawEvent],
    params: &[ParamDecl],
) -> Result<Procedure, Vec<Diagnostic>> {
    if manifest.target_process == BROWSER_SURFACE && !events.is_empty() {
        return compile_browser(manifest, events, params);
    }
    let mut diags = Vec::new();
    if events.is_empty() {
        return Err(vec![diag(
            "empty_recording",
            None,
            "recording has no events",
        )]);
    }
    let mut mods = ModState::default();
    let mut b = Builder {
        steps: Vec::new(),
        text: String::new(),
        text_window: None,
        text_from: 0,
        text_to: 0,
    };
    // Pending mouse-down per button: (seq, x, y, window).
    let mut pending: BTreeMap<u8, (u64, i32, i32, WindowRef)> = BTreeMap::new();
    // A modifier pressed and released with nothing in between is a key of
    // its own (e.g. Alt opens ribbon accelerators); it is never dropped.
    let mut lone_mod: Option<(u16, u64)> = None;

    for ev in events {
        match &ev.kind {
            RawKind::Key {
                vk, down, ch, dead, ..
            } => {
                if let Some(which) = modifier_of(*vk) {
                    let was_idle = !mods.mods().any();
                    mods.apply(which, *down, *vk);
                    if *down {
                        lone_mod = if was_idle && lone_mod.is_none() {
                            Some((*vk, ev.seq))
                        } else {
                            None
                        };
                    } else if let Some((lvk, from)) = lone_mod.take() {
                        if lvk == *vk {
                            b.push(
                                from,
                                ev.seq,
                                &ev.window,
                                Action::Key {
                                    vk: *vk,
                                    mods: Modifiers::default(),
                                },
                            );
                        }
                    }
                    continue;
                }
                if !*down {
                    continue;
                }
                lone_mod = None;
                if *vk == VK_PACKET && ch.as_deref().map(printable) != Some(true) {
                    diags.push(diag(
                        "vk_packet_unsupported",
                        Some(ev.seq),
                        "Unicode packet without a printable character (lone surrogate or control)",
                    ));
                    continue;
                }
                if *dead {
                    diags.push(diag(
                        "dead_key_unsupported",
                        Some(ev.seq),
                        format!("dead key vk=0x{vk:02X}"),
                    ));
                    continue;
                }
                let m = mods.mods();
                let text_ok = !m.win && !(m.ctrl ^ m.alt); // plain, shift, or AltGr (ctrl+alt)
                match ch {
                    Some(c) if text_ok && printable(c) => b.add_char(ev.seq, &ev.window, c),
                    _ => b.push(ev.seq, ev.seq, &ev.window, Action::Key { vk: *vk, mods: m }),
                }
            }
            RawKind::Mouse { button, down, x, y } => {
                lone_mod = None;
                if *button != MouseButton::Left {
                    diags.push(diag(
                        "mouse_button_unsupported",
                        Some(ev.seq),
                        format!("{button:?} button"),
                    ));
                    continue;
                }
                if *down {
                    b.flush();
                    pending.insert(0, (ev.seq, *x, *y, ev.window.clone()));
                } else if let Some((from, dx, dy, w)) = pending.remove(&0) {
                    if (x - dx).abs() > CLICK_SLOP_PX || (y - dy).abs() > CLICK_SLOP_PX {
                        diags.push(diag(
                            "drag_unsupported",
                            Some(ev.seq),
                            "pointer moved between press and release",
                        ));
                        continue;
                    }
                    let action = Action::Click {
                        button: MouseButton::Left,
                        rel_x: dx - w.rect.left,
                        rel_y: dy - w.rect.top,
                        window_rect: w.rect,
                    };
                    b.push(from, ev.seq, &w, action);
                } else {
                    diags.push(diag(
                        "orphan_mouse_up",
                        Some(ev.seq),
                        "release without press",
                    ));
                }
            }
            RawKind::Wheel { .. } => diags.push(diag(
                "wheel_unsupported",
                Some(ev.seq),
                "scroll is not in IR v1",
            )),
            _ => diags.push(diag(
                "mixed_surface",
                Some(ev.seq),
                "browser event inside a native recording",
            )),
        }
    }
    b.flush();
    if !pending.is_empty() {
        diags.push(diag(
            "unterminated_click",
            None,
            "recording ended with a button held",
        ));
    }

    let mut steps = b.steps;
    // Effectful heuristics (conservative): any key or click delivered to a
    // standard dialog (it may confirm a save/overwrite), and Ctrl+S. A later
    // failure after such a step is reported uncertain, never failed.
    for s in &mut steps {
        s.effectful = match &s.action {
            Action::Key { vk, mods } => {
                s.expect.class == DIALOG_CLASS || (*vk == VK_S && mods.ctrl && !mods.alt)
            }
            Action::Click { .. } => s.expect.class == DIALOG_CLASS,
            _ => false,
        };
    }

    finish(manifest, steps, diags, params, IR_VERSION, CATEGORY_WINDOWS)
}

/// Shared tail: parameter slots, emptiness, validation.
fn finish(
    manifest: &Manifest,
    mut steps: Vec<Step>,
    mut diags: Vec<Diagnostic>,
    params: &[ParamDecl],
    ir_version: u32,
    category: &str,
) -> Result<Procedure, Vec<Diagnostic>> {
    let mut specs = Vec::new();
    for p in params {
        let is_literal = |s: &Step| match &s.action {
            Action::TypeText {
                text: TextValue::Literal(t),
            }
            | Action::BrowserFill {
                text: TextValue::Literal(t),
                ..
            } => *t == p.literal,
            _ => false,
        };
        let hits: Vec<usize> = steps
            .iter()
            .enumerate()
            .filter(|(_, s)| is_literal(s))
            .map(|(i, _)| i)
            .collect();
        match hits.as_slice() {
            [i] => {
                let slot = TextValue::Param(p.name.clone());
                match &mut steps[*i].action {
                    Action::TypeText { text } | Action::BrowserFill { text, .. } => *text = slot,
                    _ => unreachable!("filtered above"),
                }
                specs.push(ParamSpec {
                    name: p.name.clone(),
                    role: p.role,
                });
            }
            [] => diags.push(diag(
                "param_not_found",
                None,
                format!("no typed text equals the literal of '{}'", p.name),
            )),
            _ => diags.push(diag(
                "param_ambiguous",
                None,
                format!("'{}' literal typed {} times", p.name, hits.len()),
            )),
        }
    }
    if steps.is_empty() {
        diags.push(diag(
            "no_steps",
            None,
            "recording produced no actionable steps",
        ));
    }
    if !diags.is_empty() {
        return Err(diags);
    }
    let proc = Procedure {
        ir_version,
        category: category.into(),
        platform: manifest.platform.clone(),
        source: SourceRef {
            recording_id: manifest.recording_id.clone(),
            events_sha256: manifest.events_sha256.clone(),
            input_origin: manifest.input_origin.clone(),
        },
        target_process: manifest.target_process.clone(),
        params: specs,
        steps,
    };
    proc.validate()
        .map_err(|e| vec![diag("invalid_procedure", None, format!("{e:?}"))])?;
    Ok(proc)
}

/// Browser recordings: one step per trusted DOM action. Duplicate fills
/// (the recorder commits a value on Enter and again on change) collapse.
/// Clicks and Enter presses may submit, so they are effectful.
fn compile_browser(
    manifest: &Manifest,
    events: &[RawEvent],
    params: &[ParamDecl],
) -> Result<Procedure, Vec<Diagnostic>> {
    let mut diags = Vec::new();
    let mut steps: Vec<Step> = Vec::new();
    for ev in events {
        let (action, effectful) = match &ev.kind {
            RawKind::BrowserGoto { url } => (Action::BrowserGoto { url: url.clone() }, false),
            RawKind::BrowserClick { selector } => (
                Action::BrowserClick {
                    selector: selector.clone(),
                },
                true,
            ),
            RawKind::BrowserFill { selector, value } => {
                let dup = matches!(steps.last().map(|s| &s.action),
                    Some(Action::BrowserFill { selector: ls, text: TextValue::Literal(lv) }) if ls == selector && lv == value);
                if dup {
                    continue;
                }
                (
                    Action::BrowserFill {
                        selector: selector.clone(),
                        text: TextValue::Literal(value.clone()),
                    },
                    false,
                )
            }
            RawKind::BrowserPress { selector, key } => (
                Action::BrowserPress {
                    selector: selector.clone(),
                    key: key.clone(),
                },
                key == "Enter",
            ),
            RawKind::BrowserUnsupported { reason } => {
                diags.push(diag("browser_unsupported", Some(ev.seq), reason.clone()));
                continue;
            }
            _ => {
                diags.push(diag(
                    "mixed_surface",
                    Some(ev.seq),
                    "native input inside a browser recording",
                ));
                continue;
            }
        };
        let id = steps.len() as u32;
        steps.push(Step {
            id,
            from_seq: [ev.seq, ev.seq],
            expect: WindowMatch {
                process_image: BROWSER_SURFACE.into(),
                class: ev.window.class.clone(),
            },
            action,
            effectful,
        });
    }
    if !matches!(
        steps.first().map(|s| &s.action),
        Some(Action::BrowserGoto { .. })
    ) {
        diags.push(diag(
            "browser_no_start_url",
            None,
            "a browser procedure must start with the recorded URL",
        ));
    }
    finish(
        manifest,
        steps,
        diags,
        params,
        IR_VERSION_BROWSER,
        CATEGORY_BROWSER,
    )
}
