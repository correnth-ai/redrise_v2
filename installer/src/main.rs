//! RedRise per-user installer (P10), one self-contained file:
//! `[setup stub][zip payload][trailer: "RRSETUP1" | zip_len u64 LE | sha256(zip)]`.
//!
//! install: verify payload hash -> refuse while RedRise runs from the target
//! -> extract to a staging folder -> verify every file against the payload
//! manifest -> atomic swap (previous version kept for recovery) -> Start Menu
//! shortcut + HKCU uninstall entry. Data under %LOCALAPPDATA%\RedRise is never
//! touched. Any failure before the swap leaves the existing install unchanged.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

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

struct Opts {
    quiet: bool,
    relaunch: bool,
    wait_pid: Option<u32>,
    root: PathBuf,
    data: PathBuf,
    isolated: bool, // --install-root (tests only)
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
fn payload(exe: &[u8]) -> Result<Option<(usize, Vec<u8>)>, String> {
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

fn extract_verified(zip: &[u8], staging: &Path) -> Result<Value, String> {
    let mut z = zip::ZipArchive::new(Cursor::new(zip)).map_err(|e| e.to_string())?;
    let mut man = String::new();
    z.by_name("manifest.json").map_err(|e| e.to_string())?.read_to_string(&mut man).map_err(|e| e.to_string())?;
    let manifest: Value = serde_json::from_slice(no_bom(man.as_bytes())).map_err(|e| e.to_string())?;
    let expected: std::collections::HashMap<String, String> = manifest["files"].as_array().ok_or("manifest without files")?
        .iter().map(|f| (f["path"].as_str().unwrap_or("").to_string(), f["sha256"].as_str().unwrap_or("").to_string())).collect();
    for i in 0..z.len() {
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

fn install(o: &Opts, stub_len: usize, me: &[u8], zip: &[u8]) -> Result<Value, String> {
    let parent = o.root.parent().ok_or("invalid target")?.to_path_buf();
    fs::create_dir_all(&parent).map_err(|e| e.to_string())?;
    wait_free(&o.root, o.wait_pid)?;
    let staging = parent.join(format!("{DIR_NAME}.new-{}", now()));
    let manifest = match extract_verified(zip, &staging) {
        Ok(m) => m,
        Err(e) => {
            let _ = fs::remove_dir_all(&staging);
            return Err(e);
        }
    };
    // Uninstaller (stub only, no payload) outside the manifest-verified binaries.
    fs::write(staging.join("uninstall.exe"), &me[..stub_len]).map_err(|e| e.to_string())?;
    let previous = parent.join(format!("{DIR_NAME}.previous"));
    let had_previous = o.root.exists();
    if had_previous {
        if previous.exists() {
            fs::remove_dir_all(&previous).map_err(|e| format!("old previous version: {e}"))?;
        }
        if let Err(e) = fs::rename(&o.root, &previous) {
            let _ = fs::remove_dir_all(&staging);
            return Err(format!("could not replace the current installation (file in use?): {e}"));
        }
    }
    if let Err(e) = fs::rename(&staging, &o.root) {
        if had_previous {
            let _ = fs::rename(&previous, &o.root); // rollback
        }
        let _ = fs::remove_dir_all(&staging);
        return Err(format!("version swap failed; previous version restored: {e}"));
    }
    let version = manifest["app_version"].as_str().unwrap_or("0.0.0").to_string();
    // An isolated test root never touches the real Start Menu entry or uninstall key.
    let lnk = if o.isolated { None } else { Some(shortcut(&o.root).map_err(|e| format!("instalado, mas o atalho falhou: {e}"))?) };
    if !o.isolated {
        let uninstall = format!("\"{}\" --uninstall", o.root.join("uninstall.exe").display());
        win::reg_set(&[("DisplayName", "RedRise"), ("DisplayVersion", &version), ("Publisher", "Correnth"),
                       ("InstallLocation", &o.root.to_string_lossy()), ("UninstallString", &uninstall),
                       ("DisplayIcon", &o.root.join(APP_EXE).to_string_lossy())],
                     &[("NoModify", 1), ("NoRepair", 1)])?;
    }
    Ok(json!({"installed": version, "install_root": o.root, "previous_kept": had_previous, "shortcut": lnk,
              "files": manifest["file_count"], "data_root_untouched": o.data}))
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
fn pt_error(e: &str) -> String {
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
        ("version swap failed; previous version restored", "troca de versão falhou; versão anterior restaurada"),
        ("no previous version kept", "não há versão anterior guardada"),
        ("this file does not contain a RedRise package", "este arquivo não contém um pacote do RedRise"),
    ];
    MAP.iter().fold(e.to_string(), |acc, (en, pt)| acc.replace(en, pt))
}

fn log_result(o: &Opts, v: &Value) {
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
    let o = Opts {
        quiet: has("--quiet"),
        relaunch: has("--relaunch"),
        wait_pid: val("--wait-pid").and_then(|s| s.parse().ok()),
        // --install-root is for isolated tests only; the product default is fixed (U25/U26-INSTALL).
        root: val("--install-root").map(PathBuf::from).unwrap_or_else(|| lad.join("Programs").join(DIR_NAME)),
        data: lad.join("RedRise"),
        isolated: val("--install-root").is_some(),
    };
    let me = std::env::current_exe().and_then(fs::read).unwrap_or_default();
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
            Ok(Some((stub, zip))) => {
                if o.quiet || win::ask("Instalar RedRise", &format!("Instalar o RedRise para este usuário em\n{}?\n\nNenhuma permissão de administrador é necessária.", o.root.display())) {
                    install(&o, stub, &me, &zip)
                } else {
                    Ok(json!({"cancelled": true}))
                }
            }
        }
    };
    let record = match &result { Ok(v) => json!({"ok": true, "at": now(), "result": v}), Err(e) => json!({"ok": false, "at": now(), "error": e}) };
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
                win::tell("RedRise", &format!("A instalação não foi concluída.\n\n{}\n\nA instalação anterior, se havia, foi mantida.", pt_error(&e)), true);
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
