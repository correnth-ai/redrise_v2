//! P03 browser regressions: compiler and executor with a fake driver.
//! Fakes model the adapter contract; native proof is separate.
use std::cell::{Cell, RefCell};
use std::collections::BTreeMap;
use std::path::Path;

use engine_core::compile::{compile, ParamDecl};
use engine_core::execute::{run, Delivery, Outcome, Ports, RunOptions};
use engine_core::ir::{Action, ParamRole, Procedure, TextValue};
use engine_core::model::{MouseButton, RawEvent, RawKind, Rect, WindowRef, BROWSER_SURFACE};
use engine_core::ports::{
    url_origin, BrowserDriver, BrowserError, BrowserState, CancelToken, FileProbe, InjectError,
    InputInjector, Modifiers, Pacer, Readiness, SessionProbe, WindowInspector,
};
use engine_core::recording::{Manifest, RecordingStatus};

const ORIGIN: &str = "http://127.0.0.1:47321";

fn ev(seq: u64, kind: RawKind) -> RawEvent {
    RawEvent {
        seq,
        t_us: seq,
        kind,
        window: WindowRef {
            pid: 1,
            process_image: BROWSER_SURFACE.into(),
            class: ORIGIN.into(),
            title: "Pedido".into(),
            rect: Rect::default(),
        },
    }
}

fn manifest() -> Manifest {
    Manifest {
        format: 1,
        recording_id: "b1".into(),
        status: RecordingStatus::Complete,
        reason: None,
        platform: "windows-x86_64".into(),
        target_process: BROWSER_SURFACE.into(),
        input_origin: "injected-accepted".into(),
        event_count: 0,
        events_sha256: "00".into(),
        dropped: 0,
        source: Default::default(),
        started_at_unix_ms: 0,
        duration_ms: 0,
        engine_version: "test".into(),
    }
}

fn recording() -> Vec<RawEvent> {
    let fill = |s: &str, v: &str| RawKind::BrowserFill {
        selector: s.into(),
        value: v.into(),
    };
    vec![
        ev(
            0,
            RawKind::BrowserGoto {
                url: format!("{ORIGIN}/"),
            },
        ),
        ev(1, fill("#cliente", "Cliente Teste 01")),
        ev(2, fill("#valor", "1500")),
        ev(3, fill("#valor", "1500")), // duplicate commit (Enter then change)
        ev(
            4,
            RawKind::BrowserClick {
                selector: "[data-testid=\"salvar\"]".into(),
            },
        ),
    ]
}

#[test]
fn compiles_browser_recording_to_ir_v2() {
    let p = compile(&manifest(), &recording(), &[]).unwrap();
    assert_eq!((p.ir_version, p.category.as_str()), (2, "browser"));
    assert_eq!(p.steps.len(), 4, "duplicate fill collapsed");
    assert!(p.steps[3].effectful && !p.steps[1].effectful);
    assert_eq!(p.steps[0].expect.class, ORIGIN);
    let back = Procedure::from_json(&p.to_canonical_json()).unwrap();
    assert_eq!(back, p);
}

#[test]
fn browser_param_on_fill_value() {
    let decl = ParamDecl {
        name: "cliente".into(),
        role: ParamRole::Text,
        literal: "Cliente Teste 01".into(),
    };
    let p = compile(&manifest(), &recording(), &[decl]).unwrap();
    assert!(
        matches!(&p.steps[1].action, Action::BrowserFill { text: TextValue::Param(n), .. } if n == "cliente")
    );
}

#[test]
fn browser_recording_refusals() {
    let mut evs = recording();
    evs.remove(0);
    for (i, e) in evs.iter_mut().enumerate() {
        e.seq = i as u64;
    }
    assert!(compile(&manifest(), &evs, &[])
        .unwrap_err()
        .iter()
        .any(|d| d.code == "browser_no_start_url"));
    let mut evs = recording();
    evs.push(ev(
        5,
        RawKind::BrowserUnsupported {
            reason: "password fields are not recorded".into(),
        },
    ));
    evs.push(ev(
        6,
        RawKind::Mouse {
            button: MouseButton::Left,
            down: true,
            x: 0,
            y: 0,
        },
    ));
    let codes: Vec<&str> = compile(&manifest(), &evs, &[])
        .unwrap_err()
        .iter()
        .map(|d| d.code)
        .collect();
    assert_eq!(codes, vec!["browser_unsupported", "mixed_surface"]);
}

#[test]
fn ir_rejects_mixed_category_and_non_http_goto() {
    let p = compile(&manifest(), &recording(), &[]).unwrap();
    let mut v: serde_json::Value = serde_json::from_slice(&p.to_canonical_json()).unwrap();
    v["category"] = "windows".into();
    assert!(Procedure::from_json(v.to_string().as_bytes()).is_err());
    let mut v: serde_json::Value = serde_json::from_slice(&p.to_canonical_json()).unwrap();
    v["steps"][0]["action"]["url"] = "file:///C:/Windows/win.ini".into();
    assert!(Procedure::from_json(v.to_string().as_bytes()).is_err());
}

#[test]
fn origin_is_scheme_host_port() {
    assert_eq!(url_origin("http://127.0.0.1:47321/save?x=1"), ORIGIN);
    assert_eq!(url_origin("https://example.test"), "https://example.test");
}

// ---------------------------------------------------------------- executor

#[derive(Default)]
struct FakeBrowser {
    url: RefCell<String>,
    log: RefCell<Vec<String>>,
    fail: RefCell<Option<(String, BrowserError)>>,
    stuck_on: RefCell<Option<String>>,
}

impl FakeBrowser {
    fn act(&self, what: String) -> Result<(), BrowserError> {
        if let Some((prefix, e)) = self.fail.borrow().as_ref() {
            if what.starts_with(prefix.as_str()) {
                return Err(e.clone());
            }
        }
        self.log.borrow_mut().push(what);
        Ok(())
    }
}

impl BrowserDriver for FakeBrowser {
    fn state(&self) -> Result<BrowserState, BrowserError> {
        let url = self
            .stuck_on
            .borrow()
            .clone()
            .unwrap_or_else(|| self.url.borrow().clone());
        Ok(BrowserState {
            url,
            title: "t".into(),
        })
    }
    fn goto(&self, url: &str) -> Result<(), BrowserError> {
        *self.url.borrow_mut() = url.into();
        self.act(format!("goto {url}"))
    }
    fn click(&self, s: &str) -> Result<(), BrowserError> {
        self.act(format!("click {s}"))
    }
    fn fill(&self, s: &str, v: &str) -> Result<(), BrowserError> {
        self.act(format!("fill {s}={v}"))
    }
    fn press(&self, s: &str, k: &str) -> Result<(), BrowserError> {
        self.act(format!("press {s} {k}"))
    }
}

#[derive(Default)]
struct Native {
    now: Cell<u64>,
    locked: Cell<bool>,
    cancel: CancelToken,
}
impl WindowInspector for Native {
    fn foreground(&self) -> Option<WindowRef> {
        None
    }
    fn activate(&self, _: &str, _: &str) -> bool {
        false
    }
}
impl InputInjector for Native {
    fn click(&self, _: MouseButton, _: i32, _: i32) -> Result<(), InjectError> {
        panic!("native input must not be used for browser steps")
    }
    fn key(&self, _: u16, _: Modifiers) -> Result<(), InjectError> {
        panic!("native input must not be used for browser steps")
    }
    fn type_char(&self, _: char) -> Result<(), InjectError> {
        panic!("native input must not be used for browser steps")
    }
    fn release_modifiers(&self) {}
}
impl SessionProbe for Native {
    fn readiness(&self) -> Readiness {
        Readiness {
            platform: "windows-x86_64".into(),
            interactive_desktop: !self.locked.get(),
            detail: vec![],
        }
    }
    fn can_drive_process(&self, _: u32) -> Option<bool> {
        Some(true)
    }
}
impl FileProbe for Native {
    fn exists(&self, _: &Path) -> bool {
        false
    }
    fn parent_exists(&self, _: &Path) -> bool {
        true
    }
}
impl Pacer for Native {
    fn sleep_ms(&self, ms: u64) {
        self.now.set(self.now.get() + ms);
    }
    fn now_ms(&self) -> u64 {
        self.now.get()
    }
}

fn go(n: &Native, b: Option<&FakeBrowser>, p: &Procedure) -> engine_core::execute::RunReport {
    let ports = Ports {
        windows: n,
        input: n,
        session: n,
        files: n,
        pacer: n,
        cancel: n.cancel.clone(),
        browser: b.map(|x| x as &dyn BrowserDriver),
        interference: None,
    };
    run(
        p,
        &ports,
        &RunOptions {
            stable_ms: 0,
            output_wait_ms: 0,
            bindings: BTreeMap::new(),
            ..RunOptions::default()
        },
    )
}

#[test]
fn browser_happy_path_uses_driver_only() {
    let p = compile(&manifest(), &recording(), &[]).unwrap();
    let (n, b) = (Native::default(), FakeBrowser::default());
    let r = go(&n, Some(&b), &p);
    assert_eq!(r.outcome, Outcome::CompletedUnverified, "{:?}", r.code);
    assert_eq!(
        b.log.borrow().join("|"),
        format!("goto {ORIGIN}/|fill #cliente=Cliente Teste 01|fill #valor=1500|click [data-testid=\"salvar\"]")
    );
}

#[test]
fn missing_driver_and_locked_session_refuse() {
    let p = compile(&manifest(), &recording(), &[]).unwrap();
    let n = Native::default();
    assert_eq!(
        go(&n, None, &p).code.as_deref(),
        Some("browser_adapter_unavailable")
    );
    n.locked.set(true);
    let b = FakeBrowser::default();
    assert_eq!(go(&n, Some(&b), &p).outcome, Outcome::Refused);
    assert!(b.log.borrow().is_empty());
}

#[test]
fn wrong_origin_times_out_without_action() {
    let p = compile(&manifest(), &recording(), &[]).unwrap();
    let (n, b) = (Native::default(), FakeBrowser::default());
    *b.stuck_on.borrow_mut() = Some("https://other.test/".into());
    let r = go(&n, Some(&b), &p);
    assert_eq!(
        (r.outcome, r.code.as_deref(), r.failed_step),
        (Outcome::Failed, Some("origin_mismatch"), Some(1))
    );
    assert_eq!(b.log.borrow().len(), 1, "only the goto ran");
}

#[test]
fn missing_selector_before_submit_is_failed_and_after_partial_submit_is_uncertain() {
    let p = compile(&manifest(), &recording(), &[]).unwrap();
    let (n, b) = (Native::default(), FakeBrowser::default());
    *b.fail.borrow_mut() = Some((
        "fill #valor".into(),
        BrowserError {
            code: "selector_not_found".into(),
            detail: String::new(),
            partial: false,
        },
    ));
    let r = go(&n, Some(&b), &p);
    assert_eq!(
        (r.outcome, r.steps[2].delivery),
        (Outcome::Failed, Delivery::NotAttempted)
    );

    let (n, b) = (Native::default(), FakeBrowser::default());
    *b.fail.borrow_mut() = Some((
        "click".into(),
        BrowserError {
            code: "browser_error".into(),
            detail: String::new(),
            partial: true,
        },
    ));
    let r = go(&n, Some(&b), &p);
    assert_eq!(
        r.outcome,
        Outcome::Uncertain,
        "a click that may have submitted is uncertain"
    );
}
