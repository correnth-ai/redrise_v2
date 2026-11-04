//! Executes a procedure through ports. Never retries an injected step; a
//! failure after an effectful step is `Uncertain`. Success here is only
//! `CompletedUnverified`: verification belongs to an independent reader.
use std::collections::BTreeMap;
use std::path::PathBuf;

use serde::Serialize;

use crate::ir::{Action, ParamRole, Procedure, Step, TextValue, WindowMatch, CATEGORY_BROWSER};
use crate::model::WindowRef;
use crate::ports::{
    url_origin, BrowserDriver, BrowserError, CancelToken, FileProbe, InjectError, InputInjector,
    InterferenceMonitor, Pacer, SessionProbe, WindowInspector,
};

/// Run report code when foreign input was seen during a native run.
pub const USER_INPUT_DETECTED: &str = "user_input_detected";

#[derive(Debug, Clone)]
pub struct RunOptions {
    pub bindings: BTreeMap<String, String>,
    pub step_timeout_ms: u64,
    pub poll_ms: u64,
    pub settle_ms: u64,
    pub char_delay_ms: u64,
    /// When a step targets a different surface than the previous one (or is
    /// the first), the surface must stay in the foreground this long before
    /// input: a just-shown window may not process input yet.
    pub stable_ms: u64,
    /// After a completed run, how long to wait for bound output files to
    /// appear (the application may write asynchronously). Observation only.
    pub output_wait_ms: u64,
    /// The top-level window the caller opened for this run. When set, a step's
    /// surface must be that window or a dialog it owns; another window of the
    /// same app (a restored session, a second document) is not the target.
    pub bound_window: Option<u64>,
}

impl Default for RunOptions {
    fn default() -> Self {
        Self {
            bindings: BTreeMap::new(),
            step_timeout_ms: 10_000,
            poll_ms: 50,
            settle_ms: 150,
            char_delay_ms: 25,
            stable_ms: 400,
            output_wait_ms: 10_000,
            bound_window: None,
        }
    }
}

pub struct Ports<'a> {
    pub windows: &'a dyn WindowInspector,
    pub input: &'a dyn InputInjector,
    pub session: &'a dyn SessionProbe,
    pub files: &'a dyn FileProbe,
    pub pacer: &'a dyn Pacer,
    pub cancel: CancelToken,
    /// Required for `browser` procedures; `None` for native-only runs.
    pub browser: Option<&'a dyn BrowserDriver>,
    /// Foreign-input guard for native steps. With it, a key or button press
    /// the Engine did not send stops the run: our input could interleave
    /// with someone else's (observed: garbled text in Notepad).
    pub interference: Option<&'a dyn InterferenceMonitor>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Outcome {
    /// Every step delivered; effects not yet verified independently.
    CompletedUnverified,
    Failed,
    Cancelled,
    /// A step that may persist an effect was delivered before the failure.
    Uncertain,
    /// Refused before any input was sent.
    Refused,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Delivery {
    NotAttempted,
    Delivered,
    Partial,
}

#[derive(Debug, Clone, Serialize)]
pub struct StepRecord {
    pub id: u32,
    pub delivery: Delivery,
    pub effectful: bool,
    pub waited_ms: u64,
    pub note: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ObservedOutput {
    pub param: String,
    pub path: String,
    pub exists_after_run: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct RunReport {
    pub outcome: Outcome,
    pub code: Option<String>,
    pub message: Option<String>,
    pub failed_step: Option<u32>,
    pub procedure_sha256: String,
    pub steps: Vec<StepRecord>,
    pub observed_outputs: Vec<ObservedOutput>,
    pub verified: bool,
    /// Browser procedures: page URL/title after the last step (observation
    /// for verifiers such as login-vs-inbox; never a success criterion here).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub browser_final: Option<BrowserFinal>,
}

#[derive(Debug, Clone, Serialize)]
pub struct BrowserFinal {
    pub url: String,
    pub title: String,
}

struct ReleaseGuard<'a>(&'a dyn InputInjector);
impl Drop for ReleaseGuard<'_> {
    fn drop(&mut self) {
        self.0.release_modifiers();
    }
}

type StepError = (Delivery, String, String);

/// One browser step: wait (bounded) until the page is on the recorded
/// origin (except for `goto`), then a single driver call. No retries.
fn browser_step(
    step: &Step,
    driver: &dyn BrowserDriver,
    ports: &Ports<'_>,
    opts: &RunOptions,
    waited: &mut u64,
    t0: u64,
) -> Result<(), StepError> {
    let to_err = |e: BrowserError| {
        let d = if e.partial {
            Delivery::Partial
        } else {
            Delivery::NotAttempted
        };
        (d, e.code, e.detail)
    };
    if !matches!(step.action, Action::BrowserGoto { .. }) {
        loop {
            let st = driver.state().map_err(to_err)?;
            if url_origin(&st.url) == step.expect.class {
                break;
            }
            if ports.cancel.is_cancelled() {
                return Err((
                    Delivery::NotAttempted,
                    "cancelled".into(),
                    "before step".into(),
                ));
            }
            if ports.pacer.now_ms().saturating_sub(t0) >= opts.step_timeout_ms {
                return Err((
                    Delivery::NotAttempted,
                    "origin_mismatch".into(),
                    format!("expected {}, page is on {}", step.expect.class, st.url),
                ));
            }
            ports.pacer.sleep_ms(opts.poll_ms);
        }
    }
    *waited = ports.pacer.now_ms().saturating_sub(t0);
    let r = match &step.action {
        Action::BrowserGoto { url } => driver.goto(url),
        Action::BrowserClick { selector } => driver.click(selector),
        Action::BrowserFill { selector, text } => {
            let v = match text {
                TextValue::Literal(t) => t.clone(),
                TextValue::Param(n) => opts.bindings[n].clone(),
            };
            driver.fill(selector, &v)
        }
        Action::BrowserPress { selector, key } => driver.press(selector, key),
        _ => unreachable!("browser actions only"),
    };
    r.map_err(to_err)
}

/// What an injection error says about delivery: nothing accepted means the
/// input never reached the target; anything else may have partially arrived.
fn delivery_of(e: &InjectError) -> Delivery {
    match e {
        InjectError::Partial { accepted: 0, .. } => Delivery::NotAttempted,
        _ => Delivery::Partial,
    }
}

fn matches(w: &WindowRef, m: &WindowMatch) -> bool {
    w.process_image == m.process_image && w.class == m.class
}

fn on_target(ports: &Ports<'_>, opts: &RunOptions, w: &WindowRef, m: &WindowMatch) -> bool {
    matches(w, m)
        && opts
            .bound_window
            .is_none_or(|b| ports.windows.foreground_root() == Some(b))
}

fn interfered(ports: &Ports<'_>) -> Option<String> {
    ports.interference.and_then(|m| m.observed())
}

/// Foreign input stops the run: `Uncertain` once any of our input reached
/// the desktop (the two streams may have mixed), `Failed` otherwise.
fn mark_interference(r: &mut RunReport) {
    r.outcome = if r.steps.iter().any(|s| s.delivery != Delivery::NotAttempted) {
        Outcome::Uncertain
    } else {
        Outcome::Failed
    };
}

pub fn run(proc: &Procedure, ports: &Ports<'_>, opts: &RunOptions) -> RunReport {
    let mut report = RunReport {
        outcome: Outcome::CompletedUnverified,
        code: None,
        message: None,
        failed_step: None,
        procedure_sha256: proc.sha256(),
        steps: proc
            .steps
            .iter()
            .map(|s| StepRecord {
                id: s.id,
                delivery: Delivery::NotAttempted,
                effectful: s.effectful,
                waited_ms: 0,
                note: None,
            })
            .collect(),
        observed_outputs: Vec::new(),
        verified: false,
        browser_final: None,
    };
    let refuse = |mut r: RunReport, code: &str, msg: String| {
        r.outcome = Outcome::Refused;
        r.code = Some(code.into());
        r.message = Some(msg);
        r
    };

    // ---- readiness, before any input
    if let Err(e) = proc.validate() {
        return refuse(report, "invalid_procedure", format!("{e:?}"));
    }
    let ready = ports.session.readiness();
    if ready.platform != proc.platform {
        return refuse(
            report,
            "platform_mismatch",
            format!("runner {} vs procedure {}", ready.platform, proc.platform),
        );
    }
    if !ready.interactive_desktop {
        return refuse(report, "session_unavailable", ready.detail.join("; "));
    }
    if let Some(m) = ports.interference {
        if let Err(e) = m.ready() {
            return refuse(report, "input_monitor_unavailable", e);
        }
    }
    // ---- bindings
    for k in opts.bindings.keys() {
        if !proc.params.iter().any(|p| &p.name == k) {
            return refuse(
                report,
                "unknown_binding",
                format!("binding '{k}' is not a procedure param"),
            );
        }
    }
    let mut outputs: Vec<(String, PathBuf)> = Vec::new();
    for p in &proc.params {
        let Some(v) = opts.bindings.get(&p.name) else {
            return refuse(
                report,
                "missing_binding",
                format!("param '{}' requires a binding", p.name),
            );
        };
        if p.role == ParamRole::OutputPath {
            let path = PathBuf::from(v);
            if !path.is_absolute() {
                return refuse(report, "output_path_not_absolute", v.clone());
            }
            if ports.files.exists(&path) {
                return refuse(
                    report,
                    "output_exists",
                    format!("{v} already exists; refusing to overwrite"),
                );
            }
            if !ports.files.parent_exists(&path) {
                return refuse(report, "output_parent_missing", v.clone());
            }
            outputs.push((p.name.clone(), path));
        }
    }

    if proc.category == CATEGORY_BROWSER && ports.browser.is_none() {
        return refuse(
            report,
            "browser_adapter_unavailable",
            "browser procedure without a browser driver".into(),
        );
    }

    let _guard = ReleaseGuard(ports.input);
    let mut effect_crossed = false;
    let fail = |r: &mut RunReport, step: u32, code: &str, msg: String, crossed: bool| {
        r.outcome = if crossed {
            Outcome::Uncertain
        } else {
            Outcome::Failed
        };
        r.code = Some(code.into());
        r.message = Some(msg);
        r.failed_step = Some(step);
    };

    for (i, step) in proc.steps.iter().enumerate() {
        if ports.cancel.is_cancelled() {
            report.outcome = if effect_crossed {
                Outcome::Uncertain
            } else {
                Outcome::Cancelled
            };
            report.code = Some("cancelled".into());
            report.failed_step = Some(step.id);
            break;
        }
        if step.action.is_browser() {
            let driver = ports.browser.expect("checked before the loop");
            let t0 = ports.pacer.now_ms();
            let result = browser_step(
                step,
                driver,
                ports,
                opts,
                &mut report.steps[i].waited_ms,
                t0,
            );
            match result {
                Ok(()) => {
                    report.steps[i].delivery = Delivery::Delivered;
                    if step.effectful {
                        effect_crossed = true;
                    }
                    ports.pacer.sleep_ms(opts.settle_ms);
                    continue;
                }
                Err((delivery, code, msg)) => {
                    report.steps[i].delivery = delivery;
                    let crossed =
                        effect_crossed || (step.effectful && delivery != Delivery::NotAttempted);
                    fail(&mut report, step.id, &code, msg, crossed);
                    break;
                }
            }
        }
        // ---- wait for the expected surface (bounded, sleeping poll)
        let t0 = ports.pacer.now_ms();
        let mut activated = false;
        let needs_stability = i == 0 || proc.steps[i - 1].expect != step.expect;
        let mut stable_since: Option<u64> = None;
        let fg = loop {
            match ports.windows.foreground() {
                Some(w) if on_target(ports, opts, &w, &step.expect) => {
                    let now = ports.pacer.now_ms();
                    let since = *stable_since.get_or_insert(now);
                    if !needs_stability || now.saturating_sub(since) >= opts.stable_ms {
                        break Some(w);
                    }
                }
                _ => {
                    stable_since = None;
                    // Only when the target is not in front: activating the root of a
                    // bound run would take the focus from the dialog it owns.
                    if i == 0 && !activated {
                        activated = true;
                        match opts.bound_window {
                            Some(b) => ports.windows.activate_window(b),
                            None => ports
                                .windows
                                .activate(&step.expect.process_image, &step.expect.class),
                        };
                    }
                }
            }
            if ports.cancel.is_cancelled()
                || ports.pacer.now_ms().saturating_sub(t0) >= opts.step_timeout_ms
            {
                break None;
            }
            ports.pacer.sleep_ms(opts.poll_ms);
        };
        report.steps[i].waited_ms = ports.pacer.now_ms().saturating_sub(t0);
        let Some(fg) = fg else {
            if ports.cancel.is_cancelled() {
                report.outcome = if effect_crossed {
                    Outcome::Uncertain
                } else {
                    Outcome::Cancelled
                };
                report.code = Some("cancelled".into());
                report.failed_step = Some(step.id);
            } else {
                fail(
                    &mut report,
                    step.id,
                    "focus_timeout",
                    match opts.bound_window {
                        Some(b) => format!(
                            "expected {}/{} of window {b} in foreground",
                            step.expect.process_image, step.expect.class
                        ),
                        None => format!(
                            "expected {}/{} in foreground",
                            step.expect.process_image, step.expect.class
                        ),
                    },
                    effect_crossed,
                );
            }
            break;
        };
        if ports.session.can_drive_process(fg.pid) == Some(false) {
            fail(
                &mut report,
                step.id,
                "integrity_blocked",
                "target runs at higher integrity (UIPI)".into(),
                effect_crossed,
            );
            if report
                .steps
                .iter()
                .all(|s| s.delivery == Delivery::NotAttempted)
            {
                report.outcome = Outcome::Refused; // no input was ever sent
            }
            break;
        }
        if let Some(what) = interfered(ports) {
            fail(
                &mut report,
                step.id,
                USER_INPUT_DETECTED,
                what,
                effect_crossed,
            );
            mark_interference(&mut report);
            break;
        }

        // ---- act (single attempt)
        let result: Result<(), (Delivery, String, String)> = match &step.action {
            Action::Click {
                button,
                rel_x,
                rel_y,
                window_rect,
            } => {
                if fg.rect != *window_rect {
                    Err((
                        Delivery::NotAttempted,
                        "window_geometry_mismatch".into(),
                        format!("recorded {window_rect:?}, now {:?}", fg.rect),
                    ))
                } else {
                    ports
                        .input
                        .click(*button, fg.rect.left + rel_x, fg.rect.top + rel_y)
                        .map_err(|e| (delivery_of(&e), "inject_failed".into(), format!("{e:?}")))
                }
            }
            Action::Key { vk, mods } => ports
                .input
                .key(*vk, *mods)
                .map_err(|e| (delivery_of(&e), "inject_failed".into(), format!("{e:?}"))),
            Action::TypeText { text } => {
                let s = match text {
                    TextValue::Literal(t) => t.clone(),
                    TextValue::Param(n) => opts.bindings[n].clone(),
                };
                let mut res = Ok(());
                for (sent, ch) in s.chars().enumerate() {
                    let so_far = if sent == 0 {
                        Delivery::NotAttempted
                    } else {
                        Delivery::Partial
                    };
                    if ports.cancel.is_cancelled() {
                        res = Err((so_far, "cancelled".into(), format!("after {sent} chars")));
                        break;
                    }
                    if let Some(what) = interfered(ports) {
                        res = Err((
                            so_far,
                            USER_INPUT_DETECTED.into(),
                            format!("{what} after {sent} chars"),
                        ));
                        break;
                    }
                    if sent > 0 {
                        match ports.windows.foreground() {
                            Some(w) if on_target(ports, opts, &w, &step.expect) => {}
                            _ => {
                                res = Err((
                                    Delivery::Partial,
                                    "focus_lost_during_input".into(),
                                    format!("after {sent} chars"),
                                ));
                                break;
                            }
                        }
                    }
                    if let Err(e) = ports.input.type_char(ch) {
                        let d = if sent == 0 {
                            delivery_of(&e)
                        } else {
                            Delivery::Partial
                        };
                        res = Err((d, "inject_failed".into(), format!("{e:?}")));
                        break;
                    }
                    ports.pacer.sleep_ms(opts.char_delay_ms);
                }
                res
            }
            _ => unreachable!("browser steps are handled above"),
        };
        match result {
            Ok(()) => {
                report.steps[i].delivery = Delivery::Delivered;
                if step.effectful {
                    effect_crossed = true;
                }
                ports.pacer.sleep_ms(opts.settle_ms);
            }
            Err((delivery, code, msg)) => {
                report.steps[i].delivery = delivery;
                let crossed =
                    effect_crossed || (step.effectful && delivery != Delivery::NotAttempted);
                fail(&mut report, step.id, &code, msg, crossed);
                if code == "cancelled" && !crossed {
                    report.outcome = Outcome::Cancelled;
                }
                if code == USER_INPUT_DETECTED {
                    mark_interference(&mut report);
                }
                break;
            }
        }
    }
    // Foreign input during the last step's settle may still have reached the
    // surface after our final input.
    if report.outcome == Outcome::CompletedUnverified {
        if let Some(what) = interfered(ports) {
            let last = proc.steps.last().map(|s| s.id).unwrap_or(0);
            fail(&mut report, last, USER_INPUT_DETECTED, what, true);
            mark_interference(&mut report);
        }
    }

    if report.outcome == Outcome::CompletedUnverified && !outputs.is_empty() {
        let t0 = ports.pacer.now_ms();
        while !outputs.iter().all(|(_, p)| ports.files.exists(p))
            && ports.pacer.now_ms().saturating_sub(t0) < opts.output_wait_ms
        {
            ports.pacer.sleep_ms(opts.poll_ms.max(1));
        }
    }
    if let Some(driver) = ports.browser {
        if let Ok(st) = driver.state() {
            report.browser_final = Some(BrowserFinal {
                url: st.url,
                title: st.title,
            });
        }
    }
    for (param, path) in outputs {
        report.observed_outputs.push(ObservedOutput {
            exists_after_run: ports.files.exists(&path),
            param,
            path: path.display().to_string(),
        });
    }
    report
}
