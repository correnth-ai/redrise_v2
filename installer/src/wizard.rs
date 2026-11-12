//! "Instalar RedRise": the InstallRS wizard (pinned 0.1.1, user decision of PROCESS-LIST-INSTALLER-20261110 item 2)
//! shown when a person opens the installer. InstallRS draws the pages, the progress bar and Cancelar; the work stays in
//! `install()` of this crate (payload check, staging, per-file verification, atomic swap, shortcut, registry, setup
//! intent): one owner of the install folder, never two mechanisms on the same target.
//!
//! Pages: Boas-vindas -> Como este computador será usado? (server|station, chosen explicitly; skipped when this computer
//! already has a team configuration, whose role is kept) -> Pronto para instalar (role and destination) -> Instalação
//! (real progress; Cancelar before the swap changes nothing) -> Concluído (Abrir o RedRise) | erro.
use std::sync::{Arc, Mutex};

use installrs::gui::{self, ButtonLabels, InstallerGui};
use installrs::{Installer, OptionKind};
use serde_json::{json, Value};

use crate::{configured, install, log_result, now, read_intent, Failure, Opts, Progress, APP_EXE};

const SERVER: &str = "Servidor da equipe: guarda os dados da equipe e também executa rotinas. Fica ligado, com o RedRise \
aberto, para atender estações e agendamentos.";
const STATION: &str = "Estação de operação: conecta-se ao servidor de uma equipe que já existe, sem criar outro banco nem \
outra equipe aqui.";

/// Runs the wizard and returns the process exit code (0 installed or cancelled before installing, 3 failed).
pub fn run(o: Opts, stub: usize, me: Vec<u8>, zip: Vec<u8>) -> i32 {
    let existing = configured(&o.data);
    let mut i = Installer::new(&[], &[], "");
    i.add_option("role", OptionKind::String, "server or station");
    i.add_option("open", OptionKind::Bool, "open RedRise when done");
    // A role chosen by an earlier run that was not set up yet comes back selected; otherwise nothing is preselected.
    i.set_option("role", read_intent(&o.data).unwrap_or_default());
    i.set_option("open", true);

    let dest = o.root.display().to_string();
    let mut w = InstallerGui::new("Instalar RedRise");
    w.buttons(ButtonLabels { back: "< Voltar".into(), next: "Continuar >".into(), install: "Instalar".into(),
                             uninstall: "Desinstalar".into(), finish: "Concluir".into(), cancel: "Cancelar".into() });
    w.welcome("Instalar RedRise",
              "Este assistente instala o RedRise para o seu usuário do Windows, sem pedir senha de administrador.\n\n\
               Clique em Continuar.");
    // Welcome-type pages (InstallRS gives their message 80 px with widgets, 200 px without; a custom page's label is
    // one line): the explanations stay readable.
    w.welcome("Como este computador será usado?", &format!("{SERVER}\n\n{STATION}"))
    .with_widgets(|p| {
        p.dropdown("role", "Uso deste computador:", &[("", "Escolha uma opção"), ("server", "Servidor da equipe"),
                                                      ("station", "Estação de operação")]);
    })
    .skip_if(move |_| existing)
    .on_before_leave(|i| {
        let role: String = i.option("role").unwrap_or_default();
        if role.is_empty() {
            let _ = gui::warn("Escolha obrigatória", "Escolha como este computador será usado: servidor da equipe ou estação de operação.");
            return Ok(false);
        }
        Ok(true)
    });
    let ready = |what: &str| format!("Uso escolhido: {what}.\n\nDestino: {dest}\n(somente para o seu usuário; seus dados ficam em %LOCALAPPDATA%\\RedRise)\n\n\
                                      Clique em Instalar. Você poderá cancelar até a troca de versão.");
    // While nothing is chosen yet the server page counts as the next one, so the role page shows Continuar, never
    // Instalar (the choice is still required by on_before_leave above).
    w.welcome("Pronto para instalar", &ready("Servidor da equipe"))
        .skip_if(move |i| existing || i.option::<String>("role").as_deref() == Some("station"));
    w.welcome("Pronto para instalar", &ready("Estação de operação"))
        .skip_if(move |i| existing || i.option::<String>("role").as_deref() != Some("station"));
    w.welcome("Pronto para atualizar",
              &format!("Este computador já está configurado numa equipe. O uso (servidor ou estação), os dados e os acessos \
                        são mantidos; nada é perguntado de novo.\n\nDestino: {dest}\n\nClique em Instalar."))
        .skip_if(move |_| !existing);

    let outcome: Arc<Mutex<Option<Result<Value, Failure>>>> = Arc::new(Mutex::new(None));
    let out_c = outcome.clone();
    let o_c = o.clone();
    w.install_page(move |i| {
        let mut opts = o_c.clone();
        opts.role = if existing { None } else { i.option::<String>("role").filter(|r| !r.is_empty()) };
        let report = |status: &str, fraction: f64| {
            i.set_status(status);
            i.set_progress(fraction);
        };
        let cancelled = || i.is_cancelled();
        let r = install(&opts, stub, &me, &zip, &Progress { report: &report, cancelled: &cancelled });
        *out_c.lock().unwrap() = Some(r.clone());
        r.map(|_| ()).map_err(|f| anyhow::anyhow!(f.pt()))
    })
    .hide_log();
    w.finish_page("RedRise instalado",
                  if existing { "A nova versão está instalada. Ao abrir, o RedRise continua de onde estava." }
                  else { "Ao abrir, o RedRise continua a configuração do uso escolhido, sem perguntar de novo." })
        .with_widgets(|p| {
            p.checkbox("open", "Abrir o RedRise agora");
        });
    // The text of each failure says what really happened (phase, version in the folder, data, next step): nothing
    // here assumes the previous version is intact (PROCESS-ACTIONS-20261111 item 4.2).
    w.error_page("A instalação não foi concluída como esperado", "O que aconteceu e o que fazer agora:");

    let ran = w.run(&mut i);
    let result = outcome.lock().unwrap().take();
    let record = match &result {
        Some(Ok(v)) => json!({"ok": true, "at": now(), "result": v, "via": "wizard"}),
        Some(Err(f)) => json!({"ok": false, "at": now(), "error": f.message(), "failure": f.to_json(), "via": "wizard"}),
        None => json!({"ok": true, "at": now(), "result": {"cancelled": true}, "via": "wizard"}),
    };
    log_result(&o, &record);
    println!("{record}");
    match result {
        Some(Ok(_)) => {
            if i.option::<bool>("open").unwrap_or(false) && o.root.join(APP_EXE).is_file() {
                let _ = std::process::Command::new(o.root.join(APP_EXE)).current_dir(&o.root).spawn();
            }
            0
        }
        Some(Err(_)) => 3,
        None => if ran.is_err() { 3 } else { 0 },
    }
}
