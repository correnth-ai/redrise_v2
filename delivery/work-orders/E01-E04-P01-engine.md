# Work Order — E01–E04 Engine and P01 Excel proof

```text
Task ID / Run ID: TASK-REDRISE-V2-BETA-20261026 / RUN-E01..P01-20261026-01
Roadmap step: E01, E02, E03, E04, P01 (sequential; one writer)
Human request and authorized scope: user 2026-10-26 via docs/AGENT-START-BETA.md — local development and local native proofs with synthetic data; no commit/push/publication.
Product / Repository: product:redrise-v2 / repo:redrise-v2
Root / remote / branch: D:/Correnth/products/redrise-v2/repos/app / https://github.com/correnth-ai/redrise_v2.git / main (unborn)
Existing dirty files to preserve: entire untracked tree; .local/ (untouched); proofs/excel/* (old verifier, untouched)
Objective and observable acceptance: own Rust Engine (contracts, capture with bounded finalization, IR/compiler, executor) proven natively on Notepad and real Excel; independent read-only verifier confirms XLSX persistence (T07–T09).
Non-objectives: UI, Core/Runner, installer, UIA targeting, parametrization beyond output path, any OpenAdapt code.
Predecessor evidence: delivery/evidence/I00/investigation.json
Allowed write set: engine/**, proofs/operator/**, proofs/engine-native/**, proofs/excel-engine/**, docs/decisions/E01-*.md, delivery/evidence/{E01,E02,E03,E04,P01-engine}/**, delivery/status.json, scripts/{source-digest,write-engine-evidence}.mjs. Lab/build output: C:/Users/<user>/RedRise-v2-dev/{target,proofs,verifier-venv}.
Dependencies: serde 1.0, serde_json 1.0, sha2 0.10, windows-sys 0.61, tempfile (dev); openpyxl 3.1.5 in an isolated verifier venv.
Applicable skills / pins: scope-planning fd7b13af…; upstream-license-governance 74699dbd…; task-context-checkpoint 88c25b1e…
Memory / graph: degraded (ai-memory absent) / not used (no registered root).
Native scenarios: proofs/engine-native/e04-notepad.ps1; proofs/excel-engine/p01-excel.ps1; negative hardware-only capture.
Data class: synthetic text/workbooks; raw events.jsonl kept on C: only (may contain window titles).
Stop condition: native finalization hang, misdirected input, value divergence, or uncertain effect — keep files and stop.
Recovery: new run directory per attempt; outputs never overwritten (Engine refuses existing outputs; recorded evidence set read-only before replay); applications closed with WM_CLOSE only.
HITL boundaries: none crossed (no system settings, credentials, network services).
Independent review: read-only review agent not involved in authoring.
```
