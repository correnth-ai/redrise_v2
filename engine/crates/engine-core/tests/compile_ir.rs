//! E03 compiler and IR regressions.
use engine_core::compile::{compile, ParamDecl};
use engine_core::ir::{Action, IrError, ParamRole, Procedure, TextValue};
use engine_core::model::{MouseButton, RawEvent, RawKind, Rect, WindowRef};
use engine_core::recording::{Manifest, RecordingStatus};

fn win(class: &str) -> WindowRef {
    WindowRef {
        pid: 7,
        process_image: "excel.exe".into(),
        class: class.into(),
        title: "Book".into(),
        rect: Rect {
            left: 100,
            top: 50,
            right: 1100,
            bottom: 850,
        },
    }
}

struct Rec {
    events: Vec<RawEvent>,
}

impl Rec {
    fn new() -> Self {
        Self { events: Vec::new() }
    }
    fn push(&mut self, kind: RawKind, class: &str) -> &mut Self {
        let seq = self.events.len() as u64;
        self.events.push(RawEvent {
            seq,
            t_us: seq * 10,
            kind,
            window: win(class),
        });
        self
    }
    fn key(&mut self, vk: u16, ch: Option<&str>, class: &str) -> &mut Self {
        self.push(
            RawKind::Key {
                vk,
                scan: 0,
                down: true,
                extended: false,
                ch: ch.map(Into::into),
                dead: false,
            },
            class,
        );
        self.push(
            RawKind::Key {
                vk,
                scan: 0,
                down: false,
                extended: false,
                ch: None,
                dead: false,
            },
            class,
        )
    }
    fn text(&mut self, s: &str, class: &str) -> &mut Self {
        for c in s.chars() {
            let upper = c.is_uppercase();
            if upper {
                self.push(
                    RawKind::Key {
                        vk: 0xA0,
                        scan: 0,
                        down: true,
                        extended: false,
                        ch: None,
                        dead: false,
                    },
                    class,
                );
            }
            let vk = if c.is_ascii_alphanumeric() || c == ' ' {
                c.to_ascii_uppercase() as u16
            } else {
                0xE2
            };
            self.key(vk, Some(&c.to_string()), class);
            if upper {
                self.push(
                    RawKind::Key {
                        vk: 0xA0,
                        scan: 0,
                        down: false,
                        extended: false,
                        ch: None,
                        dead: false,
                    },
                    class,
                );
            }
        }
        self
    }
    fn click(&mut self, x: i32, y: i32, class: &str) -> &mut Self {
        self.push(
            RawKind::Mouse {
                button: MouseButton::Left,
                down: true,
                x,
                y,
            },
            class,
        );
        self.push(
            RawKind::Mouse {
                button: MouseButton::Left,
                down: false,
                x,
                y,
            },
            class,
        )
    }
}

fn manifest() -> Manifest {
    Manifest {
        format: 1,
        recording_id: "r1".into(),
        status: RecordingStatus::Complete,
        reason: None,
        platform: "windows-x86_64".into(),
        target_process: "excel.exe".into(),
        input_origin: "synthetic-test".into(),
        event_count: 0,
        events_sha256: "00".into(),
        dropped: 0,
        source: Default::default(),
        started_at_unix_ms: 0,
        duration_ms: 0,
        engine_version: "test".into(),
    }
}

const F5: u16 = 0x74;
const F12: u16 = 0x7B;
const RET: u16 = 0x0D;

fn s1() -> Rec {
    let mut r = Rec::new();
    r.click(600, 400, "XLMAIN")
        .key(F5, None, "XLMAIN")
        .text("B2", "#32770")
        .key(RET, Some("\r"), "#32770")
        .text("Cliente Teste 01", "XLMAIN")
        .key(RET, Some("\r"), "XLMAIN")
        .text("1500", "XLMAIN")
        .key(RET, Some("\r"), "XLMAIN")
        .key(F12, None, "XLMAIN")
        .text("C:\\out\\gravado.xlsx", "#32770")
        .key(RET, Some("\r"), "#32770");
    r
}

#[test]
fn compiles_excel_scenario_into_expected_steps() {
    let r = s1();
    let p = compile(&manifest(), &r.events, &[]).unwrap();
    let kinds: Vec<String> = p
        .steps
        .iter()
        .map(|s| match &s.action {
            Action::Click { rel_x, rel_y, .. } => {
                format!("click({rel_x},{rel_y})@{}", s.expect.class)
            }
            Action::Key { vk, .. } => format!("key({vk:#x})@{}", s.expect.class),
            Action::TypeText {
                text: TextValue::Literal(t),
            } => format!("type({t})@{}", s.expect.class),
            Action::TypeText {
                text: TextValue::Param(n),
            } => format!("param({n})"),
            _ => unreachable!("native scenario"),
        })
        .collect();
    assert_eq!(
        kinds,
        vec![
            "click(500,350)@XLMAIN",
            "key(0x74)@XLMAIN",
            "type(B2)@#32770",
            "key(0xd)@#32770",
            "type(Cliente Teste 01)@XLMAIN",
            "key(0xd)@XLMAIN",
            "type(1500)@XLMAIN",
            "key(0xd)@XLMAIN",
            "key(0x7b)@XLMAIN",
            "type(C:\\out\\gravado.xlsx)@#32770",
            "key(0xd)@#32770",
        ]
    );
    // Enter in a dialog is effectful; the Enter in the grid is not.
    assert!(p.steps[3].effectful && p.steps[10].effectful && !p.steps[5].effectful);
}

#[test]
fn output_param_replaces_exactly_one_literal() {
    let r = s1();
    let decl = ParamDecl {
        name: "output_path".into(),
        role: ParamRole::OutputPath,
        literal: "C:\\out\\gravado.xlsx".into(),
    };
    let p = compile(&manifest(), &r.events, &[decl]).unwrap();
    assert_eq!(
        p.steps[9].action,
        Action::TypeText {
            text: TextValue::Param("output_path".into())
        }
    );
    assert_eq!(p.params.len(), 1);
}

#[test]
fn param_absent_or_ambiguous_is_refused() {
    let r = s1();
    let absent = ParamDecl {
        name: "x".into(),
        role: ParamRole::Text,
        literal: "nope".into(),
    };
    let d = compile(&manifest(), &r.events, &[absent]).unwrap_err();
    assert_eq!(d[0].code, "param_not_found");

    let mut r2 = Rec::new();
    r2.text("same", "XLMAIN")
        .key(RET, Some("\r"), "XLMAIN")
        .text("same", "XLMAIN");
    let amb = ParamDecl {
        name: "x".into(),
        role: ParamRole::Text,
        literal: "same".into(),
    };
    let d = compile(&manifest(), &r2.events, &[amb]).unwrap_err();
    assert_eq!(d[0].code, "param_ambiguous");
}

#[test]
fn unsupported_input_is_refused_not_dropped() {
    let mut r = Rec::new();
    r.push(
        RawKind::Key {
            vk: 0xDE,
            scan: 0,
            down: true,
            extended: false,
            ch: None,
            dead: true,
        },
        "XLMAIN",
    );
    r.push(
        RawKind::Mouse {
            button: MouseButton::Right,
            down: true,
            x: 1,
            y: 1,
        },
        "XLMAIN",
    );
    r.push(
        RawKind::Wheel {
            delta: 120,
            x: 1,
            y: 1,
        },
        "XLMAIN",
    );
    r.push(
        RawKind::Mouse {
            button: MouseButton::Left,
            down: true,
            x: 10,
            y: 10,
        },
        "XLMAIN",
    );
    r.push(
        RawKind::Mouse {
            button: MouseButton::Left,
            down: false,
            x: 90,
            y: 10,
        },
        "XLMAIN",
    );
    let codes: Vec<&str> = compile(&manifest(), &r.events, &[])
        .unwrap_err()
        .iter()
        .map(|d| d.code)
        .collect();
    assert_eq!(
        codes,
        vec![
            "dead_key_unsupported",
            "mouse_button_unsupported",
            "wheel_unsupported",
            "drag_unsupported",
            "no_steps"
        ]
    );
}

#[test]
fn ctrl_chords_become_keys_and_altgr_text_stays_text() {
    let mut r = Rec::new();
    r.push(
        RawKind::Key {
            vk: 0xA2,
            scan: 0,
            down: true,
            extended: false,
            ch: None,
            dead: false,
        },
        "XLMAIN",
    );
    r.key(0x53, Some("\u{13}"), "XLMAIN"); // ctrl+S
    r.push(
        RawKind::Key {
            vk: 0xA5,
            scan: 0,
            down: true,
            extended: false,
            ch: None,
            dead: false,
        },
        "XLMAIN",
    ); // AltGr = ctrl+alt
    r.key(0x51, Some("/"), "XLMAIN");
    let p = compile(&manifest(), &r.events, &[]).unwrap();
    assert!(matches!(p.steps[0].action, Action::Key { vk: 0x53, mods } if mods.ctrl));
    assert!(p.steps[0].effectful);
    assert_eq!(
        p.steps[1].action,
        Action::TypeText {
            text: TextValue::Literal("/".into())
        }
    );
}

#[test]
fn empty_recording_refused() {
    assert_eq!(
        compile(&manifest(), &[], &[]).unwrap_err()[0].code,
        "empty_recording"
    );
}

#[test]
fn compilation_is_deterministic_and_roundtrips() {
    let r = s1();
    let a = compile(&manifest(), &r.events, &[]).unwrap();
    let b = compile(&manifest(), &r.events, &[]).unwrap();
    assert_eq!(a.sha256(), b.sha256());
    let back = Procedure::from_json(&a.to_canonical_json()).unwrap();
    assert_eq!(back, a);
}

#[test]
fn ir_rejects_unknown_version_fields_and_scripts() {
    let p = compile(&manifest(), &s1().events, &[]).unwrap();
    let mut v: serde_json::Value = serde_json::from_slice(&p.to_canonical_json()).unwrap();
    v["ir_version"] = 3.into();
    assert_eq!(
        Procedure::from_json(v.to_string().as_bytes()).unwrap_err(),
        IrError::UnsupportedVersion(3)
    );

    let mut v: serde_json::Value = serde_json::from_slice(&p.to_canonical_json()).unwrap();
    v["steps"][0]["script"] = "import os".into();
    assert!(matches!(
        Procedure::from_json(v.to_string().as_bytes()),
        Err(IrError::Parse(_))
    ));

    let mut v: serde_json::Value = serde_json::from_slice(&p.to_canonical_json()).unwrap();
    v["steps"][1]["action"] = serde_json::json!({"type": "shell", "command": "calc"});
    assert!(matches!(
        Procedure::from_json(v.to_string().as_bytes()),
        Err(IrError::Parse(_))
    ));

    let mut v: serde_json::Value = serde_json::from_slice(&p.to_canonical_json()).unwrap();
    v["steps"][2]["action"] =
        serde_json::json!({"type": "type_text", "text": {"param": "undeclared"}});
    assert!(matches!(
        Procedure::from_json(v.to_string().as_bytes()),
        Err(IrError::Invalid(_))
    ));
}

#[test]
fn lone_alt_tap_becomes_a_key_step_not_dropped() {
    let mut r = Rec::new();
    r.push(
        RawKind::Key {
            vk: 0xA4,
            scan: 0,
            down: true,
            extended: false,
            ch: None,
            dead: false,
        },
        "XLMAIN",
    );
    r.push(
        RawKind::Key {
            vk: 0xA4,
            scan: 0,
            down: false,
            extended: false,
            ch: None,
            dead: false,
        },
        "XLMAIN",
    );
    r.key(0x48, Some("h"), "XLMAIN");
    let p = compile(&manifest(), &r.events, &[]).unwrap();
    assert!(matches!(p.steps[0].action, Action::Key { vk: 0xA4, mods } if !mods.any()));
    assert_eq!(
        p.steps[1].action,
        Action::TypeText {
            text: TextValue::Literal("h".into())
        }
    );
}

#[test]
fn unicode_packet_without_char_is_refused() {
    let mut r = Rec::new();
    r.push(
        RawKind::Key {
            vk: 0xE7,
            scan: 0xD83D,
            down: true,
            extended: false,
            ch: None,
            dead: false,
        },
        "XLMAIN",
    );
    assert_eq!(
        compile(&manifest(), &r.events, &[]).unwrap_err()[0].code,
        "vk_packet_unsupported"
    );
}
