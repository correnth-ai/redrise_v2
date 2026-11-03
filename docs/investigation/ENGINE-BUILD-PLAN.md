# I00 — Engine build plan (E01–E04, P01)

Run `RUN-I00-20261026-01`. Derived from [ENGINE-BEHAVIOR-SPEC.md](ENGINE-BEHAVIOR-SPEC.md). Paths are proposals until the increment creates them. Build/test artefacts go to C: (`CARGO_TARGET_DIR=C:\Users\<user>\RedRise-v2-dev\target\engine`); sources stay on D:.

## Decision proposals handed to E01

| ID | Question | Proposal | Criterion |
|---|---|---|---|
| E01-D1 | Engine language/boundary | **Rust** Cargo workspace `engine/` producing the app-managed binary `redrise-engine.exe`; Core/Runner (Python) invoke it as a managed child process (JSON files + stdin control lines); Tauri may link the same crates later | See comparison below |
| E01-D2 | Win32 binding | `windows-sys` behind the adapter crate only | `unsafe` isolated in one crate; domain has zero OS deps |
| E01-D3 | Recording format | Directory `events.jsonl` + `manifest.json` (manifest written last) | Inspectable, hashable; single writer thread, no SQLite/multi-process writers |
| E01-D4 | IR | JSON `procedure.json`, `ir_version: 1`, closed action enum | Spec §4 |
| E01-D5 | Independent verifier | Python + openpyxl in an isolated C: venv, read-only | Different process/language from the Engine; never writes |
| E01-D6 | First-slice targeting | Window identity (process image + class) + window-relative geometry + keyboard; UIA later | Minimum for P01; drift halts |

### E01-D1 alternatives

| Option | Pros | Rejected / kept because |
|---|---|---|
| A. Python (ctypes/pywin32) inside the Runner | Same language as Runner; fast iteration | Rejected: LL-hook callbacks would run under the GIL with Runner work, risking the silent-unhook timeout (spec C12); Engine and Runner responsibilities would merge (violates S); needs the Python runtime even for capture |
| B. Rust standalone binary, process boundary (chosen) | Native hooks without a runtime; crash isolation from Runner/Core; one artefact to sign/inventory; testable domain crate | Kept. Costs: JSON contract to maintain; process lifecycle managed by Runner (already its responsibility) |
| C. Rust crate linked into the Tauri app | No extra process | Rejected for the first slice: the Engine must also run from the Runner on stations without UI focus coupling; can be added later because the crates are reusable |
| D. Python + PyO3 Rust extension | Shares Runner process | Rejected: build/packaging complexity with no benefit over B; still couples crashes |

## Increments

Each increment: prerequisites → work → commands → observable result → review → failure/recovery.

### E01 — contracts
- **Prerequisites:** I00 verified.
- **Work:** `docs/decisions/E01-engine-contracts.md`; `engine/crates/engine-core/src/{ports,model,ir,recording}.rs`; IR examples in `engine/contracts/ir-v1/{valid,invalid}/`.
- **Minimum dependencies:** serde, serde_json, sha2 (tempfile for tests).
- **Commands:** `cargo test -p engine-core` (IR valid/invalid/unknown-field/version tests; ports compile against fakes).
- **Observable:** examples accepted or rejected as expected; crate graph shows that `engine-core` has no OS deps (`cargo tree -p engine-core`).
- **Review:** independent read-only review of the decision record and contracts.
- **Failure/recovery:** contract defects reopen E01 only; no data involved.

### E02 — capture and bounded finalization
- **Prerequisites:** E01 verified.
- **Work:** `engine-core/src/capture.rs` (controller), writer in `recording.rs`, `engine-win/src/{hooks,window,dpi}.rs`, CLI `record`.
- **Minimum dependencies:** windows-sys.
- **Commands:** `cargo test -p engine-core capture` (fake producer: complete, producer panic → ProducerFailed, writer error → WriterFailed, overflow → Lossy, hung producer → FinalizeTimeout within deadline, cancel → Cancelled, pending events drained, empty → Empty); native `redrise-engine record --target notepad.exe …` on C:.
- **Observable:** native manifest `complete`, event count = lines, sha256 matches; non-target events filtered; finalization within the deadline.
- **Review:** independent review of the tests and of one native manifest.
- **Failure/recovery:** incomplete recordings are retained with a non-complete status and never compiled; rerun with a new directory (no overwrite).

### E03 — IR and compiler
- **Prerequisites:** E02 verified (native recording available).
- **Work:** `engine-core/src/compile.rs`, CLI `compile`.
- **Commands:** `cargo test -p engine-core compile` (char runs → `type_text`; chords → `key`; click relative coordinates; window change; parameter slot; negatives: dead key, wheel, right/middle button, drag, absent/ambiguous parameter, incomplete recording, hash mismatch, unknown IR version/field); compile the E02 native recording.
- **Observable:** deterministic `procedure.json` (same input → same sha256) correlated to `events_sha256`.
- **Review:** independent review of the compiler diagnostics and of a sample procedure.
- **Failure/recovery:** compile errors leave no procedure file; recordings are never edited by hand.

### E04 — executor and verification boundary
- **Prerequisites:** E03 verified.
- **Work:** `engine-core/src/execute.rs`, `engine-win/src/{inject,session}.rs`, CLI `run`, `readiness`.
- **Commands:** `cargo test -p engine-core execute` with fakes (focus timeout → no input; cancel between steps; modifiers released on every exit; failure after an effectful step → Uncertain; no retry; binding collision refused; UIPI refusal); native Notepad record → compile → run with a bound output path → independent read of the saved TXT.
- **Observable:** `run.json` per-step delivery records; an independent reader confirms the text file content.
- **Review:** independent review of the run report against the file read.
- **Failure/recovery:** a failed or uncertain run never auto-retries; outputs go to new bound paths; the operator inspects before rerunning.

### P01 — real Excel
- **Prerequisites:** E04 verified; interactive unlocked session; Excel 365 x64.
- **Work:** `proofs/excel-engine/` (verifier + runbook script), `delivery/evidence/P01-engine/`.
- **Files verified:** `entrada/template_redrise.xlsx` (T07: labels A1..A3/B1, B2/B3 empty), `saida/resultado_gravado.xlsx` (recording output: B2=`Cliente Teste 01`, B3=1500 numeric), `saida/resultado_replay.xlsx` (replay output, same values, distinct file).
- **Commands:** `redrise-engine readiness`, `record`, `compile --param output_path=…`, `run --bind output_path=…`, then `python verify_engine_result.py check`.
- **Review:** independent review of the evidence.
- **Failure/recovery:** a diverging value or an uncertain run blocks P01; files are kept; new attempts use new run directories.
- **Honest limitation:** in an unattended agent session the demonstration is performed by a synthetic operator injecting OS input, recorded under `--accept-injected` and labelled as such; a human-operated recording remains a recommended confirmation.

## Packaging forward-compatibility
`redrise-engine.exe` is self-contained and placed under `%LOCALAPPDATA%\Programs\@redrise\engine\` by the P10 installer. Data and recordings go under `%LOCALAPPDATA%\RedRise\data\`, outside the binaries. No ports, plugins or customer setup.

## Re-routing triggers
Hook unreliability under load, UIPI blocking, locale variance in Excel dialogs, or a need for UIA targeting → re-route before continuing.
