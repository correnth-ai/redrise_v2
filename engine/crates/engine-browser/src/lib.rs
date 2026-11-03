//! Browser surface adapters. The Playwright work happens in the packaged
//! adapter process (`python -m redrise_browser`); this crate owns its
//! lifecycle and maps its JSON lines onto the Engine ports.
use std::cell::RefCell;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

use engine_core::model::{RawEvent, RawKind, Rect, WindowRef, BROWSER_SURFACE};
use engine_core::ports::{
    url_origin, BrowserDriver, BrowserError, BrowserState, EventTx, InputSource, RunningSource,
    SourceStats,
};
use serde_json::{json, Value};

const READY_TIMEOUT: Duration = Duration::from_secs(90);

/// How to start the adapter: `<install>/runtime/python/python.exe -B -X utf8
/// -m redrise_browser --browsers <install>/browsers`.
#[derive(Debug, Clone)]
pub struct AdapterCommand {
    pub program: PathBuf,
    pub args: Vec<String>,
}

impl AdapterCommand {
    pub fn for_install(root: &Path) -> Self {
        Self {
            program: root.join("runtime").join("python").join("python.exe"),
            args: vec![
                "-B".into(),
                "-X".into(),
                "utf8".into(),
                "-m".into(),
                "redrise_browser".into(),
                "--browsers".into(),
                root.join("browsers").display().to_string(),
            ],
        }
    }

    fn spawn(&self, extra: &[String]) -> Result<Child, String> {
        let mut c = Command::new(&self.program);
        c.args(&self.args).args(extra);
        // The adapter must not inherit a foreign Python configuration.
        for k in [
            "PYTHONHOME",
            "PYTHONPATH",
            "PYTHONSTARTUP",
            "PLAYWRIGHT_BROWSERS_PATH",
        ] {
            c.env_remove(k);
        }
        c.stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null());
        c.spawn().map_err(|e| {
            format!(
                "browser adapter not startable ({}): {e}",
                self.program.display()
            )
        })
    }
}

// ---------------------------------------------------------------- record

pub struct BrowserInputSource {
    pub cmd: AdapterCommand,
    pub url: String,
    pub profile: PathBuf,
}

struct RunningBrowser {
    child: Mutex<Child>,
    stdin: Mutex<ChildStdin>,
    reader: JoinHandle<Result<(), String>>,
    pong: Arc<AtomicBool>,
}

fn window(pid: u32, url: &str, title: &str) -> WindowRef {
    WindowRef {
        pid,
        process_image: BROWSER_SURFACE.into(),
        class: url_origin(url),
        title: title.into(),
        rect: Rect::default(),
    }
}

fn s(v: &Value, k: &str) -> String {
    v.get(k)
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_string()
}

fn to_kind(v: &Value) -> Option<RawKind> {
    Some(match v.get("type")?.as_str()? {
        "browser_goto" => RawKind::BrowserGoto { url: s(v, "url") },
        "browser_click" => RawKind::BrowserClick {
            selector: s(v, "selector"),
        },
        "browser_fill" => RawKind::BrowserFill {
            selector: s(v, "selector"),
            value: s(v, "value"),
        },
        "browser_press" => RawKind::BrowserPress {
            selector: s(v, "selector"),
            key: s(v, "key"),
        },
        "unsupported" => RawKind::BrowserUnsupported {
            reason: s(v, "reason"),
        },
        _ => return None,
    })
}

impl InputSource for BrowserInputSource {
    fn spawn(self: Box<Self>, mut tx: EventTx) -> Result<Box<dyn RunningSource>, String> {
        let mut child = self.cmd.spawn(&[
            "record".into(),
            "--url".into(),
            self.url.clone(),
            "--profile".into(),
            self.profile.display().to_string(),
        ])?;
        let pid = child.id();
        let stdin = child.stdin.take().ok_or("no adapter stdin")?;
        let stdout = child.stdout.take().ok_or("no adapter stdout")?;
        let (ready_tx, ready_rx) = mpsc::channel::<Result<String, String>>();
        let pong = Arc::new(AtomicBool::new(false));
        let pong2 = pong.clone();
        let started = Instant::now();
        let reader = std::thread::Builder::new()
            .name("rr-browser-record".into())
            .spawn(move || {
                let mut ready_tx = Some(ready_tx);
                for line in BufReader::new(stdout).lines() {
                    let line = line.map_err(|e| e.to_string())?;
                    // A line that is not an event cannot be dropped silently: the
                    // recording would look complete with an event missing.
                    let Ok(v) = serde_json::from_str::<Value>(&line) else {
                        return Err(format!(
                            "browser adapter sent a non-JSON line ({} bytes)",
                            line.len()
                        ));
                    };
                    match v.get("type").and_then(Value::as_str) {
                        Some("ready") => {
                            if let Some(t) = ready_tx.take() {
                                let _ = t.send(Ok(s(&v, "browser_executable")));
                            }
                        }
                        Some("pong") => pong2.store(true, Ordering::SeqCst),
                        Some("stopped") => break,
                        Some("error") => {
                            let msg = s(&v, "detail");
                            if let Some(t) = ready_tx.take() {
                                let _ = t.send(Err(msg.clone()));
                            }
                            return Err(format!("browser adapter error: {msg}"));
                        }
                        _ => {
                            if let Some(kind) = to_kind(&v) {
                                let url = s(&v, "url");
                                let ev = RawEvent {
                                    seq: 0,
                                    t_us: started.elapsed().as_micros() as u64,
                                    kind,
                                    window: window(pid, &url, &s(&v, "title")),
                                };
                                tx.offer(ev);
                            }
                        }
                    }
                }
                drop(tx); // end of stream
                Ok(())
            })
            .map_err(|e| e.to_string())?;
        let executable = match ready_rx.recv_timeout(READY_TIMEOUT) {
            Ok(Ok(exe)) => exe,
            Ok(Err(e)) => return Err(format!("browser adapter failed to start: {e}")),
            Err(_) => {
                let _ = child.kill();
                return Err("browser adapter did not become ready".into());
            }
        };
        eprintln!("browser recording via {executable}");
        Ok(Box::new(RunningBrowser {
            child: Mutex::new(child),
            stdin: Mutex::new(stdin),
            reader,
            pong,
        }))
    }
}

impl RunningSource for RunningBrowser {
    fn check_liveness(&self) -> Result<(), String> {
        self.pong.store(false, Ordering::SeqCst);
        writeln!(self.stdin.lock().unwrap(), "ping").map_err(|e| e.to_string())?;
        let t0 = Instant::now();
        while !self.pong.load(Ordering::SeqCst) {
            if t0.elapsed() > Duration::from_secs(3) {
                return Err("browser adapter did not answer ping".into());
            }
            std::thread::sleep(Duration::from_millis(20));
        }
        Ok(())
    }
    fn request_stop(&self) {
        let _ = writeln!(self.stdin.lock().unwrap(), "stop");
    }
    fn join(self: Box<Self>) -> Result<SourceStats, String> {
        let r = self
            .reader
            .join()
            .map_err(|_| "browser reader panicked".to_string())?;
        let status = self
            .child
            .lock()
            .unwrap()
            .wait()
            .map_err(|e| e.to_string())?;
        r?;
        if !status.success() {
            return Err(format!("browser adapter exited with {status}"));
        }
        Ok(SourceStats::default())
    }
}

// ---------------------------------------------------------------- replay

/// Upper bound for one adapter reply (the adapter's own action timeout is
/// 10 s by default); a hung adapter becomes a partial transport error.
const CALL_TIMEOUT: Duration = Duration::from_secs(40);

pub struct ChildBrowserDriver {
    child: RefCell<Child>,
    io: RefCell<(ChildStdin, mpsc::Receiver<String>)>,
    pub executable: String,
}

/// Lines from the adapter's stdout on a channel, so every read has a deadline.
fn line_channel(stdout: ChildStdout) -> mpsc::Receiver<String> {
    let (tx, rx) = mpsc::channel();
    std::thread::spawn(move || {
        let mut r = BufReader::new(stdout);
        loop {
            let mut line = String::new();
            match r.read_line(&mut line) {
                Ok(0) | Err(_) => return, // sender dropped: receiver sees disconnect
                Ok(_) => {
                    if tx.send(line).is_err() {
                        return;
                    }
                }
            }
        }
    });
    rx
}

impl ChildBrowserDriver {
    pub fn start(cmd: &AdapterCommand, profile: &Path) -> Result<Self, String> {
        let mut child = cmd.spawn(&[
            "serve".into(),
            "--profile".into(),
            profile.display().to_string(),
        ])?;
        let stdin = child.stdin.take().ok_or("no adapter stdin")?;
        let lines = line_channel(child.stdout.take().ok_or("no adapter stdout")?);
        let first = match lines.recv_timeout(READY_TIMEOUT) {
            Ok(l) => l,
            Err(e) => {
                let _ = child.kill();
                return Err(format!("adapter not ready: {e}"));
            }
        };
        let v: Value = serde_json::from_str(first.trim())
            .map_err(|_| format!("adapter not ready: {first}"))?;
        if v.get("ok") != Some(&Value::Bool(true)) {
            return Err(format!("adapter failed: {first}"));
        }
        Ok(Self {
            child: RefCell::new(child),
            io: RefCell::new((stdin, lines)),
            executable: s(&v, "browser_executable"),
        })
    }

    fn call(&self, cmd: Value) -> Result<Value, BrowserError> {
        let mut io = self.io.borrow_mut();
        let transport = |e: String| BrowserError {
            code: "adapter_transport".into(),
            detail: e,
            partial: true,
        };
        writeln!(io.0, "{cmd}").map_err(|e| transport(e.to_string()))?;
        io.0.flush().map_err(|e| transport(e.to_string()))?;
        let line = match io.1.recv_timeout(CALL_TIMEOUT) {
            Ok(l) => l,
            Err(mpsc::RecvTimeoutError::Timeout) => {
                return Err(transport(format!("no adapter reply in {CALL_TIMEOUT:?}")))
            }
            Err(mpsc::RecvTimeoutError::Disconnected) => {
                return Err(transport("adapter closed".into()))
            }
        };
        let v: Value = serde_json::from_str(line.trim()).map_err(|e| transport(e.to_string()))?;
        if v.get("ok") == Some(&Value::Bool(true)) {
            Ok(v)
        } else {
            Err(BrowserError {
                code: s(&v, "code"),
                detail: s(&v, "detail"),
                partial: s(&v, "delivery") != "not_attempted",
            })
        }
    }
}

impl BrowserDriver for ChildBrowserDriver {
    fn state(&self) -> Result<BrowserState, BrowserError> {
        let v = self.call(json!({"cmd": "state"}))?;
        Ok(BrowserState {
            url: s(&v, "url"),
            title: s(&v, "title"),
        })
    }
    fn goto(&self, url: &str) -> Result<(), BrowserError> {
        self.call(json!({"cmd": "goto", "url": url})).map(|_| ())
    }
    fn click(&self, selector: &str) -> Result<(), BrowserError> {
        self.call(json!({"cmd": "click", "selector": selector}))
            .map(|_| ())
    }
    fn fill(&self, selector: &str, value: &str) -> Result<(), BrowserError> {
        self.call(json!({"cmd": "fill", "selector": selector, "value": value}))
            .map(|_| ())
    }
    fn press(&self, selector: &str, key: &str) -> Result<(), BrowserError> {
        self.call(json!({"cmd": "press", "selector": selector, "key": key}))
            .map(|_| ())
    }
}

impl Drop for ChildBrowserDriver {
    fn drop(&mut self) {
        let _ = self.call(json!({"cmd": "close"}));
        let mut c = self.child.borrow_mut();
        let t0 = Instant::now();
        while t0.elapsed() < Duration::from_secs(10) {
            if let Ok(Some(_)) = c.try_wait() {
                return;
            }
            std::thread::sleep(Duration::from_millis(50));
        }
        // Our own child only; the browser it launched closes with it.
        let _ = c.kill();
    }
}
