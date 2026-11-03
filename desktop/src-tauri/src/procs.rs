//! App-managed child processes: host Core and Runner agent. They stop via
//! stop files (clean shutdown, PostgreSQL stopped by the Core); a kill is only
//! the last resort after the grace period.
use std::io::{BufRead, BufReader};
use std::os::windows::process::CommandExt;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::mpsc;
use std::time::{Duration, Instant};

use serde_json::{json, Value};

use crate::paths::Paths;

const NO_WINDOW: u32 = 0x0800_0000;

#[derive(Default)]
pub struct Supervisor {
    core: Option<(Child, PathBuf, Value)>,
    agent: Option<(Child, PathBuf)>,
}

fn err(code: &str, what: &str, detail: String) -> Value {
    let mut v = crate::diag_err(code, what, &detail);
    v["diagnostic"]["module_hints"] = json!(["RR-RUNTIME", "RR-UI"]);
    v
}

fn log_file(dir: &PathBuf, name: &str) -> Result<std::fs::File, Value> {
    std::fs::create_dir_all(dir).map_err(|e| err("RUNTIME-NOT-PRIVATE", "Could not prepare the data folder.", e.to_string()))?;
    std::fs::OpenOptions::new().create(true).append(true).open(dir.join(name))
        .map_err(|e| err("RUNTIME-NOT-PRIVATE", "Could not open the log.", e.to_string()))
}

fn python(p: &Paths, module: &str) -> Command {
    let mut c = Command::new(p.python());
    c.args(["-B", "-X", "utf8", "-m", module]).creation_flags(NO_WINDOW).stdin(Stdio::null());
    c
}

impl Supervisor {
    pub fn reap(&mut self) {
        if let Some((c, _, _)) = self.core.as_mut() {
            if matches!(c.try_wait(), Ok(Some(_))) {
                self.core = None;
            }
        }
        if let Some((c, _)) = self.agent.as_mut() {
            if matches!(c.try_wait(), Ok(Some(_))) {
                self.agent = None;
            }
        }
    }

    pub fn core_running(&self) -> bool {
        self.core.is_some()
    }

    pub fn agent_running(&self) -> bool {
        self.agent.is_some()
    }

    pub fn start_core(&mut self, p: &Paths, port: Option<u16>) -> Result<Value, Value> {
        self.reap();
        if let Some((_, _, ready)) = &self.core {
            return Ok(ready.clone());
        }
        let host_dir = p.data_root.join("host");
        let stop = host_dir.join("core.stop");
        let mut cmd = python(p, "redrise_core");
        cmd.arg("serve").arg("--stop-file").arg(&stop);
        if let Some(port) = port {
            cmd.arg("--port").arg(port.to_string());
        }
        let mut child = cmd.stdout(Stdio::piped()).stderr(log_file(&host_dir.join("logs"), "core.log")?).spawn()
            .map_err(|e| err("RUNTIME-NOT-PRIVATE", "The team server could not be started.", e.to_string()))?;
        let out = child.stdout.take().unwrap();
        let (tx, rx) = mpsc::channel();
        std::thread::spawn(move || {
            for line in BufReader::new(out).lines().map_while(Result::ok) {
                if let Ok(v) = serde_json::from_str::<Value>(&line) {
                    if v.get("event").and_then(Value::as_str) == Some("core_ready") {
                        let _ = tx.send(v);
                    }
                }
            }
        });
        match rx.recv_timeout(Duration::from_secs(180)) {
            Ok(ready) => {
                self.core = Some((child, stop, ready.clone()));
                Ok(ready)
            }
            Err(_) => {
                let status = child.try_wait().ok().flatten();
                if status.is_none() {
                    let _ = std::fs::write(&stop, b"stop");
                }
                Err(err("CORE-UNREACHABLE", "The team server did not become ready.",
                        format!("no readiness signal ({}); see host\\logs\\core.log", status.map(|s| s.to_string()).unwrap_or("running".into()))))
            }
        }
    }

    pub fn start_agent(&mut self, p: &Paths) -> Result<(), Value> {
        self.reap();
        if self.agent.is_some() {
            return Ok(());
        }
        let dir = p.data_root.join("agent");
        let stop = dir.join("agent.stop");
        let log = log_file(&dir, "agent.log")?;
        let child = python(p, "redrise_runner").arg("agent").arg("--stop-file").arg(&stop)
            .stdout(log.try_clone().map_err(|e| err("RUNTIME-NOT-PRIVATE", "Log unavailable.", e.to_string()))?)
            .stderr(log).spawn()
            .map_err(|e| err("RUNTIME-NOT-PRIVATE", "The runner of this station could not be started.", e.to_string()))?;
        self.agent = Some((child, stop));
        Ok(())
    }

    pub fn stop_all(&mut self) {
        let mut waiting: Vec<Child> = Vec::new();
        if let Some((c, stop)) = self.agent.take() {
            let _ = std::fs::write(&stop, b"stop");
            waiting.push(c);
        }
        if let Some((c, stop, _)) = self.core.take() {
            let _ = std::fs::write(&stop, b"stop");
            waiting.push(c);
        }
        let t0 = Instant::now();
        while t0.elapsed() < Duration::from_secs(20) && waiting.iter_mut().any(|c| matches!(c.try_wait(), Ok(None))) {
            std::thread::sleep(Duration::from_millis(100));
        }
        for mut c in waiting {
            if matches!(c.try_wait(), Ok(None)) {
                let _ = c.kill(); // last resort after the grace period
            }
        }
    }
}
