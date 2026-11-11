//! RedRise desktop: Tauri commands for the React UI.
//!
//! Responsibilities (small, separate modules):
//! - `paths`: install root (binaries) and real LocalAppData data root;
//! - `procs`: app-managed lifecycle of the host Core and the Runner agent
//!   (stop files, never a kill while they write);
//! - `core_api`: HTTPS client pinned to the team host certificate;
//! - `local`: whitelisted local Runner/Engine operations (no arbitrary shell).
mod core_api;
mod local;
mod paths;
mod procs;
mod update;
mod vault;

use std::sync::Mutex;

use serde_json::{json, Value};
use tauri::{Manager, RunEvent, State};

pub struct App {
    pub paths: paths::Paths,
    pub procs: Mutex<procs::Supervisor>,
    pub recording: Mutex<Option<local::Recording>>,
    pub verified_release: Mutex<Option<Value>>,
}

type Res = Result<Value, Value>;

fn diag_err(code: &str, what: &str, detail: &str) -> Value {
    // UI-side diagnostic (redrise.diagnostic/1) for failures before any Core/Runner answer.
    json!({"diagnostic": {
        "schema": "redrise.diagnostic/1", "error_code": code, "category": "environment",
        "what_happened": what, "completed": "The action was not completed.", "pending": "Nothing was changed by the app.",
        "effect_state": "none", "next_action": "Try again. If it persists, copy the diagnostic and send it to support.",
        "retry": "after_fix", "details_summary": detail, "reported_by": "RR-UI", "module_hints": ["RR-UI", "RR-RUNTIME"],
        "diagnosis_status": "unconfirmed", "boundary": null, "correlation_id": local::short_id(),
        "version": {"desktop": env!("CARGO_PKG_VERSION")}, "technical_details": {}, "cause": null, "params": {"reason": detail}}})
}

#[tauri::command]
fn app_info(app: State<App>) -> Res {
    let p = &app.paths;
    let mut s = app.procs.lock().unwrap();
    s.reap();
    Ok(json!({
        "desktop": env!("CARGO_PKG_VERSION"),
        "install_root": p.install_root.display().to_string(),
        "data_root": p.data_root.display().to_string(),
        "install_manifest_sha256": p.manifest_sha256(),
        "host_configured": p.host_config().is_some(),
        "host": p.host_config(),
        "connection": p.connection(),
        // Chosen in the installer for this computer while it is not set up (server|station), or null.
        "setup_intent": if p.connection().is_none() { p.setup_intent() } else { None },
        "core_running": s.core_running(),
        "agent_running": s.agent_running(),
        "agent_status": p.agent_status(),
        "lab_accept_injected": local::lab_accept_injected(),
    }))
}

#[tauri::command(async)]
fn host_create(app: State<App>, port: u16, team: String, username: String, display: String, password: String,
               station_name: String) -> Res {
    let p = &app.paths;
    let ready = app.procs.lock().unwrap().start_core(p, Some(port))?;
    let client = core_api::Client::from_host(p, None).map_err(|e| diag_err("CORE-UNREACHABLE", "The team server did not answer.", &e))?;
    client.call("POST", "/api/v1/setup", &json!({"team": team, "username": username, "display": display, "password": password}))?;
    let code = ready.get("join_code").and_then(Value::as_str).unwrap_or_default().to_string();
    // The host computer is also a station (D05: the host can execute too).
    local::join(p, &code, &username, &password, &station_name, true, Some("127.0.0.1"))?;
    app.procs.lock().unwrap().start_agent(p)?;
    p.consume_setup_intent();
    Ok(json!({"join_code": code}))
}

#[tauri::command(async)]
fn host_start(app: State<App>) -> Res {
    let ready = app.procs.lock().unwrap().start_core(&app.paths, None)?;
    Ok(ready)
}

#[tauri::command(async)]
fn station_join(app: State<App>, code: String, username: String, password: String, station_name: String) -> Res {
    let out = local::join(&app.paths, &code, &username, &password, &station_name, false, None)?;
    app.procs.lock().unwrap().start_agent(&app.paths)?;
    app.paths.consume_setup_intent();
    Ok(out)
}

#[tauri::command]
fn agent_start(app: State<App>) -> Res {
    app.procs.lock().unwrap().start_agent(&app.paths)?;
    Ok(json!({"ok": true}))
}

#[tauri::command(async)]
fn api(app: State<App>, method: String, path: String, body: Option<Value>, token: Option<String>) -> Res {
    if !path.starts_with("/api/v1/") || path.contains("..") || path.starts_with("/api/v1/runner/") {
        return Err(diag_err("CONTRACT-PAYLOAD", "Invalid internal request.", "route not allowed for the interface"));
    }
    let client = core_api::Client::from_connection(&app.paths, token)
        .map_err(|e| diag_err("STATION-NOT-JOINED", "This computer is not connected to a team yet.", &e))?;
    let mut body = body.unwrap_or(json!({}));
    if method == "POST" && path == "/api/v1/login" {
        // The session is tied to this station by its own credential, never by a name the page sends.
        if let (Some(obj), Some(t)) = (body.as_object_mut(), vault::station_token()) {
            obj.insert("station_token".into(), Value::String(t));
        }
    }
    client.call(&method, &path, &body)
}

#[tauri::command(async)]
fn runner_local(app: State<App>, args: Vec<String>) -> Res {
    local::runner(&app.paths, &args)
}

#[tauri::command]
fn record_start(app: State<App>, category: String, target: Option<String>, url: Option<String>) -> Res {
    let mut slot = app.recording.lock().unwrap();
    if slot.is_some() {
        return Err(diag_err("SESSION-BUSY", "A recording is already in progress.", "one recording at a time"));
    }
    let r = local::Recording::start(&app.paths, &category, target.as_deref(), url.as_deref())?;
    let info = r.info();
    *slot = Some(r);
    Ok(info)
}

#[tauri::command(async)]
fn record_stop(app: State<App>, cancel: bool) -> Res {
    let r = app.recording.lock().unwrap().take();
    match r {
        Some(r) => r.stop(cancel),
        None => Err(diag_err("NOT-FOUND", "No recording in progress.", "recording missing")),
    }
}

#[tauri::command(async)]
fn record_compile(app: State<App>, recording: String, params: Vec<String>, declares: Vec<String>) -> Res {
    local::compile(&app.paths, &recording, &params, &declares)
}

/// Bytes used by this station's data folder, split into logs and other data;
/// the PostgreSQL cluster folder is left out (the Core reports the database size).
#[tauri::command(async)]
fn storage_local(app: State<App>) -> Res {
    fn size(p: &std::path::Path) -> u64 {
        match std::fs::symlink_metadata(p) {
            Ok(m) if m.is_dir() => std::fs::read_dir(p).map(|rd| rd.flatten().map(|e| size(&e.path())).sum()).unwrap_or(0),
            Ok(m) if m.is_file() => m.len(),
            _ => 0, // links and unreadable entries are not followed
        }
    }
    let d = &app.paths.data_root;
    let logs = size(&d.join("logs")) + size(&d.join("host").join("logs"));
    let total = size(d);
    let pg = size(&d.join("host").join("pgdata"));
    Ok(json!({"data_bytes": total.saturating_sub(logs + pg), "logs_bytes": logs}))
}

/// "Outro…" in Nova Rotina: the Windows file picker, owned by the app window. Cancel returns null.
#[tauri::command(async)]
fn pick_file(handle: tauri::AppHandle) -> Res {
    use windows_sys::Win32::UI::Controls::Dialogs::{GetOpenFileNameW, OFN_EXPLORER, OFN_FILEMUSTEXIST, OFN_NOCHANGEDIR, OFN_PATHMUSTEXIST, OPENFILENAMEW};
    let owner = handle.get_webview_window("main").and_then(|w| w.hwnd().ok()).map_or(std::ptr::null_mut(), |h| h.0 as _);
    let mut file = vec![0u16; 32768];
    let mut ofn: OPENFILENAMEW = unsafe { std::mem::zeroed() };
    ofn.lStructSize = std::mem::size_of::<OPENFILENAMEW>() as u32;
    ofn.hwndOwner = owner;
    ofn.lpstrFile = file.as_mut_ptr();
    ofn.nMaxFile = file.len() as u32;
    ofn.Flags = OFN_EXPLORER | OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR;
    if unsafe { GetOpenFileNameW(&mut ofn) } == 0 {
        return Ok(Value::Null); // cancelled, or the dialog could not open: nothing was chosen
    }
    let end = file.iter().position(|c| *c == 0).unwrap_or(file.len());
    Ok(Value::String(String::from_utf16_lossy(&file[..end])))
}

/// "Veja aqui!": the folder of a report of this computer in the Explorer, the file selected. The name comes
/// from a result, so it is checked: a bare .pdf name, in the one folder reports are saved to, and existing.
#[tauri::command]
fn open_report_folder(name: String) -> Res {
    use std::os::windows::process::CommandExt;
    if name.is_empty() || name.contains(['/', '\\', ':']) || name.contains("..") || !name.to_lowercase().ends_with(".pdf") {
        return Err(diag_err("VALIDATION", "The name of the report is not valid.", "bare .pdf name expected"));
    }
    let file = paths::documents().join("RedRise").join("Relatorios").join(&name);
    if !file.is_file() {
        return Err(json!({"diagnostic": {
            "schema": "redrise.diagnostic/1", "error_code": "REPORT-NOT-HERE", "category": "precondition",
            "what_happened": format!("The report {name} is not on this computer."), "completed": "Nothing was opened.",
            "pending": "The report stays where it was saved.", "effect_state": "none",
            "next_action": "Open the Documents folder of the station that ran it, under RedRise, Relatorios.",
            "retry": "not_useful", "details_summary": "Reports are saved on the station that runs the step.", "reported_by": "RR-UI",
            "module_hints": ["RR-REPORT"], "diagnosis_status": "unconfirmed", "boundary": null, "correlation_id": local::short_id(),
            "version": {"desktop": env!("CARGO_PKG_VERSION")}, "technical_details": {}, "cause": null, "params": {"name": name}}}));
    }
    std::process::Command::new("explorer.exe").raw_arg(format!("/select,\"{}\"", file.display())).spawn()
        .map_err(|e| diag_err("REPORT-NOT-HERE", "The Explorer could not be opened.", &e.to_string()))?;
    Ok(json!({"opened": name}))
}

#[tauri::command]
fn browser_open(app: State<App>, url: String) -> Res {
    local::open_browser(&app.paths, &url)
}

#[tauri::command(async)]
fn update_check(app: State<App>) -> Res {
    let r = update::check(&app.paths);
    match &r {
        // Only a release whose signature was verified here can be applied later.
        Ok(v) => *app.verified_release.lock().unwrap() = v.get("release").filter(|_| v["available"] == true).cloned(),
        Err(e) => update::log(&app.paths, &format!("check failed: {}", e["diagnostic"]["details_summary"])),
    }
    r
}

/// "Pode atualizar": only at a safe point (no job or recording on this station
/// and, on the host, no job claimed/running on any station); download the
/// release verified by `update_check` (never data from the page); start the
/// verified installer, then stop the children cleanly and exit. The installer
/// waits for them, keeps the previous version and reopens the app.
#[tauri::command(async)]
fn update_apply(handle: tauri::AppHandle, app: State<App>, token: Option<String>) -> Res {
    let busy = |why: &str| diag_err("UPDATE-BUSY", "The update is waiting: a run or recording is in progress.", why);
    if app.paths.agent_status().and_then(|s| s["job_id"].as_str().map(String::from)).is_some() || app.recording.lock().unwrap().is_some() {
        return Err(busy("run or recording on this station"));
    }
    if app.paths.host_config().is_some() {
        // This computer hosts the team: stopping the Core would interrupt jobs of other stations.
        let client = core_api::Client::from_host(&app.paths, token).map_err(|e| busy(&e))?;
        let jobs = client.call("GET", "/api/v1/jobs", &json!({}))?;
        let active = jobs.as_array().map(|a| a.iter().filter(|j| matches!(j["state"].as_str(), Some("claimed" | "running"))).count()).unwrap_or(0);
        if active > 0 {
            return Err(busy(&format!("{active} run(s) in progress in the team")));
        }
    }
    let release = app.verified_release.lock().unwrap().clone()
        .ok_or_else(|| diag_err("UPDATE-INVALID", "No verified update to apply.", "check for updates again"))?;
    let installer = update::download(&app.paths, &release)?;
    use std::os::windows::process::CommandExt;
    std::process::Command::new(&installer)
        .args(["--quiet", "--relaunch", "--wait-pid", &std::process::id().to_string()])
        .current_dir(installer.parent().unwrap_or(&app.paths.data_root)) // not the install folder
        .creation_flags(0x0000_0008 | 0x0000_0200) // DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        .spawn()
        .map_err(|e| diag_err("UPDATE-DOWNLOAD", "The update installer could not be started.", &e.to_string()))?;
    app.procs.lock().unwrap().stop_all(); // only after the installer is running
    handle.exit(0);
    Ok(json!({"handed_over": true}))
}

pub fn run() {
    let paths = paths::Paths::resolve();
    let app = tauri::Builder::default()
        .manage(App { paths, procs: Mutex::new(procs::Supervisor::default()), recording: Mutex::new(None), verified_release: Mutex::new(None) })
        .setup(|app| {
            let st = app.state::<App>();
            // Start what this computer is configured for (no manual service/agent start).
            let mut s = st.procs.lock().unwrap();
            if st.paths.host_config().is_some() {
                let _ = s.start_core(&st.paths, None);
            }
            if st.paths.connection().is_some() {
                let _ = s.start_agent(&st.paths);
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            app_info, host_create, host_start, station_join, agent_start, api, runner_local, record_start, record_stop,
            record_compile, update_check, update_apply, browser_open, storage_local, pick_file, open_report_folder
        ])
        .build(tauri::generate_context!())
        .expect("tauri app");
    app.run(|handle, ev| {
        if let RunEvent::Exit = ev {
            let st = handle.state::<App>();
            if let Some(r) = st.recording.lock().unwrap().take() {
                let _ = r.stop(true);
            }
            st.procs.lock().unwrap().stop_all();
        }
    });
}
