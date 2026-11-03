//! Local operations on this station, all through the packaged Runner/Engine
//! with fixed subcommands (no arbitrary command execution from the UI).
use std::io::Write;
use std::os::windows::process::CommandExt;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde_json::{json, Value};

use crate::paths::Paths;

const NO_WINDOW: u32 = 0x0800_0000;
const RUNNER_ALLOWED: &[&str] = &["health", "capabilities", "templates", "check-template", "excel-discover", "excel-new"];

pub fn short_id() -> String {
    let n = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_nanos()).unwrap_or(0);
    format!("{:016x}", (n as u64) ^ (std::process::id() as u64).rotate_left(32))
}

fn ts() -> String {
    format!("{}", SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_millis()).unwrap_or(0))
}

/// Synthetic (injected) input is refused by default; accepted only in a lab
/// run explicitly enabled through the environment (never a customer setting).
pub fn lab_accept_injected() -> bool {
    std::env::var("REDRISE_LAB_ACCEPT_INJECTED").map(|v| v == "1").unwrap_or(false)
}

fn fail(code: &str, what: &str, detail: String) -> Value {
    crate::diag_err(code, what, &detail)
}

fn parse_out(stdout: &[u8], what: &str) -> Result<Value, Value> {
    serde_json::from_slice::<Value>(stdout).map_err(|_| {
        let mut v = fail("CONTRACT-PAYLOAD", what, "local response is not JSON".into());
        v["diagnostic"]["category"] = json!("contract");
        v["diagnostic"]["module_hints"] = json!(["RR-RUNNER", "RR-UI", "RR-CONTRACT"]);
        v
    })
}

pub fn runner(p: &Paths, args: &[String]) -> Result<Value, Value> {
    let sub = args.first().map(String::as_str).unwrap_or("");
    if !RUNNER_ALLOWED.contains(&sub) {
        return Err(fail("CONTRACT-PAYLOAD", "Local operation not allowed.", format!("subcommand {sub:?}")));
    }
    let out = Command::new(p.python()).args(["-B", "-X", "utf8", "-m", "redrise_runner"]).args(args)
        .creation_flags(NO_WINDOW).stdin(Stdio::null()).output()
        .map_err(|e| fail("RUNTIME-NOT-PRIVATE", "The local runner could not be started.", e.to_string()))?;
    let v = parse_out(&out.stdout, "O executor local respondeu em formato inesperado.")?;
    Ok(json!({"exit": out.status.code(), "result": v}))
}

pub fn join(p: &Paths, code: &str, username: &str, password: &str, station: &str, is_host: bool,
            host_override: Option<&str>) -> Result<Value, Value> {
    let mut c = Command::new(p.python());
    c.args(["-B", "-X", "utf8", "-m", "redrise_runner", "join", "--code"]);
    // The host joins itself over loopback; the advertised code keeps the LAN name.
    let code = match host_override {
        Some(h) => {
            let parts: Vec<&str> = code.split(':').collect();
            if parts.len() == 4 { format!("rr1:{h}:{}:{}", parts[2], parts[3]) } else { code.to_string() }
        }
        None => code.to_string(),
    };
    c.arg(&code).args(["--username", username, "--station-name", station]);
    if is_host {
        c.arg("--is-host");
    }
    let mut child = c.creation_flags(NO_WINDOW).stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null())
        .spawn().map_err(|e| fail("RUNTIME-NOT-PRIVATE", "The local runner could not be started.", e.to_string()))?;
    // Password only through stdin: never on a command line or in a file.
    child.stdin.take().unwrap().write_all(format!("{password}\n").as_bytes())
        .map_err(|e| fail("RUNTIME-NOT-PRIVATE", "Falha ao comunicar com o executor local.", e.to_string()))?;
    let out = child.wait_with_output().map_err(|e| fail("RUNTIME-NOT-PRIVATE", "Executor local interrompido.", e.to_string()))?;
    let v = parse_out(&out.stdout, "The station connection answered in an unexpected format.")?;
    if out.status.success() { Ok(v) } else { Err(v) }
}

/// Opens the RedRise browser profile (the one templates use) for the user to
/// act by hand, e.g. sign in to Gmail. Detached: RedRise neither records nor types.
pub fn open_browser(p: &Paths, url: &str) -> Result<Value, Value> {
    if !(url.starts_with("https://") || url.starts_with("http://")) {
        return Err(fail("VALIDATION", "Invalid address.", "enter an http(s) address".into()));
    }
    let browsers = p.install_root.join("browsers");
    Command::new(p.python()).args(["-B", "-X", "utf8", "-m", "redrise_browser", "--browsers"]).arg(&browsers)
        .arg("open").args(["--url", url, "--profile"]).arg(p.data_root.join("browser-profile"))
        .creation_flags(NO_WINDOW).stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null()).spawn()
        .map_err(|e| fail("RUNTIME-NOT-PRIVATE", "The RedRise browser could not be opened.", e.to_string()))?;
    Ok(json!({"opened": url}))
}

pub struct Recording {
    child: Child,
    dir: PathBuf,
    stop_file: PathBuf,
    category: String,
}

fn engine(p: &Paths) -> PathBuf {
    p.install_root.join("engine").join("redrise-engine.exe")
}

impl Recording {
    pub fn start(p: &Paths, category: &str, target: Option<&str>, url: Option<&str>) -> Result<Self, Value> {
        let dir = p.data_root.join("recordings").join(ts());
        std::fs::create_dir_all(&dir).map_err(|e| fail("RUNTIME-NOT-PRIVATE", "Recordings folder unavailable.", e.to_string()))?;
        let stop_file = dir.join("stop.flag");
        let mut c = Command::new(engine(p));
        c.arg("record").arg("--out").arg(dir.join("rec")).arg("--stop-file").arg(&stop_file).args(["--max-seconds", "900"]);
        match category {
            "browser" => {
                let u = url.filter(|u| u.starts_with("http://") || u.starts_with("https://") || u.starts_with("file:///"))
                    .ok_or_else(|| fail("VALIDATION", "Invalid address.", "enter an http(s) address".into()))?;
                c.args(["--category", "browser", "--url", u]);
            }
            "windows" => {
                let t = target.filter(|t| t.to_lowercase().ends_with(".exe") && !t.contains(['\\', '/', ' ']))
                    .ok_or_else(|| fail("VALIDATION", "Invalid application.", "enter the executable, e.g. excel.exe".into()))?;
                c.args(["--target", t]);
                if lab_accept_injected() {
                    c.arg("--accept-injected");
                }
            }
            other => return Err(fail("VALIDATION", "Category not supported on this station.", format!("{other}"))),
        }
        let log = std::fs::File::create(dir.join("record.log")).map_err(|e| fail("RUNTIME-NOT-PRIVATE", "Log unavailable.", e.to_string()))?;
        let child = c.creation_flags(NO_WINDOW).stdin(Stdio::null()).stdout(Stdio::piped()).stderr(log).spawn()
            .map_err(|e| fail("ENGINE-MISSING", "The automation engine could not be started.", e.to_string()))?;
        Ok(Self { child, dir, stop_file, category: category.to_string() })
    }

    pub fn info(&self) -> Value {
        json!({"recording": self.dir.join("rec").display().to_string(), "category": self.category,
               "injected_input_accepted": self.category == "windows" && lab_accept_injected()})
    }

    pub fn stop(mut self, cancel: bool) -> Result<Value, Value> {
        let _ = std::fs::write(&self.stop_file, if cancel { "cancel" } else { "stop" });
        let t0 = std::time::Instant::now();
        while t0.elapsed() < Duration::from_secs(40) {
            if let Ok(Some(_)) = self.child.try_wait() {
                break;
            }
            std::thread::sleep(Duration::from_millis(100));
        }
        if matches!(self.child.try_wait(), Ok(None)) {
            let _ = self.child.kill();
            return Err(fail("ENGINE-NO-RESPONSE", "The recording did not finish in time.", "Engine did not answer the stop".into()));
        }
        let out = self.child.wait_with_output().map_err(|e| fail("ENGINE-NO-RESPONSE", "Recording interrupted.", e.to_string()))?;
        let v = parse_out(&out.stdout, "The recording answered in an unexpected format.")?;
        Ok(json!({"recording": self.dir.join("rec").display().to_string(), "result": v, "exit": out.status.code()}))
    }
}

pub fn compile(p: &Paths, recording: &str, params: &[String], declares: &[String]) -> Result<Value, Value> {
    // Canonical paths: ".." cannot escape the recordings folder.
    let rec = std::fs::canonicalize(recording).unwrap_or_default();
    let base = std::fs::canonicalize(p.data_root.join("recordings")).unwrap_or_default();
    if base.as_os_str().is_empty() || !rec.starts_with(&base) {
        return Err(fail("VALIDATION", "Invalid recording.", "outside the recordings folder".into()));
    }
    let out = rec.with_file_name(format!("procedure-{}.json", ts()));
    let mut c = Command::new(engine(p));
    c.arg("compile").arg("--recording").arg(&rec).arg("--out").arg(&out);
    for x in params {
        c.arg("--param").arg(x);
    }
    for x in declares {
        c.arg("--declare").arg(x);
    }
    let o = c.creation_flags(NO_WINDOW).stdin(Stdio::null()).output()
        .map_err(|e| fail("ENGINE-MISSING", "The automation engine could not be started.", e.to_string()))?;
    let v: Value = serde_json::from_slice(&o.stdout).unwrap_or(json!({"status": "error",
        "detail": String::from_utf8_lossy(&o.stderr).chars().take(400).collect::<String>()}));
    if !o.status.success() {
        return Err(json!({"compile": v}));
    }
    let proc_json: Value = std::fs::read(&out).ok().and_then(|b| serde_json::from_slice(&b).ok()).unwrap_or(Value::Null);
    Ok(json!({"compile": v, "procedure": proc_json}))
}
