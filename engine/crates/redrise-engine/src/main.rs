//! `redrise-engine` — composition root of the RedRise Engine.
//!
//! Commands (JSON on stdout; stdin lines `stop`/`cancel` control long runs):
//!   readiness [--probe-hooks] [--pid N]
//!   record --target <image> --out <dir> [--max-seconds N] [--deadline-ms N]
//!          [--accept-injected] [--stop-file <path>] [--no-probe]
//!   compile --recording <dir> --out <procedure.json> [--param name=role:literal]...
//!   run --procedure <file> --report <run.json> [--bind name=value]... [--step-timeout-ms N]
//!       [--stop-file <path>]
//! Exit codes: 0 ok, 1 usage/io, 2 refused, 3 failed, 4 uncertain, 5 cancelled,
//! 6 recording not complete, 7 compile diagnostics.
use std::collections::BTreeMap;
use std::io::BufRead;
use std::path::PathBuf;
use std::process::ExitCode;
use std::sync::mpsc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use engine_browser::{AdapterCommand, BrowserInputSource, ChildBrowserDriver};
use engine_core::capture::{run_capture, CaptureOptions, Control};
use engine_core::compile::{compile, ParamDecl};
use engine_core::execute::{self, Outcome, Ports, RunOptions};
use engine_core::ir::CATEGORY_BROWSER;
use engine_core::ir::{ParamRole, Procedure};
use engine_core::model::BROWSER_SURFACE;
use engine_core::ports::{BrowserDriver, InputSource, InterferenceMonitor};
use engine_core::ports::{CancelToken, SessionProbe};
use engine_core::recording::{self, write_json_atomic, FsRecordingWriter, RecordingStatus};
use engine_core::PLATFORM_WINDOWS_X64;
use engine_win::{
    init_dpi_awareness, probe_hooks, StdFiles, StdPacer, WinInjector, WinInputGuard,
    WinInputSource, WinSession, WinWindows,
};
use serde_json::json;

struct Args {
    flags: BTreeMap<String, Vec<String>>,
}

impl Args {
    fn parse(raw: &[String]) -> Result<Self, String> {
        let mut flags: BTreeMap<String, Vec<String>> = BTreeMap::new();
        let mut i = 0;
        while i < raw.len() {
            let k = raw[i]
                .strip_prefix("--")
                .ok_or_else(|| format!("unexpected argument {}", raw[i]))?;
            let boolean = matches!(k, "probe-hooks" | "accept-injected" | "no-probe");
            if boolean {
                flags.entry(k.into()).or_default().push("true".into());
                i += 1;
            } else {
                let v = raw
                    .get(i + 1)
                    .ok_or_else(|| format!("--{k} needs a value"))?;
                flags.entry(k.into()).or_default().push(v.clone());
                i += 2;
            }
        }
        Ok(Self { flags })
    }
    fn one(&self, k: &str) -> Option<&str> {
        self.flags.get(k).and_then(|v| v.last()).map(String::as_str)
    }
    fn req(&self, k: &str) -> Result<&str, String> {
        self.one(k).ok_or_else(|| format!("--{k} is required"))
    }
    fn all(&self, k: &str) -> Vec<String> {
        self.flags.get(k).cloned().unwrap_or_default()
    }
    fn has(&self, k: &str) -> bool {
        self.flags.contains_key(k)
    }
    fn num(&self, k: &str, default: u64) -> Result<u64, String> {
        self.one(k)
            .map(|v| v.parse().map_err(|_| format!("--{k} must be a number")))
            .unwrap_or(Ok(default))
    }
}

fn print(v: serde_json::Value) {
    println!("{}", serde_json::to_string_pretty(&v).unwrap());
}

/// Control lines from stdin and an optional stop file feed one channel.
fn control_channel(stop_file: Option<PathBuf>) -> mpsc::Receiver<Control> {
    let (tx, rx) = mpsc::channel();
    let tx2 = tx.clone();
    std::thread::spawn(move || {
        for line in std::io::stdin().lock().lines() {
            match line.map(|l| l.trim().to_lowercase()).as_deref() {
                Ok("stop") => {
                    let _ = tx.send(Control::Stop);
                }
                Ok("cancel") => {
                    let _ = tx.send(Control::Cancel);
                }
                Ok(_) => {}
                Err(_) => break,
            }
        }
        // stdin EOF is not a stop signal (the engine may be detached).
        std::mem::forget(tx);
    });
    if let Some(p) = stop_file {
        std::thread::spawn(move || loop {
            if p.exists() {
                let content = std::fs::read_to_string(&p).unwrap_or_default();
                let c = if content.trim().eq_ignore_ascii_case("cancel") {
                    Control::Cancel
                } else {
                    Control::Stop
                };
                let _ = tx2.send(c);
                break;
            }
            std::thread::sleep(Duration::from_millis(100));
        });
    }
    rx
}

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

fn cmd_readiness(a: &Args) -> Result<ExitCode, String> {
    let r = WinSession.readiness();
    let mut v = json!({ "readiness": r });
    if let Some(pid) = a.one("pid") {
        let pid: u32 = pid.parse().map_err(|_| "--pid must be a number")?;
        v["can_drive_pid"] = json!(WinSession.can_drive_process(pid));
    }
    let mut ok = r.interactive_desktop;
    if a.has("probe-hooks") {
        match probe_hooks(Duration::from_millis(500)) {
            Ok(ms) => v["hooks"] = json!({"status": "ok", "latency_ms": ms}),
            Err(e) => {
                ok = false;
                v["hooks"] = json!({"status": "unavailable", "error": e});
            }
        }
    }
    v["ready"] = json!(ok);
    print(v);
    Ok(if ok {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(2)
    })
}

/// `<install>` = parent of the `engine` folder holding this executable,
/// unless `--install-root` is given (development layouts).
fn install_root(a: &Args) -> PathBuf {
    a.one("install-root").map(PathBuf::from).unwrap_or_else(|| {
        std::env::current_exe()
            .ok()
            .and_then(|p| p.parent().and_then(|d| d.parent()).map(PathBuf::from))
            .unwrap_or_default()
    })
}

fn sibling(p: &std::path::Path, suffix: &str) -> PathBuf {
    let mut s = p.as_os_str().to_owned();
    s.push(suffix);
    PathBuf::from(s)
}

fn cmd_record(a: &Args) -> Result<ExitCode, String> {
    let browser = a.one("category") == Some("browser");
    let target = if browser {
        BROWSER_SURFACE.to_string()
    } else {
        a.req("target")?.to_lowercase()
    };
    let out = PathBuf::from(a.req("out")?);
    let ready = WinSession.readiness();
    if !ready.interactive_desktop {
        print(json!({"status": "refused", "code": "session_unavailable", "detail": ready.detail}));
        return Ok(ExitCode::from(2));
    }
    if !browser && !a.has("no-probe") {
        if let Err(e) = probe_hooks(Duration::from_millis(500)) {
            print(json!({"status": "refused", "code": "hooks_unavailable", "detail": e}));
            return Ok(ExitCode::from(2));
        }
    }
    let writer =
        FsRecordingWriter::create(&out).map_err(|e| format!("cannot create recording dir: {e}"))?;
    let accept = a.has("accept-injected");
    let opts = CaptureOptions {
        recording_id: out
            .file_name()
            .map(|s| s.to_string_lossy().into_owned())
            .unwrap_or_else(|| "recording".into()),
        platform: PLATFORM_WINDOWS_X64.into(),
        target_process: target.clone(),
        input_origin: if browser {
            "dom-trusted-events".into()
        } else if accept {
            "injected-accepted".into()
        } else {
            "hardware-only".into()
        },
        channel_capacity: 4096,
        max_duration: Duration::from_secs(a.num("max-seconds", 300)?),
        // Browser shutdown (Chromium) is slower than native hooks.
        finalize_deadline: Duration::from_millis(
            a.num("deadline-ms", if browser { 20_000 } else { 5_000 })?,
        ),
        started_at_unix_ms: now_ms(),
    };
    let control = control_channel(a.one("stop-file").map(PathBuf::from));
    eprintln!("recording {target}; send 'stop' or 'cancel' on stdin");
    let source: Box<dyn InputSource> = if browser {
        Box::new(BrowserInputSource {
            cmd: AdapterCommand::for_install(&install_root(a)),
            url: a.req("url")?.to_string(),
            profile: sibling(&out, ".profile"),
        })
    } else {
        Box::new(WinInputSource {
            target_process: target,
            accept_injected: accept,
        })
    };
    let outcome = run_capture(source, Box::new(writer), control, &opts);
    print(json!({
        "status": outcome.status,
        "reason": outcome.reason,
        "finalize_ms": outcome.finalize_ms,
        "manifest": outcome.manifest,
    }));
    Ok(if outcome.status == RecordingStatus::Complete {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(6)
    })
}

fn parse_param(s: &str) -> Result<ParamDecl, String> {
    let (name, rest) = s.split_once('=').ok_or("param must be name=role:literal")?;
    let (role, literal) = rest
        .split_once(':')
        .ok_or("param must be name=role:literal")?;
    let role = match role {
        "output_path" => ParamRole::OutputPath,
        "text" => ParamRole::Text,
        r => return Err(format!("unknown param role {r}")),
    };
    Ok(ParamDecl {
        name: name.into(),
        role,
        literal: literal.into(),
    })
}

fn cmd_compile(a: &Args) -> Result<ExitCode, String> {
    let dir = PathBuf::from(a.req("recording")?);
    let out = PathBuf::from(a.req("out")?);
    if out.exists() {
        return Err(format!("{} exists; refusing to overwrite", out.display()));
    }
    let (manifest, events) = match recording::load(&dir) {
        Ok(x) => x,
        Err(e) => {
            print(
                json!({"status": "refused", "code": "recording_not_loadable", "detail": format!("{e:?}")}),
            );
            return Ok(ExitCode::from(6));
        }
    };
    let params = a
        .all("param")
        .iter()
        .map(|p| parse_param(p))
        .collect::<Result<Vec<_>, _>>()?;
    // `--declare name=role`: a parameter no step types, e.g. the full
    // `output_path` guarding collisions while the Save As dialog receives the
    // folder and the bare file name as separate parameters.
    let mut declared = Vec::new();
    for d in a.all("declare") {
        let (name, role) = d.split_once('=').ok_or("declare must be name=role")?;
        let role = match role {
            "output_path" => ParamRole::OutputPath,
            "text" => ParamRole::Text,
            r => return Err(format!("unknown param role {r}")),
        };
        declared.push(engine_core::ir::ParamSpec {
            name: name.into(),
            role,
        });
    }
    match compile(&manifest, &events, &params) {
        Ok(mut p) => {
            for d in declared {
                if p.params.iter().any(|x| x.name == d.name) {
                    return Err(format!("param {} declared twice", d.name));
                }
                p.params.push(d);
            }
            p.validate().map_err(|e| format!("{e:?}"))?;
            std::fs::write(&out, p.to_canonical_json()).map_err(|e| e.to_string())?;
            print(
                json!({"status": "compiled", "procedure": out, "procedure_sha256": p.sha256(), "steps": p.steps.len(), "events_sha256": manifest.events_sha256}),
            );
            Ok(ExitCode::SUCCESS)
        }
        Err(d) => {
            print(json!({"status": "diagnostics", "diagnostics": d}));
            Ok(ExitCode::from(7))
        }
    }
}

fn cmd_run(a: &Args) -> Result<ExitCode, String> {
    let proc =
        Procedure::from_json(&std::fs::read(a.req("procedure")?).map_err(|e| e.to_string())?)
            .map_err(|e| format!("{e:?}"))?;
    let report_path = PathBuf::from(a.req("report")?);
    if report_path.exists() {
        return Err(format!(
            "{} exists; refusing to overwrite",
            report_path.display()
        ));
    }
    let mut bindings = BTreeMap::new();
    for b in a.all("bind") {
        let (k, v) = b.split_once('=').ok_or("bind must be name=value")?;
        bindings.insert(k.to_string(), v.to_string());
    }
    let cancel = CancelToken::default();
    let control = control_channel(a.one("stop-file").map(PathBuf::from));
    let c2 = cancel.clone();
    std::thread::spawn(move || {
        while let Ok(c) = control.recv() {
            if matches!(c, Control::Cancel | Control::Stop) {
                c2.cancel();
            }
        }
    });
    let pacer = StdPacer::default();
    let driver = if proc.category == CATEGORY_BROWSER {
        let d = ChildBrowserDriver::start(
            &AdapterCommand::for_install(&install_root(a)),
            &a.one("profile")
                .map(PathBuf::from)
                .unwrap_or_else(|| sibling(&report_path, ".profile")),
        )?;
        eprintln!("browser replay via {}", d.executable);
        Some(d)
    } else {
        None
    };
    // Native replays drive the shared desktop: anyone else's key or button
    // press stops them. Browser replays act inside their own page.
    let guard = (proc.category != CATEGORY_BROWSER).then(WinInputGuard::start);
    let ports = Ports {
        windows: &WinWindows,
        input: &WinInjector,
        session: &WinSession,
        files: &StdFiles,
        pacer: &pacer,
        cancel,
        browser: driver.as_ref().map(|d| d as &dyn BrowserDriver),
        interference: guard.as_ref().map(|g| g as &dyn InterferenceMonitor),
    };
    let opts = RunOptions {
        bindings,
        step_timeout_ms: a.num("step-timeout-ms", 10_000)?,
        settle_ms: a.num("settle-ms", RunOptions::default().settle_ms)?,
        char_delay_ms: a.num("char-delay-ms", RunOptions::default().char_delay_ms)?,
        stable_ms: a.num("stable-ms", RunOptions::default().stable_ms)?,
        bound_window: a
            .one("bound-window")
            .map(|v| v.parse::<u64>())
            .transpose()
            .map_err(|e| format!("--bound-window: {e}"))?,
        ..Default::default()
    };
    let started = now_ms();
    let report = execute::run(&proc, &ports, &opts);
    let v = json!({"started_at_unix_ms": started, "ended_at_unix_ms": now_ms(), "report": report});
    write_json_atomic(&report_path, &v).map_err(|e| e.to_string())?;
    print(v);
    Ok(ExitCode::from(match report.outcome {
        Outcome::CompletedUnverified => 0,
        Outcome::Refused => 2,
        Outcome::Failed => 3,
        Outcome::Uncertain => 4,
        Outcome::Cancelled => 5,
    }))
}

fn main() -> ExitCode {
    init_dpi_awareness();
    let raw: Vec<String> = std::env::args().skip(1).collect();
    let Some(cmd) = raw.first().cloned() else {
        eprintln!("usage: redrise-engine <readiness|record|compile|run> [flags]");
        return ExitCode::from(1);
    };
    let result = Args::parse(&raw[1..]).and_then(|a| match cmd.as_str() {
        "readiness" => cmd_readiness(&a),
        "record" => cmd_record(&a),
        "compile" => cmd_compile(&a),
        "run" => cmd_run(&a),
        "version" => {
            print(json!({"engine": env!("CARGO_PKG_VERSION"), "platform": PLATFORM_WINDOWS_X64}));
            Ok(ExitCode::SUCCESS)
        }
        other => Err(format!("unknown command {other}")),
    });
    match result {
        Ok(c) => c,
        Err(e) => {
            print(json!({"status": "error", "error": e}));
            ExitCode::from(1)
        }
    }
}
