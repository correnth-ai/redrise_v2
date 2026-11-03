# Checkpoint — 2026-10-26 — Engine slice proven; P02 blocked on a clean machine

- **Objective:** RedRise v2 to a release-ready Beta per [AGENT-START-BETA.md](../../docs/AGENT-START-BETA.md). Authorization: user, 2026-10-26: local research/development/proofs with synthetic data. No commit/push/publication.
- **Root:** `D:/Correnth/products/redrise-v2/repos/app` (HEAD unborn, whole tree untracked). Lab: `C:/Users/<user>/RedRise-v2-dev` (`research/` upstream clones, `target/engine` Cargo output, `proofs/` native runs, `verifier-venv/` openpyxl 3.1.5).
- **Verified (see `delivery/status.json`):** P00, I00, E01, E02, E03, E04, P01 — evidence in `delivery/evidence/{I00,E01,E02,E03,E04,P01-engine}/`.
- **Engine:** Rust workspace `engine/` → `redrise-engine.exe` 0.1.0 (`readiness | record | compile | run`). Build: `cd engine; $env:CARGO_TARGET_DIR="$env:USERPROFILE\RedRise-v2-dev\target\engine"; cargo test --release; cargo build --release --locked`.
- **Native proofs:** `proofs/engine-native/e04-notepad.ps1 -Engine <exe>`; `proofs/excel-engine/p01-excel.ps1 -Engine <exe> -VerifierPython <venv python>`. Both drive the real desktop of the logged-in user; they close apps with WM_CLOSE only.
- **Engine build:** release sha256 `3a436103f03fe8ba37dbef47c9653d8ff6fae7ae218eb0f7d2854a920e3e8491`; 37 tests; clippy -D warnings clean; final native runs `p01-engine/run-20261027-000410`, `e04-notepad/run-20261027-000344`, `e02-negative/run-20261027-000520`.
- **Open risks:** liveness probe covers the keyboard hook only; hardware-only (default) recording proven only negatively; the demonstration is by a synthetic operator (injected input, labelled); geometry clicks need the same window rect; no UIA targeting; Notepad session-restore tabs from tests may appear in the user's Notepad.
- **Blocker for P02 (and B01/B02/P10/P13):** acceptance requires a clean Windows 11 x64 machine without Python/Node/Rust. This host has no Windows Sandbox/Hyper-V (enabling needs admin and a reboot, which is the user's decision). Later steps also need 3 machines (host + 2 stations, P10/P13), an independent human pilot/reviewer (P13/P14) and a code-signing/distribution decision (P10/P11/P14).
- **Next safe action:** P02 development that does not need the clean machine: private runtime layout under `packaging/runtime/`, a minimal Python Runner (`runner/`) driving `redrise-engine.exe` over the CLI contract, health/session reporting, and the per-user layout `%LOCALAPPDATA%\Programs\@redrise`. P02 is `blocked` in status; it may move to `in_progress` while developing, but stays unverified until the clean-machine run.
- **Successor policy:** at most one successor session; resume from this file plus `delivery/status.json`, re-verify volatile state (lab paths, running processes, the build hash) first.

## Update 2026-10-27 — P02 development (unverified)

- User will provide a clean disposable Windows 11 x64 VM; P02 is `in_progress`, acceptance pending that run.
- Built: stdlib-only Runner (`runner/redrise_runner`, 12 tests in `tests/runtime`), layout builder `packaging/runtime/build-layout.ps1` (private CPython 3.12.10 from nuget.org, SHA512 matches the catalog; `._pth` isolation; manifest + integrity check), VM bundle builder and VM entry script under `packaging/runtime/vm/`, runbook `packaging/runtime/CLEAN-MACHINE-P02.md`, decisions `docs/decisions/P02-private-runtime.md`, dev evidence `delivery/evidence/P02/dev-machine.json`.
- Candidate: layout manifest `3d8f1620…70b0` (640 files), VM bundle `%USERPROFILE%/RedRise-v2-dev/stage/p02-vm-bundle-20261027-011940` (bundle-manifest `17f29364…0c21`).
- Dev-machine proof: P01 through the packaged Engine + Runner job under a hostile Python environment → verified (run-20261027-012101).
- **Next safe action:** copy the VM bundle into the clean VM and follow the runbook; verify results on the host; independent review; mark P02 verified; then P03 (Browser private: Playwright/Chromium packaged).

## Update 2026-10-27 — P03 development (unverified) and current candidates

- Engine rebuilt for P03 → `d14f9e9b…a570` (46 tests). E04/P01 revalidated natively on it (runs 015404/015429), recorded under `revalidations` in their evidence.
- **Current P02 VM bundle:** `%USERPROFILE%/RedRise-v2-dev/stage/p02-vm-bundle-20261027-015624` (bundle-manifest `138c9dc2…56cf`). The earlier 011940 bundle was removed (superseded).
- P03: browser adapter `browser/redrise_browser` (Playwright 1.63.0 + Chrome for Testing 153.0.8010.12, packaged), Engine IR v2 browser actions, crate `engine-browser`, proof `proofs/browser/p03-browser.ps1` → verified on the dev machine (run-20261027-015319), including the fault-injection refutation. Evidence `delivery/evidence/P03/dev-machine.json`; status `in_progress` (needs P02 verified, then a clean-machine browser pass).
- **Next safe action:** clean-VM P02 run with the current bundle; then add the browser layout to the VM bundle and run `p03-browser.ps1` there (synthetic server via the package's private Python, verifier on host); then P04 templates.

## Update 2026-10-27 — P04 development (unverified); final build of the day

- Engine `2a8b830f…9305` (46 tests). E04/P01/P03 revalidated on it (runs 091252 / 091323 / 091039+091105).
- **Current P02 VM bundle:** `%USERPROFILE%/RedRise-v2-dev/stage/p02-vm-bundle-20261027-091450` (bundle-manifest `082a638c…31f0`). Earlier bundles removed.
- P04: `templates/` (boas-vindas 1.1.0, excel-pedido 1.1.0, outlook-abrir, gmail-acessar, browser-formulario = candidate, not shipped); Runner `templates`, `check-template`, `run-template`; stdlib verifiers (UTF-8 text, XLSX cells, window present, final URL). Proof `proofs/templates/p04-templates.ps1` → all as expected (run-20261027-091130). Evidence `delivery/evidence/P04/dev-machine.json`.
- Save As rule (user): folder via the navigation field, only the file name in "Nome do arquivo". Corporate skill `windows-file-dialog-navigation` created in `D:/Correnth/catalogs/skills` (uncommitted; catalog `npm test` 0 failures).
- **Next safe action:** clean-VM P02 run; then P03/P04 clean-machine passes (real Desktop write, Outlook launch with a synthetic account, Gmail signed-in path); decide the shipped Browser target; then P05.
