//! RedRise per-user installer (P10), one self-contained file:
//! `[setup stub][zip payload][trailer: "RRSETUP1" | zip_len u64 LE | sha256(zip)]`.
//!
//! install: verify payload hash -> refuse while RedRise runs from the target
//! -> extract to a staging folder -> verify every file against the payload
//! manifest -> atomic swap (previous version kept for recovery) -> Start Menu
//! shortcut + HKCU uninstall entry. Data under %LOCALAPPDATA%\RedRise is never
//! touched, except the non-secret setup intent of a new install
//! (`install/setup-intent.json`, role server|station, consumed by the app).
//! Any failure or cancellation before the swap leaves the existing install unchanged. A failure is reported with its
//! phase (`Failure`): before the swap nothing changed; at the swap the previous version is put back and that is
//! CHECKED before saying so; after the swap the new version is installed and the message says which step failed.
//!
//! Opened by a person (no `--quiet`), the InstallRS wizard (`wizard.rs`) shows
//! the pages and runs `install` with its progress and Cancel; `--quiet` (the
//! in-app update, tests) keeps the same contract as before, without a window.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod wizard;

use std::fs;
use std::io::{Cursor, Read, Write};
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use serde_json::{json, Value};
use sha2::{Digest, Sha256};

const MAGIC: &[u8; 8] = b"RRSETUP1";
const TRAILER: usize = 8 + 8 + 32;
const DIR_NAME: &str = "@redrise";
const APP_EXE: &str = "RedRise.exe";
const UNINSTALL_KEY: &str = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\RedRise";

mod win {
    use std::path::{Path, PathBuf};
    use windows_sys::Win32::Foundation::{CloseHandle, HANDLE};
    use windows_sys::Win32::System::Com::CoTaskMemFree;
    use windows_sys::Win32::System::Diagnostics::ToolHelp::{
        CreateToolhelp32Snapshot, Process32FirstW, Process32NextW, PROCESSENTRY32W, TH32CS_SNAPPROCESS,
    };
    use windows_sys::Win32::System::Registry::*;
    use windows_sys::Win32::System::Threading::{OpenProcess, QueryFullProcessImageNameW, PROCESS_QUERY_LIMITED_INFORMATION};
    use windows_sys::Win32::UI::Shell::{SHGetKnownFolderPath, FOLDERID_LocalAppData, FOLDERID_Programs};
    use windows_sys::Win32::UI::WindowsAndMessaging::{MessageBoxW, IDYES, MB_ICONERROR, MB_ICONINFORMATION, MB_YESNO, MB_ICONQUESTION};

    pub fn wide(s: &str) -> Vec<u16> {
        s.encode_utf16().chain(std::iter::once(0)).collect()
    }

    fn known(id: &windows_sys::core::GUID) -> PathBuf {
        unsafe {
            let mut p: *mut u16 = std::ptr::null_mut();
            if SHGetKnownFolderPath(id, 0, std::ptr::null_mut(), &mut p) != 0 || p.is_null() {
                return PathBuf::new();
            }
            let mut n = 0;
            while *p.add(n) != 0 {
                n += 1;
            }
            let s = String::from_utf16_lossy(std::slice::from_raw_parts(p, n));
            CoTaskMemFree(p as _);
            PathBuf::from(s)
        }
    }
    pub fn local_app_data() -> PathBuf {
        known(&FOLDERID_LocalAppData)
    }
    pub fn start_menu_programs() -> PathBuf {
        known(&FOLDERID_Programs)
    }

    pub fn ask(title: &str, text: &str) -> bool {
        unsafe { MessageBoxW(std::ptr::null_mut(), wide(text).as_ptr(), wide(title).as_ptr(), MB_YESNO | MB_ICONQUESTION) == IDYES }
    }
    pub fn tell(title: &str, text: &str, error: bool) {
        unsafe {
            MessageBoxW(std::ptr::null_mut(), wide(text).as_ptr(), wide(title).as_ptr(), if error { MB_ICONERROR } else { MB_ICONINFORMATION });
        }
    }

    /// Processes whose image lives under `root` (e.g. RedRise.exe, the private python.exe, postgres.exe).
    pub fn processes_under(root: &Path) -> Vec<(u32, PathBuf)> {
        let mut out = Vec::new();
        let root_l = root.to_string_lossy().to_lowercase();
        unsafe {
            let snap: HANDLE = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
            if snap.is_null() || snap as isize == -1 {
                return out;
            }
            let mut e: PROCESSENTRY32W = std::mem::zeroed();
            e.dwSize = std::mem::size_of::<PROCESSENTRY32W>() as u32;
            let mut ok = Process32FirstW(snap, &mut e) != 0;
            while ok {
                let h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, e.th32ProcessID);
                if !h.is_null() {
                    let mut buf = [0u16; 1024];
                    let mut n = buf.len() as u32;
                    if QueryFullProcessImageNameW(h, 0, buf.as_mut_ptr(), &mut n) != 0 {
                        let p = String::from_utf16_lossy(&buf[..n as usize]);
                        if p.to_lowercase().starts_with(&(root_l.clone() + "\\")) {
                            out.push((e.th32ProcessID, PathBuf::from(p)));
                        }
                    }
                    CloseHandle(h);
                }
                ok = Process32NextW(snap, &mut e) != 0;
            }
            CloseHandle(snap);
        }
        out
    }

    pub fn reg_set(values: &[(&str, &str)], dword: &[(&str, u32)]) -> Result<(), String> {
        unsafe {
            let mut k: HKEY = std::ptr::null_mut();
            if RegCreateKeyExW(HKEY_CURRENT_USER, wide(super::UNINSTALL_KEY).as_ptr(), 0, std::ptr::null(), 0, KEY_WRITE,
                               std::ptr::null(), &mut k, std::ptr::null_mut()) != 0 {
                return Err("RegCreateKeyExW".into());
            }
            for (n, v) in values {
                let w = wide(v);
                RegSetValueExW(k, wide(n).as_ptr(), 0, REG_SZ, w.as_ptr() as *const u8, (w.len() * 2) as u32);
            }
            for (n, v) in dword {
                RegSetValueExW(k, wide(n).as_ptr(), 0, REG_DWORD, v as *const u32 as *const u8, 4);
            }
            RegCloseKey(k);
        }
        Ok(())
    }
    pub fn reg_delete() {
        unsafe {
            RegDeleteKeyW(HKEY_CURRENT_USER, wide(super::UNINSTALL_KEY).as_ptr());
        }
    }
}

#[derive(Clone)]
pub struct Opts {
    quiet: bool,
    relaunch: bool,
    wait_pid: Option<u32>,
    pub root: PathBuf,
    pub data: PathBuf,
    isolated: bool, // --install-root (tests only)
    /// Setup intent of a new install: from the wizard, or `--role` (quiet tests). Never a secret.
    pub role: Option<String>,
    /// False for an isolated test root without `--data-root`: it never writes into the real data folder.
    intent_allowed: bool,
    /// `--test-fail-at <point>`, honoured only with `--install-root` (copies in the lab): before-swap, swap, restore,
    /// after-swap or intent. Proves each failure report on a copy; a real install never reads it.
    fail_at: Option<String>,
}

pub const INTENT_SCHEMA: &str = "redrise.setup-intent/1";
pub const ROLES: [&str; 2] = ["server", "station"];

/// This computer already has a team configuration (server or station): its role is kept, never asked again.
pub fn configured(data: &Path) -> bool {
    data.join("host").join("host.json").is_file() || data.join("agent").join("connection.json").is_file()
}

fn intent_path(data: &Path) -> PathBuf {
    data.join("install").join("setup-intent.json")
}

/// The role chosen by an earlier run that the app has not consumed yet (installed, setup not finished).
pub fn read_intent(data: &Path) -> Option<String> {
    let v: Value = serde_json::from_slice(&fs::read(intent_path(data)).ok()?).ok()?;
    let role = v["role"].as_str()?;
    (v["schema"] == INTENT_SCHEMA && ROLES.contains(&role)).then(|| role.to_string())
}

fn write_intent(data: &Path, role: &str, version: &str) -> Result<(), String> {
    let p = intent_path(data);
    fs::create_dir_all(p.parent().unwrap()).map_err(|e| e.to_string())?;
    let tmp = p.with_extension("json.tmp");
    let body = json!({"schema": INTENT_SCHEMA, "role": role, "chosen_at": now(), "installer_version": version});
    fs::write(&tmp, serde_json::to_vec_pretty(&body).unwrap_or_default()).map_err(|e| e.to_string())?;
    fs::rename(&tmp, &p).map_err(|e| e.to_string())
}

/// Progress of an install: a status line and a fraction (0..1); `cancelled` is asked before the commit point only.
pub struct Progress<'a> {
    pub report: &'a dyn Fn(&str, f64),
    pub cancelled: &'a dyn Fn() -> bool,
}

const CANCELLED: &str = "installation cancelled before any change";

/// A failed install, by phase, as it really ended (PROCESS-ACTIONS-20261111 item 4.2): the JSON record and the person's
/// message say the same thing. `installed_now` is the version found in the install folder afterwards (read from its
/// manifest, never assumed); `previous_kept` is the folder of the previous version when it still exists.
#[derive(Clone, Debug)]
pub struct Failure {
    pub phase: &'static str, // "before_swap" | "swap" | "after_swap"
    pub step: &'static str,  // what failed: "check", "swap", "shortcut", "uninstall_entry", "setup_intent", "cancelled"
    pub error: String,
    pub recovery_error: Option<String>,
    pub installed_now: Option<String>,
    pub previous_kept: Option<PathBuf>,
    pub root: PathBuf,
}

fn installed_version(root: &Path) -> Option<String> {
    // The layout manifest is UTF-8 with BOM (written by Windows PowerShell): read it as the package check does.
    let v: Value = serde_json::from_slice(no_bom(&fs::read(root.join("manifest.json")).ok()?)).ok()?;
    v["app_version"].as_str().map(str::to_string)
}

impl Failure {
    fn before(o: &Opts, error: String) -> Self {
        let step = if error == CANCELLED { "cancelled" } else { "check" };
        Failure { phase: "before_swap", step, error, recovery_error: None, installed_now: installed_version(&o.root), previous_kept: None, root: o.root.clone() }
    }
    pub fn to_json(&self) -> Value {
        json!({"phase": self.phase, "step": self.step, "error": self.error, "recovery_error": self.recovery_error,
               "installed_now": self.installed_now, "previous_kept": self.previous_kept, "install_root": self.root,
               "data_touched": self.step == "setup_intent"})
    }
    fn kept(&self) -> String {
        self.previous_kept.as_deref().unwrap_or(Path::new("?")).display().to_string()
    }
    /// English, for the JSON record and logs.
    pub fn message(&self) -> String {
        let now = self.installed_now.as_deref();
        match (self.phase, &self.recovery_error) {
            ("before_swap", _) if self.step == "cancelled" => CANCELLED.to_string(),
            ("before_swap", _) => format!("{}. Nothing was changed: {}; your data were not touched.", self.error,
                                          now.map(|v| format!("version {v} stays installed")).unwrap_or("nothing was installed".into())),
            ("swap", None) => format!("version swap failed: {}. {}; your data were not touched.", self.error,
                                      now.map(|v| format!("The previous version {v} was put back and checked")).unwrap_or("Nothing was installed".into())),
            ("swap", Some(r)) => format!("version swap failed: {}; putting the previous version back also failed: {r}. Nothing is installed in {} \
                                          now; the previous version is kept in {}. Your data were not touched. Run this installer again.",
                                         self.error, self.root.display(), self.kept()),
            _ => format!("version {} is installed, but {} failed: {}. {}Your data were not touched{}.", now.unwrap_or("?"), self.step_en(), self.error,
                         self.previous_kept.as_ref().map(|p| format!("The previous version is kept in {} for a rollback. ", p.display())).unwrap_or_default(),
                         if self.step == "setup_intent" { ", except the setup intent file that was not saved" } else { "" }),
        }
    }
    fn step_en(&self) -> &'static str {
        match self.step { "shortcut" => "the Start Menu shortcut", "uninstall_entry" => "the uninstall entry", _ => "saving the server/station choice" }
    }
    /// pt-BR, for the person: what happened, what is installed now, the data, and what to do next.
    pub fn pt(&self) -> String {
        let now = self.installed_now.as_deref();
        match (self.phase, &self.recovery_error) {
            ("before_swap", _) if self.step == "cancelled" => pt_error(CANCELLED),
            ("before_swap", _) => format!("{}.\n\nNada foi alterado: {}. Seus dados não foram tocados.\n\nCorrija o motivo acima e abra o instalador de novo.",
                                          pt_error(&self.error), now.map(|v| format!("a versão {v} continua instalada")).unwrap_or("nada foi instalado".into())),
            ("swap", None) => format!("A troca de versão falhou: {}.\n\n{}. Seus dados não foram tocados.\n\n\
                                       Feche o que estiver usando a pasta do RedRise e abra o instalador de novo.",
                                      pt_error(&self.error), now.map(|v| format!("A versão anterior ({v}) foi recolocada e conferida")).unwrap_or("Nada foi instalado".into())),
            ("swap", Some(r)) => format!("A troca de versão falhou: {}.\nRecolocar a versão anterior também falhou: {r}.\n\n\
                                          Não há RedRise instalado em {} agora; a versão anterior está guardada em {}. Seus dados não foram tocados.\n\n\
                                          Abra este instalador de novo para instalar a versão nova.",
                                         pt_error(&self.error), self.root.display(), self.kept()),
            _ => {
                let (what, next) = match self.step {
                    "shortcut" => ("o atalho no menu Iniciar", format!("Abra o RedRise por {}, ou abra o instalador de novo para criar o atalho.", self.root.join(APP_EXE).display())),
                    "uninstall_entry" => ("o registro de desinstalação", "Abra o instalador de novo para criar o registro.".to_string()),
                    _ => ("gravar a escolha servidor/estação", "Abra o RedRise: ele pergunta de novo como este computador será usado.".to_string()),
                };
                format!("A versão {} foi instalada, mas {what} falhou: {}.\n\n{}Seus dados não foram tocados.\n\n{next}", now.unwrap_or("?"), self.error,
                        self.previous_kept.as_ref().map(|p| format!("A versão anterior continua guardada em {} para voltar, se precisar. ", p.display())).unwrap_or_default())
            }
        }
    }
}

fn now() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0)
}

/// The layout manifest is written by Windows PowerShell (UTF-8 with BOM).
fn no_bom(b: &[u8]) -> &[u8] {
    b.strip_prefix(&[0xEF, 0xBB, 0xBF]).unwrap_or(b)
}

fn hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{x:02x}")).collect()
}

/// (stub length, zip bytes) when this exe carries a verified payload.
pub fn payload(exe: &[u8]) -> Result<Option<(usize, Vec<u8>)>, String> {
    if exe.len() < TRAILER || &exe[exe.len() - TRAILER..exe.len() - 40] != MAGIC {
        return Ok(None);
    }
    let t = &exe[exe.len() - TRAILER..];
    let zlen = u64::from_le_bytes(t[8..16].try_into().unwrap()) as usize;
    if zlen + TRAILER > exe.len() {
        return Err("pacote truncado".into());
    }
    let start = exe.len() - TRAILER - zlen;
    let zip = exe[start..exe.len() - TRAILER].to_vec();
    if hex(&Sha256::digest(&zip)) != hex(&t[16..48]) {
        return Err("corrupted package: content SHA-256 does not match".into());
    }
    Ok(Some((start, zip)))
}

fn pack(layout: &Path, out: &Path) -> Result<Value, String> {
    let me = fs::read(std::env::current_exe().map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    let stub = match payload(&me)? { Some((n, _)) => me[..n].to_vec(), None => me };
    let manifest: Value = serde_json::from_slice(no_bom(&fs::read(layout.join("manifest.json")).map_err(|e| format!("manifest: {e}"))?))
        .map_err(|e| e.to_string())?;
    let mut buf = Cursor::new(Vec::new());
    {
        let mut z = zip::ZipWriter::new(&mut buf);
        let o = zip::write::SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated).large_file(true);
        let mut files: Vec<String> = manifest["files"].as_array().ok_or("manifest without files")?
            .iter().filter_map(|f| f["path"].as_str().map(String::from)).collect();
        files.push("manifest.json".into());
        for rel in files {
            z.start_file(&rel, o).map_err(|e| e.to_string())?;
            let mut f = fs::File::open(layout.join(&rel)).map_err(|e| format!("{rel}: {e}"))?;
            std::io::copy(&mut f, &mut z).map_err(|e| e.to_string())?;
        }
        z.finish().map_err(|e| e.to_string())?;
    }
    let zip = buf.into_inner();
    let mut f = fs::File::create(out).map_err(|e| e.to_string())?;
    f.write_all(&stub).and_then(|_| f.write_all(&zip)).and_then(|_| f.write_all(MAGIC))
        .and_then(|_| f.write_all(&(zip.len() as u64).to_le_bytes())).and_then(|_| f.write_all(&Sha256::digest(&zip)))
        .map_err(|e| e.to_string())?;
    drop(f);
    Ok(json!({"out": out, "sha256": hex(&Sha256::digest(fs::read(out).map_err(|e| e.to_string())?)),
              "payload_sha256": hex(&Sha256::digest(&zip)), "app_version": manifest["app_version"]}))
}

fn wait_free(root: &Path, wait_pid: Option<u32>) -> Result<(), String> {
    let t0 = Instant::now();
    loop {
        let me = std::process::id(); // uninstall.exe itself runs from the install folder
        let busy: Vec<_> = win::processes_under(root).into_iter().filter(|(pid, _)| *pid != me).collect();
        if busy.is_empty() {
            return Ok(());
        }
        if wait_pid.is_none() || t0.elapsed() > Duration::from_secs(90) {
            let names: Vec<String> = busy.iter().map(|(_, p)| p.file_name().unwrap_or_default().to_string_lossy().into()).collect();
            return Err(format!("RedRise is still running ({}). Close the app and try again.", names.join(", ")));
        }
        std::thread::sleep(Duration::from_millis(500));
    }
}

fn extract_verified(zip: &[u8], staging: &Path, pr: &Progress) -> Result<Value, String> {
    let mut z = zip::ZipArchive::new(Cursor::new(zip)).map_err(|e| e.to_string())?;
    let mut man = String::new();
    z.by_name("manifest.json").map_err(|e| e.to_string())?.read_to_string(&mut man).map_err(|e| e.to_string())?;
    let manifest: Value = serde_json::from_slice(no_bom(man.as_bytes())).map_err(|e| e.to_string())?;
    let expected: std::collections::HashMap<String, String> = manifest["files"].as_array().ok_or("manifest without files")?
        .iter().map(|f| (f["path"].as_str().unwrap_or("").to_string(), f["sha256"].as_str().unwrap_or("").to_string())).collect();
    let total = z.len().max(1);
    for i in 0..z.len() {
        if (pr.cancelled)() {
            return Err(CANCELLED.into());
        }
        if i % 25 == 0 {
            // 5% .. 90% of the bar: copying and checking the files is most of the work.
            (pr.report)(&format!("Copiando e conferindo arquivos ({} de {})", i + 1, total), 0.05 + 0.85 * i as f64 / total as f64);
        }
        let mut e = z.by_index(i).map_err(|e| e.to_string())?;
        let rel = e.enclosed_name().ok_or("invalid path in package")?.to_path_buf();
        let rel_s = rel.to_string_lossy().replace('\\', "/");
        if rel_s != "manifest.json" && !expected.contains_key(&rel_s) {
            return Err(format!("file not declared in package: {rel_s}"));
        }
        let dst = staging.join(&rel);
        fs::create_dir_all(dst.parent().unwrap()).map_err(|e| e.to_string())?;
        let mut data = Vec::with_capacity(e.size() as usize);
        e.read_to_end(&mut data).map_err(|e| e.to_string())?;
        if rel_s != "manifest.json" && hex(&Sha256::digest(&data)) != expected[&rel_s] {
            return Err(format!("content mismatch: {rel_s}"));
        }
        fs::write(&dst, &data).map_err(|e| format!("{rel_s}: {e}"))?;
    }
    for p in expected.keys() {
        if !staging.join(p).is_file() {
            return Err(format!("arquivo ausente no pacote: {p}"));
        }
    }
    fs::write(staging.join("manifest.json"), man.as_bytes()).map_err(|e| e.to_string())?;
    Ok(manifest)
}

fn shortcut(root: &Path) -> Result<PathBuf, String> {
    let lnk = win::start_menu_programs().join("RedRise.lnk");
    let mut l = mslnk::ShellLink::new(root.join(APP_EXE)).map_err(|e| e.to_string())?;
    l.set_working_dir(Some(root.to_string_lossy().into()));
    l.set_icon_location(Some(root.join(APP_EXE).to_string_lossy().into()));
    l.create_lnk(&lnk).map_err(|e| e.to_string())?;
    Ok(lnk)
}

pub fn install(o: &Opts, stub_len: usize, me: &[u8], zip: &[u8], pr: &Progress) -> Result<Value, Failure> {
    let staged = prepare(o, stub_len, me, zip, pr).map_err(|e| Failure::before(o, e))?;
    let (staging, manifest) = staged;
    let fail = |point: &str| o.fail_at.as_deref() == Some(point);
    (pr.report)("Trocando a versão instalada", 0.92);
    let parent = o.root.parent().unwrap().to_path_buf();
    let previous = parent.join(format!("{DIR_NAME}.previous"));
    let had_previous = o.root.exists();
    if had_previous {
        if previous.exists() {
            if let Err(e) = fs::remove_dir_all(&previous) {
                let _ = fs::remove_dir_all(&staging);
                return Err(Failure::before(o, format!("old previous version: {e}")));
            }
        }
        if let Err(e) = fs::rename(&o.root, &previous) {
            let _ = fs::remove_dir_all(&staging);
            return Err(Failure::before(o, format!("could not replace the current installation (file in use?): {e}")));
        }
    }
    let swapped = if fail("swap") || fail("restore") { Err(std::io::Error::other("injected failure (test)")) } else { fs::rename(&staging, &o.root) };
    if let Err(e) = swapped {
        // Put the previous version back, and only say so once its manifest is read again from the install folder.
        let recovery_error = if !had_previous { None } else if fail("restore") { Some("injected failure (test)".to_string()) } else {
            fs::rename(&previous, &o.root).err().map(|r| r.to_string())
        };
        let _ = fs::remove_dir_all(&staging);
        let installed_now = installed_version(&o.root);
        let recovery_error = recovery_error.or_else(|| (had_previous && installed_now.is_none()).then(|| "previous version not found after restoring".to_string()));
        return Err(Failure { phase: "swap", step: "swap", error: e.to_string(), recovery_error, installed_now,
                             previous_kept: previous.is_dir().then(|| previous.clone()), root: o.root.clone() });
    }
    let version = manifest["app_version"].as_str().unwrap_or("0.0.0").to_string();
    let after = |step: &'static str, error: String| Failure { phase: "after_swap", step, error, recovery_error: None,
        installed_now: installed_version(&o.root), previous_kept: previous.is_dir().then(|| previous.clone()), root: o.root.clone() };
    (pr.report)("Criando o atalho e o registro de desinstalação", 0.96);
    if fail("after-swap") {
        return Err(after("shortcut", "injected failure (test)".into()));
    }
    // An isolated test root never touches the real Start Menu entry or uninstall key.
    let lnk = if o.isolated { None } else { Some(shortcut(&o.root).map_err(|e| after("shortcut", e))?) };
    if !o.isolated {
        let uninstall = format!("\"{}\" --uninstall", o.root.join("uninstall.exe").display());
        win::reg_set(&[("DisplayName", "RedRise"), ("DisplayVersion", &version), ("Publisher", "Correnth"),
                       ("InstallLocation", &o.root.to_string_lossy()), ("UninstallString", &uninstall),
                       ("DisplayIcon", &o.root.join(APP_EXE).to_string_lossy())],
                     &[("NoModify", 1), ("NoRepair", 1)]).map_err(|e| after("uninstall_entry", e))?;
    }
    // Setup intent: only for a computer without a team configuration. An update or a reinstall keeps the role it has
    // (server or station) and never asks or converts it. Written after the swap: a cancelled install leaves none.
    let existing = configured(&o.data);
    let intent = match (&o.role, existing) {
        (Some(r), false) if ROLES.contains(&r.as_str()) && o.intent_allowed => {
            let w = if fail("intent") { Err("injected failure (test)".to_string()) } else { write_intent(&o.data, r, &version) };
            w.map_err(|e| after("setup_intent", e))?;
            Some(r.clone())
        }
        _ => None,
    };
    (pr.report)("Concluído", 1.0);
    Ok(json!({"installed": version, "install_root": o.root, "previous_kept": had_previous, "shortcut": lnk,
              "files": manifest["file_count"], "data_root_untouched": o.data,
              "configuration": if !o.intent_allowed { "not checked (isolated test root without --data-root)" }
                               else if existing { "existing (role kept)" } else { "none yet" }, "setup_intent": intent}))
}

/// Everything before the swap: nothing in the install folder changes here. Returns the verified staging folder.
fn prepare(o: &Opts, stub_len: usize, me: &[u8], zip: &[u8], pr: &Progress) -> Result<(PathBuf, Value), String> {
    let parent = o.root.parent().ok_or("invalid target")?.to_path_buf();
    fs::create_dir_all(&parent).map_err(|e| e.to_string())?;
    (pr.report)("Verificando se o RedRise está fechado", 0.02);
    wait_free(&o.root, o.wait_pid)?;
    let staging = parent.join(format!("{DIR_NAME}.new-{}", now()));
    let manifest = match extract_verified(zip, &staging, pr) {
        Ok(m) => m,
        Err(e) => {
            let _ = fs::remove_dir_all(&staging);
            return Err(e);
        }
    };
    // Uninstaller (stub only, no payload) outside the manifest-verified binaries.
    if let Err(e) = fs::write(staging.join("uninstall.exe"), &me[..stub_len]) {
        let _ = fs::remove_dir_all(&staging);
        return Err(e.to_string());
    }
    // Last point where Cancelar is honored: from here the swap is completed or rolled back, never left half done.
    if (pr.cancelled)() || o.fail_at.as_deref() == Some("before-swap") {
        let _ = fs::remove_dir_all(&staging);
        return Err(if (pr.cancelled)() { CANCELLED.into() } else { "injected failure (test)".into() });
    }
    Ok((staging, manifest))
}

fn uninstall(o: &Opts) -> Result<Value, String> {
    wait_free(&o.root, o.wait_pid)?;
    if !o.isolated {
        let _ = fs::remove_file(win::start_menu_programs().join("RedRise.lnk"));
        win::reg_delete();
    }
    let parent = o.root.parent().unwrap().to_path_buf();
    let _ = fs::remove_dir_all(parent.join(format!("{DIR_NAME}.previous")));
    // The running uninstall.exe lives in the folder: remove everything else now,
    // the folder itself is removed by a detached cmd after this process exits.
    for e in fs::read_dir(&o.root).map_err(|e| e.to_string())?.flatten() {
        if e.file_name() != "uninstall.exe" {
            let p = e.path();
            let r = if p.is_dir() { fs::remove_dir_all(&p) } else { fs::remove_file(&p) };
            r.map_err(|err| format!("{}: {err}", p.display()))?;
        }
    }
    use std::os::windows::process::CommandExt;
    // raw_arg: cmd.exe does not understand the \" escaping of normal args.
    let _ = std::process::Command::new("cmd.exe")
        .raw_arg(format!("/d /c \"ping -n 3 127.0.0.1 >nul & rmdir /s /q \"{}\"\"", o.root.display()))
        .creation_flags(0x0800_0000).spawn();
    Ok(json!({"uninstalled": o.root, "data_kept": o.data}))
}

fn rollback(o: &Opts) -> Result<Value, String> {
    let parent = o.root.parent().unwrap().to_path_buf();
    let previous = parent.join(format!("{DIR_NAME}.previous"));
    if !previous.is_dir() {
        return Err("no previous version kept".into());
    }
    wait_free(&o.root, o.wait_pid)?;
    let failed = parent.join(format!("{DIR_NAME}.failed-{}", now()));
    fs::rename(&o.root, &failed).map_err(|e| e.to_string())?;
    if let Err(e) = fs::rename(&previous, &o.root) {
        let _ = fs::rename(&failed, &o.root);
        return Err(e.to_string());
    }
    let _ = fs::remove_dir_all(&failed);
    Ok(json!({"restored_previous": o.root}))
}

/// UI mask of the installer dialogs: errors are English (JSON output, logs);
/// the person sees them in pt-BR. Unknown messages are shown as they are.
pub fn pt_error(e: &str) -> String {
    const MAP: &[(&str, &str)] = &[
        ("corrupted package: content SHA-256 does not match", "pacote corrompido: SHA-256 do conteúdo não confere"),
        ("RedRise is still running", "o RedRise ainda está em execução"),
        ("Close the app and try again.", "Feche o aplicativo e tente novamente."),
        ("invalid path in package", "caminho inválido no pacote"),
        ("file not declared in package", "arquivo não declarado no pacote"),
        ("content mismatch", "conteúdo divergente"),
        ("invalid target", "destino inválido"),
        ("old previous version", "versão anterior antiga"),
        ("could not replace the current installation (file in use?)", "não foi possível substituir a instalação atual (arquivo em uso?)"),
        ("no previous version kept", "não há versão anterior guardada"),
        ("this file does not contain a RedRise package", "este arquivo não contém um pacote do RedRise"),
        ("installation cancelled before any change", "instalação cancelada antes de qualquer alteração; a instalação anterior, se havia, continua como estava"),
        ("installed, but the setup intent was not saved", "instalado, mas a escolha servidor/estação não foi gravada"),
    ];
    MAP.iter().fold(e.to_string(), |acc, (en, pt)| acc.replace(en, pt))
}

pub fn log_result(o: &Opts, v: &Value) {
    // Isolated tests log next to their own root, never over the real install record.
    let dir = if o.isolated { o.root.parent().map(|p| p.join("install-log")).unwrap_or_default() } else { o.data.join("install") };
    let _ = fs::create_dir_all(&dir);
    let _ = fs::write(dir.join("last-install.json"), serde_json::to_vec_pretty(v).unwrap_or_default());
}

fn main() {
    // GUI subsystem (no console window on double-click); when started from a
    // console (pack, tests), print there.
    unsafe {
        windows_sys::Win32::System::Console::AttachConsole(windows_sys::Win32::System::Console::ATTACH_PARENT_PROCESS);
    }
    // Never keep the install folder as current directory (inherited from the app
    // during an update, or uninstall.exe's own folder): Windows refuses to rename
    // or remove a folder that is a process's cwd.
    let _ = std::env::set_current_dir(std::env::temp_dir());
    let args: Vec<String> = std::env::args().skip(1).collect();
    // --rollback swaps the install folder, which cannot happen while this exe runs
    // from inside it (uninstall.exe): continue from a temporary copy.
    if args.iter().any(|a| a == "--rollback") && !args.iter().any(|a| a == "--from-copy") {
        if let Ok(me) = std::env::current_exe() {
            let lad = win::local_app_data();
            let root = args.iter().position(|a| a == "--install-root").and_then(|i| args.get(i + 1)).map(PathBuf::from)
                .unwrap_or_else(|| lad.join("Programs").join(DIR_NAME));
            if me.starts_with(&root) {
                let copy = std::env::temp_dir().join(format!("redrise-rollback-{}.exe", now()));
                if fs::copy(&me, &copy).is_ok() {
                    // Hand over and exit: the copy waits for this process to leave the
                    // folder (--wait-pid) before swapping; its result goes to last-install.json.
                    let spawned = std::process::Command::new(&copy).args(&args)
                        .args(["--from-copy", "--wait-pid", &std::process::id().to_string()]).spawn();
                    std::process::exit(if spawned.is_ok() { 0 } else { 3 });
                }
            }
        }
    }
    let has = |f: &str| args.iter().any(|a| a == f);
    let val = |f: &str| args.iter().position(|a| a == f).and_then(|i| args.get(i + 1)).cloned();
    if args.first().map(String::as_str) == Some("pack") {
        let r = pack(Path::new(&val("--layout").unwrap_or_default()), Path::new(&val("--out").unwrap_or_default()));
        match r {
            Ok(v) => println!("{v}"),
            Err(e) => {
                eprintln!("pack failed: {e}");
                std::process::exit(1)
            }
        }
        return;
    }
    let lad = win::local_app_data();
    let isolated = val("--install-root").is_some();
    let o = Opts {
        quiet: has("--quiet"),
        relaunch: has("--relaunch"),
        wait_pid: val("--wait-pid").and_then(|s| s.parse().ok()),
        // --install-root is for isolated tests only; the product default is fixed (U25/U26-INSTALL).
        root: val("--install-root").map(PathBuf::from).unwrap_or_else(|| lad.join("Programs").join(DIR_NAME)),
        // --data-root only with --install-root (lab): the real data folder is never redirected.
        data: val("--data-root").filter(|_| isolated).map(PathBuf::from).unwrap_or_else(|| lad.join("RedRise")),
        isolated,
        role: val("--role").filter(|r| ROLES.contains(&r.as_str())),
        intent_allowed: !isolated || val("--data-root").is_some(),
        fail_at: val("--test-fail-at").filter(|_| isolated),
    };
    let me = std::env::current_exe().and_then(fs::read).unwrap_or_default();
    // Opened by a person: the wizard owns the whole run (pages, progress, result, opening the app).
    if !o.quiet && !has("--uninstall") && !has("--rollback") {
        if let Ok(Some((stub, zip))) = payload(&me) {
            let code = wizard::run(o, stub, me, zip);
            let _ = std::io::stdout().flush();
            std::process::exit(code);
        }
    }
    let mut failure: Option<Failure> = None;
    let result: Result<Value, String> = if has("--uninstall") {
        if o.quiet || win::ask("RedRise", "Remover o RedRise deste usuário? Seus dados e rotinas em %LOCALAPPDATA%\\RedRise são mantidos.") {
            uninstall(&o)
        } else {
            Ok(json!({"cancelled": true}))
        }
    } else if has("--rollback") {
        rollback(&o)
    } else {
        match payload(&me) {
            Err(e) => Err(e),
            Ok(None) => Err("this file does not contain a RedRise package".into()),
            // Quiet (in-app update, tests): no window, the same contract as before the wizard.
            Ok(Some((stub, zip))) => install(&o, stub, &me, &zip, &Progress { report: &|_, _| {}, cancelled: &|| false })
                .map_err(|f| { let m = f.message(); failure = Some(f); m }),
        }
    };
    let record = match &result {
        Ok(v) => json!({"ok": true, "at": now(), "result": v}),
        Err(e) => json!({"ok": false, "at": now(), "error": e, "failure": failure.as_ref().map(Failure::to_json)}),
    };
    log_result(&o, &record);
    println!("{record}");
    match result {
        Ok(v) => {
            if !o.quiet && v.get("cancelled").is_none() {
                win::tell("RedRise", if has("--uninstall") { "RedRise removido." } else { "RedRise instalado." }, false);
            }
            if o.relaunch && v.get("installed").is_some() {
                let _ = std::process::Command::new(o.root.join(APP_EXE)).current_dir(&o.root).spawn();
            }
        }
        Err(e) => {
            if !o.quiet {
                let text = failure.as_ref().map(Failure::pt).unwrap_or_else(|| pt_error(&e));
                win::tell("RedRise", &format!("A instalação não foi concluída como esperado.\n\n{text}"), true);
            }
            // Update path: the app closed for the update; reopen the version still installed.
            if o.relaunch && o.root.join(APP_EXE).is_file() {
                let _ = std::process::Command::new(o.root.join(APP_EXE)).current_dir(&o.root).spawn();
            }
            std::process::exit(3);
        }
    }
    let _ = std::io::stdout().flush();
}
