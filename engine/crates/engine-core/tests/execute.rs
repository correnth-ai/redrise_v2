//! E04 executor regressions with fakes. Fakes model OS behaviour; they do
//! not prove native replay (that is the native proof).
use std::cell::{Cell, RefCell};
use std::collections::BTreeMap;
use std::path::Path;

use engine_core::execute::{run, Delivery, Outcome, Ports, RunOptions};
use engine_core::ir::{
    Action, ParamRole, ParamSpec, Procedure, SourceRef, Step, TextValue, WindowMatch,
};
use engine_core::model::{MouseButton, Rect, WindowRef};
use engine_core::ports::{
    CancelToken, FileProbe, InjectError, InputInjector, InterferenceMonitor, Modifiers, Pacer,
    Readiness, SessionProbe, WindowInspector,
};

const RECT: Rect = Rect {
    left: 0,
    top: 0,
    right: 800,
    bottom: 600,
};

fn w(class: &str) -> WindowRef {
    WindowRef {
        pid: 9,
        process_image: "notepad.exe".into(),
        class: class.into(),
        title: "".into(),
        rect: RECT,
    }
}

fn step(id: u32, class: &str, action: Action, effectful: bool) -> Step {
    Step {
        id,
        from_seq: [0, 0],
        expect: WindowMatch {
            process_image: "notepad.exe".into(),
            class: class.into(),
        },
        action,
        effectful,
    }
}

fn procedure(steps: Vec<Step>, params: Vec<ParamSpec>) -> Procedure {
    Procedure {
        ir_version: 1,
        category: "windows".into(),
        platform: "windows-x86_64".into(),
        source: SourceRef {
            recording_id: "r".into(),
            events_sha256: "00".into(),
            input_origin: "synthetic-test".into(),
        },
        target_process: "notepad.exe".into(),
        params,
        steps,
    }
}

#[derive(Default)]
struct World {
    fg: RefCell<Vec<Option<WindowRef>>>, // scripted foreground per query; last repeats
    log: RefCell<Vec<String>>,
    released: Cell<u32>,
    fail_key: Cell<Option<u16>>,
    reject_all_keys: Cell<bool>,
    now: Cell<u64>,
    locked: Cell<bool>,
    high_il: Cell<bool>,
    existing: RefCell<Vec<String>>,
    cancel_after_inputs: Cell<Option<usize>>,
    cancel: CancelToken,
    /// Someone else presses a key once this many inputs were sent.
    foreign_after_inputs: Cell<Option<usize>>,
    guard_broken: Cell<bool>,
    /// Scripted root owner of the foreground window per query; last repeats.
    roots: RefCell<Vec<Option<u64>>>,
}

impl WindowInspector for World {
    fn foreground(&self) -> Option<WindowRef> {
        let mut v = self.fg.borrow_mut();
        if v.len() > 1 {
            v.remove(0)
        } else {
            v.first().cloned().flatten()
        }
    }
    fn activate(&self, _: &str, _: &str) -> bool {
        self.log.borrow_mut().push("activate".into());
        false
    }
    fn foreground_root(&self) -> Option<u64> {
        let mut v = self.roots.borrow_mut();
        if v.len() > 1 {
            v.remove(0)
        } else {
            v.first().cloned().flatten()
        }
    }
    fn activate_window(&self, root: u64) -> bool {
        self.log
            .borrow_mut()
            .push(format!("activate_window {root}"));
        false
    }
}

impl World {
    fn record(&self, s: String) {
        self.log.borrow_mut().push(s);
        if let Some(n) = self.cancel_after_inputs.get() {
            if self
                .log
                .borrow()
                .iter()
                .filter(|l| !l.starts_with("activate"))
                .count()
                >= n
            {
                self.cancel.cancel();
            }
        }
    }
}

impl InputInjector for World {
    fn click(&self, _b: MouseButton, x: i32, y: i32) -> Result<(), InjectError> {
        self.record(format!("click {x},{y}"));
        Ok(())
    }
    fn key(&self, vk: u16, _m: Modifiers) -> Result<(), InjectError> {
        if self.reject_all_keys.get() {
            return Err(InjectError::Partial {
                sent: 2,
                accepted: 0,
            });
        }
        if self.fail_key.get() == Some(vk) {
            return Err(InjectError::Partial {
                sent: 4,
                accepted: 2,
            });
        }
        self.record(format!("key {vk:#x}"));
        Ok(())
    }
    fn type_char(&self, ch: char) -> Result<(), InjectError> {
        self.record(format!("char {ch}"));
        Ok(())
    }
    fn release_modifiers(&self) {
        self.released.set(self.released.get() + 1);
    }
}

impl SessionProbe for World {
    fn readiness(&self) -> Readiness {
        Readiness {
            platform: "windows-x86_64".into(),
            interactive_desktop: !self.locked.get(),
            detail: vec!["locked".into()],
        }
    }
    fn can_drive_process(&self, _pid: u32) -> Option<bool> {
        Some(!self.high_il.get())
    }
}

impl InterferenceMonitor for World {
    fn ready(&self) -> Result<(), String> {
        if self.guard_broken.get() {
            Err("hooks not delivered".into())
        } else {
            Ok(())
        }
    }
    fn observed(&self) -> Option<String> {
        let n = self.foreign_after_inputs.get()?;
        (inputs(self).len() >= n).then(|| "keyboard input from hardware during the run".into())
    }
}

impl FileProbe for World {
    fn exists(&self, p: &Path) -> bool {
        self.existing.borrow().iter().any(|e| Path::new(e) == p)
    }
    fn parent_exists(&self, _p: &Path) -> bool {
        true
    }
}

impl Pacer for World {
    fn sleep_ms(&self, ms: u64) {
        self.now.set(self.now.get() + ms);
    }
    fn now_ms(&self) -> u64 {
        self.now.get()
    }
}

fn ports(world: &World) -> Ports<'_> {
    Ports {
        windows: world,
        input: world,
        session: world,
        files: world,
        pacer: world,
        cancel: world.cancel.clone(),
        browser: None,
        interference: None,
    }
}

fn guarded(world: &World) -> Ports<'_> {
    Ports {
        interference: Some(world),
        ..ports(world)
    }
}

fn inputs(world: &World) -> Vec<String> {
    world
        .log
        .borrow()
        .iter()
        .filter(|l| !l.starts_with("activate"))
        .cloned()
        .collect()
}

fn save_proc() -> Procedure {
    procedure(
        vec![
            step(
                0,
                "Notepad",
                Action::TypeText {
                    text: TextValue::Literal("Oi".into()),
                },
                false,
            ),
            step(
                1,
                "Notepad",
                Action::Key {
                    vk: 0x53,
                    mods: Modifiers {
                        ctrl: true,
                        ..Default::default()
                    },
                },
                true,
            ),
            step(
                2,
                "#32770",
                Action::TypeText {
                    text: TextValue::Param("out".into()),
                },
                false,
            ),
            step(
                3,
                "#32770",
                Action::Key {
                    vk: 0x0D,
                    mods: Modifiers::default(),
                },
                true,
            ),
        ],
        vec![ParamSpec {
            name: "out".into(),
            role: ParamRole::OutputPath,
        }],
    )
}

fn binds(v: &str) -> RunOptions {
    let mut b = BTreeMap::new();
    b.insert("out".to_string(), v.to_string());
    RunOptions {
        bindings: b,
        ..opts0()
    }
}

#[test]
fn happy_path_delivers_all_steps_but_is_only_unverified() {
    let world = World::default();
    *world.fg.borrow_mut() = vec![
        Some(w("Notepad")),
        Some(w("Notepad")),
        Some(w("Notepad")),
        Some(w("#32770")),
    ];
    let r = run(&save_proc(), &ports(&world), &binds("C:\\o\\x.txt"));
    assert_eq!(r.outcome, Outcome::CompletedUnverified, "{:?}", r.code);
    assert!(!r.verified);
    assert!(r.steps.iter().all(|s| s.delivery == Delivery::Delivered));
    assert_eq!(inputs(&world).join("|"), "char O|char i|key 0x53|char C|char :|char \\|char o|char \\|char x|char .|char t|char x|char t|key 0xd");
    assert!(world.released.get() >= 1);
}

#[test]
fn locked_session_refuses_before_any_input() {
    let world = World::default();
    world.locked.set(true);
    let r = run(&save_proc(), &ports(&world), &binds("C:\\o\\x.txt"));
    assert_eq!(r.outcome, Outcome::Refused);
    assert_eq!(r.code.as_deref(), Some("session_unavailable"));
    assert!(inputs(&world).is_empty());
}

#[test]
fn platform_mismatch_refuses() {
    let world = World::default();
    let mut p = save_proc();
    p.platform = "macos-aarch64".into();
    let r = run(&p, &ports(&world), &binds("C:\\o\\x.txt"));
    assert_eq!(r.code.as_deref(), Some("platform_mismatch"));
    assert!(inputs(&world).is_empty());
}

#[test]
fn existing_output_and_missing_or_unknown_binding_refuse() {
    let world = World::default();
    world.existing.borrow_mut().push("C:\\o\\x.txt".into());
    assert_eq!(
        run(&save_proc(), &ports(&world), &binds("C:\\o\\x.txt"))
            .code
            .as_deref(),
        Some("output_exists")
    );
    assert_eq!(
        run(&save_proc(), &ports(&world), &opts0()).code.as_deref(),
        Some("missing_binding")
    );
    let mut o = binds("C:\\o\\y.txt");
    o.bindings.insert("other".into(), "z".into());
    assert_eq!(
        run(&save_proc(), &ports(&world), &o).code.as_deref(),
        Some("unknown_binding")
    );
    assert_eq!(
        run(&save_proc(), &ports(&world), &binds("relative.txt"))
            .code
            .as_deref(),
        Some("output_path_not_absolute")
    );
    assert!(inputs(&world).is_empty());
}

#[test]
fn wrong_foreground_times_out_without_input() {
    let world = World::default();
    let mut other = w("Notepad");
    other.process_image = "chrome.exe".into();
    *world.fg.borrow_mut() = vec![Some(other)];
    let r = run(&save_proc(), &ports(&world), &binds("C:\\o\\x.txt"));
    assert_eq!(r.outcome, Outcome::Failed);
    assert_eq!(r.code.as_deref(), Some("focus_timeout"));
    assert!(inputs(&world).is_empty());
    assert!(world.log.borrow().iter().any(|l| l == "activate"));
}

#[test]
fn failure_after_effectful_step_is_uncertain_and_not_retried() {
    let world = World::default();
    *world.fg.borrow_mut() = vec![
        Some(w("Notepad")),
        Some(w("Notepad")),
        Some(w("Notepad")),
        Some(w("#32770")),
    ];
    world.fail_key.set(Some(0x0D));
    let r = run(&save_proc(), &ports(&world), &binds("C:\\o\\x.txt"));
    assert_eq!(r.outcome, Outcome::Uncertain);
    assert_eq!(r.failed_step, Some(3));
    assert_eq!(r.steps[3].delivery, Delivery::Partial);
    assert_eq!(
        inputs(&world)
            .iter()
            .filter(|l| l.as_str() == "key 0xd")
            .count(),
        0
    );
    assert!(world.released.get() >= 1, "modifiers released on failure");
}

#[test]
fn partial_delivery_of_effectful_step_is_uncertain() {
    let world = World::default();
    *world.fg.borrow_mut() = vec![Some(w("Notepad"))];
    world.fail_key.set(Some(0x53)); // ctrl+S partially delivered may have saved
    let r = run(&save_proc(), &ports(&world), &binds("C:\\o\\x.txt"));
    assert_eq!(r.outcome, Outcome::Uncertain);
}

#[test]
fn failure_before_any_effect_is_failed() {
    let world = World::default();
    *world.fg.borrow_mut() = vec![Some(w("Notepad"))];
    world.fail_key.set(Some(0x74));
    let p = procedure(
        vec![
            step(
                0,
                "Notepad",
                Action::TypeText {
                    text: TextValue::Literal("a".into()),
                },
                false,
            ),
            step(
                1,
                "Notepad",
                Action::Key {
                    vk: 0x74,
                    mods: Modifiers::default(),
                },
                false,
            ),
        ],
        vec![],
    );
    let r = run(&p, &ports(&world), &opts0());
    assert_eq!(r.outcome, Outcome::Failed);
    assert_eq!(r.failed_step, Some(1));
}

#[test]
fn focus_lost_mid_text_stops_typing() {
    let world = World::default();
    *world.fg.borrow_mut() = vec![Some(w("Notepad")), Some(w("Notepad")), None];
    let p = procedure(
        vec![step(
            0,
            "Notepad",
            Action::TypeText {
                text: TextValue::Literal("abcdef".into()),
            },
            false,
        )],
        vec![],
    );
    let r = run(&p, &ports(&world), &opts0());
    assert_eq!(r.code.as_deref(), Some("focus_lost_during_input"));
    assert_eq!(r.steps[0].delivery, Delivery::Partial);
    assert!(inputs(&world).len() < 6);
}

#[test]
fn cancel_between_steps_after_effect_is_uncertain() {
    let world = World::default();
    *world.fg.borrow_mut() = vec![
        Some(w("Notepad")),
        Some(w("Notepad")),
        Some(w("Notepad")),
        Some(w("#32770")),
    ];
    world.cancel_after_inputs.set(Some(3)); // after "O","i", ctrl+S
    let r = run(&save_proc(), &ports(&world), &binds("C:\\o\\x.txt"));
    assert_eq!(r.outcome, Outcome::Uncertain);
    assert_eq!(r.code.as_deref(), Some("cancelled"));
    assert_eq!(r.failed_step, Some(2));
}

#[test]
fn cancel_before_effect_is_cancelled() {
    let world = World::default();
    *world.fg.borrow_mut() = vec![Some(w("Notepad"))];
    world.cancel.cancel();
    let r = run(&save_proc(), &ports(&world), &binds("C:\\o\\x.txt"));
    assert_eq!(r.outcome, Outcome::Cancelled);
    assert!(inputs(&world).is_empty());
}

#[test]
fn geometry_drift_halts_click() {
    let world = World::default();
    let mut moved = w("Notepad");
    moved.rect.left = 40;
    *world.fg.borrow_mut() = vec![Some(moved)];
    let p = procedure(
        vec![step(
            0,
            "Notepad",
            Action::Click {
                button: MouseButton::Left,
                rel_x: 5,
                rel_y: 5,
                window_rect: RECT,
            },
            false,
        )],
        vec![],
    );
    let r = run(&p, &ports(&world), &opts0());
    assert_eq!(r.code.as_deref(), Some("window_geometry_mismatch"));
    assert!(inputs(&world).is_empty());
}

#[test]
fn higher_integrity_target_is_refused() {
    let world = World::default();
    *world.fg.borrow_mut() = vec![Some(w("Notepad"))];
    world.high_il.set(true);
    let r = run(&save_proc(), &ports(&world), &binds("C:\\o\\x.txt"));
    assert_eq!(r.code.as_deref(), Some("integrity_blocked"));
    assert_eq!(r.outcome, Outcome::Refused);
    assert!(inputs(&world).is_empty());
}

fn opts0() -> RunOptions {
    RunOptions {
        stable_ms: 0,
        output_wait_ms: 0,
        ..RunOptions::default()
    }
}

#[test]
fn new_surface_must_be_stable_before_first_input() {
    let world = World::default();
    // Flickers: match, lost, then steady.
    *world.fg.borrow_mut() = vec![Some(w("Notepad")), None, Some(w("Notepad"))];
    let p = procedure(
        vec![step(
            0,
            "Notepad",
            Action::Key {
                vk: 0x74,
                mods: Modifiers::default(),
            },
            false,
        )],
        vec![],
    );
    let opts = RunOptions {
        stable_ms: 300,
        poll_ms: 50,
        ..RunOptions::default()
    };
    let r = run(&p, &ports(&world), &opts);
    assert_eq!(r.outcome, Outcome::CompletedUnverified);
    assert!(
        r.steps[0].waited_ms >= 300,
        "waited {}",
        r.steps[0].waited_ms
    );
}

#[test]
fn cancel_between_characters_stops_typing() {
    let world = World::default();
    *world.fg.borrow_mut() = vec![Some(w("Notepad"))];
    world.cancel_after_inputs.set(Some(2));
    let p = procedure(
        vec![step(
            0,
            "Notepad",
            Action::TypeText {
                text: TextValue::Literal("abcdef".into()),
            },
            false,
        )],
        vec![],
    );
    let r = run(&p, &ports(&world), &opts0());
    assert_eq!(r.outcome, Outcome::Cancelled);
    assert_eq!(r.steps[0].delivery, Delivery::Partial);
    assert_eq!(inputs(&world).len(), 2);
}

#[test]
fn zero_accepted_input_is_not_attempted_and_failed() {
    let world = World::default();
    *world.fg.borrow_mut() = vec![Some(w("Notepad"))];
    world.reject_all_keys.set(true);
    let p = procedure(
        vec![step(
            0,
            "Notepad",
            Action::Key {
                vk: 0x0D,
                mods: Modifiers::default(),
            },
            true,
        )],
        vec![],
    );
    let r = run(&p, &ports(&world), &opts0());
    assert_eq!(r.steps[0].delivery, Delivery::NotAttempted);
    assert_eq!(
        r.outcome,
        Outcome::Failed,
        "nothing reached the target, so not uncertain"
    );
}

fn save_world() -> World {
    let world = World::default();
    *world.fg.borrow_mut() = vec![
        Some(w("Notepad")),
        Some(w("Notepad")),
        Some(w("Notepad")),
        Some(w("#32770")),
    ];
    world
}

#[test]
fn guarded_run_without_foreign_input_completes() {
    let world = save_world();
    let r = run(&save_proc(), &guarded(&world), &binds(r"C:\o\x.txt"));
    assert_eq!(r.outcome, Outcome::CompletedUnverified, "{:?}", r.code);
}

#[test]
fn unarmed_guard_refuses_before_any_input() {
    let world = save_world();
    world.guard_broken.set(true);
    let r = run(&save_proc(), &guarded(&world), &binds(r"C:\o\x.txt"));
    assert_eq!(r.outcome, Outcome::Refused);
    assert_eq!(r.code.as_deref(), Some("input_monitor_unavailable"));
    assert!(inputs(&world).is_empty());
}

#[test]
fn foreign_input_before_our_first_input_fails_without_input() {
    let world = save_world();
    world.foreign_after_inputs.set(Some(0));
    let r = run(&save_proc(), &guarded(&world), &binds(r"C:\o\x.txt"));
    assert_eq!(r.outcome, Outcome::Failed);
    assert_eq!(r.code.as_deref(), Some("user_input_detected"));
    assert!(inputs(&world).is_empty());
}

#[test]
fn foreign_input_while_typing_stops_as_uncertain_before_saving() {
    let world = save_world();
    world.foreign_after_inputs.set(Some(1));
    let r = run(&save_proc(), &guarded(&world), &binds(r"C:\o\x.txt"));
    assert_eq!(r.outcome, Outcome::Uncertain);
    assert_eq!(r.code.as_deref(), Some("user_input_detected"));
    assert_eq!(r.failed_step, Some(0));
    assert_eq!(r.steps[0].delivery, Delivery::Partial);
    assert_eq!(
        inputs(&world).join("|"),
        "char O",
        "no further input, no Ctrl+S"
    );
    assert!(world.released.get() >= 1);
}

#[test]
fn foreign_input_after_the_last_step_is_uncertain() {
    let world = save_world();
    world.foreign_after_inputs.set(Some(14));
    let r = run(&save_proc(), &guarded(&world), &binds(r"C:\o\x.txt"));
    assert_eq!(r.outcome, Outcome::Uncertain);
    assert_eq!(r.code.as_deref(), Some("user_input_detected"));
    assert_eq!(r.failed_step, Some(3));
}

fn bound(to: u64) -> RunOptions {
    RunOptions {
        bound_window: Some(to),
        ..binds(r"C:\o\x.txt")
    }
}

#[test]
fn bound_run_ignores_another_window_of_the_same_app() {
    // A restored Notepad window is in front; the run's own window is 1.
    let world = save_world();
    *world.roots.borrow_mut() = vec![Some(2)];
    let r = run(&save_proc(), &ports(&world), &bound(1));
    assert_eq!(r.outcome, Outcome::Failed);
    assert_eq!(r.code.as_deref(), Some("focus_timeout"));
    assert!(
        inputs(&world).is_empty(),
        "nothing typed into the other window"
    );
    assert!(world.log.borrow().iter().any(|l| l == "activate_window 1"));
}

#[test]
fn bound_run_accepts_its_window_and_the_dialog_it_owns() {
    let world = save_world(); // last surface is the Save As dialog (#32770)
    *world.roots.borrow_mut() = vec![Some(1)];
    let r = run(&save_proc(), &ports(&world), &bound(1));
    assert_eq!(r.outcome, Outcome::CompletedUnverified, "{:?}", r.code);
}

#[test]
fn bound_run_stops_typing_when_another_window_of_the_app_takes_focus() {
    let world = save_world();
    // First query: the step's wait; second: the check before the 2nd character.
    *world.roots.borrow_mut() = vec![Some(1), Some(2)];
    let r = run(&save_proc(), &ports(&world), &bound(1));
    assert_eq!(r.code.as_deref(), Some("focus_lost_during_input"));
    assert_eq!(r.failed_step, Some(0));
    assert_eq!(inputs(&world).join("|"), "char O", "no Ctrl+S");
}
