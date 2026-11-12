# Review — PROCESS-LIST-INSTALLER-20261110

Date: 2026-11-11. Reviewer: current planning agent, with an independent read-only installer review by subagent `installer_review`. Scope: source, contracts, existing native evidence, repeatable component/contract checks; no new interactive installation or real-team execution.

## Conclusion

The beta.31 delivery substantially satisfies items 1–4. Two corrections remain: truthful installer failure/recovery reporting (P2) and consistent wording in the Kanban summary (P3). The newly requested process actions and removal of Recent executions change the next scope; they were not missing acceptance items in the previous WO. Corrections and new requirements are assigned to `delivery/work-orders/PROCESS-ACTIONS-20261111.md`.

## Findings

1. **P2 — Incorrect assurance after a post-swap failure.** `installer/src/wizard.rs:90–91` always says the previous installation remains unchanged. `installer/src/main.rs:347–370` can complete the swap and then fail creating a shortcut, recording installation metadata or writing the setup intent. No rollback follows those errors. Report actual phase/effect or perform verified recovery; test a post-swap failure. This review found incorrect reporting, not observed user-data loss.
2. **P2 — Recovery success is not checked.** `installer/src/main.rs:349–352` ignores the result of restoring the previous directory, then reports “previous version restored”. This predates part of the wizard work but affects its promised recovery contract. Preserve both errors and only claim restoration when confirmed.
3. **P3 — Mixed verified wording in the summary.** `desktop/src/features/fluxos.tsx:163` uses `StateBadge` (JOB_STATE verified = “Verificada”) next to the Kanban label “Conferida”. The preceding WO requested Conferida in the board and summary. Correct locally without renaming canonical enums or unrelated pages.

## Conformance

| Item | Evidence inspected | Assessment |
| --- | --- | --- |
| Process list | ProcessTable, DataTable child rows, Core last_success_at, component and Core tests | Paging/search/expansion and success over complete history implemented. |
| Installer | installer main/wizard, pinned InstallRS 0.1.1, P10 decisions, Tauri setup intent/update, native reports/screenshots | Choice and handoff implemented, update contract retained; failure-reporting corrections above. |
| Own account | TeamAdmin uses session ID; Core ACCOUNT-SELF-DEACTIVATE; tests | UI prevents request; server rejects direct self-deactivation. |
| Kanban | responsive grid, ordered columns, summary, latest-per-process API, stale notice, tests/native reports | Substantial compliance; minor wording correction. Native report records 1.97–2.11 s under healthy conditions and 25.33 s for stale notice with idle polling. These are prior measured results, not new timing tests. |
| Delivery | git, installed manifest/binary, candidate hash, evidence and checkpoint | Local main and origin/main both `5f40ecbc32c32b594094a9988ac4a0a24ca53bbf`; installed manifest beta.31. Installer and installed desktop hashes match recorded values. |

## Checks repeated in this review

- All 56 artifacts in predecessor `evidence.json` exist and match their recorded SHA256.
- UI: **104/104 tests, 14 files**, typecheck passed. Ran in `C:/Users/raulv/RedRise-v2-dev/build/ui-dev` because repo has no installed UI dependencies. Compared every repo `desktop/src` and `desktop/tests` file to that copy: zero differences; dependency/devDependency declarations and tsconfig match. Its package metadata still says beta.30; this is a component test environment, not a freshly built beta.31 proof. Initial commands in repo failed with vitest/tsc not found; no dependencies installed by this review.
- Core: `C:/Users/raulv/RedRise-v2-dev/runtime/python-3.12.10/tools/python.exe -B -m unittest test_process_list`, working directory `tests/core`: **7/7**, isolated PostgreSQL, synthetic history, no Runner automation.
- `node scripts/validate-base.mjs`: **346 passed**, foundation only.
- `git ls-remote origin refs/heads/main` matches local HEAD.
- Installed `%LOCALAPPDATA%/Programs/@redrise/manifest.json`: beta.31. RedRise.exe SHA256 matches manifest and recorded candidate desktop hash.
- Installer `C:/Users/raulv/RedRise-v2-dev/release/0.1.0-beta.31/RedRise-Setup-0.1.0-beta.31.exe`: SHA256 matches `52bcd0f10e5f0226064c9d82d1544f977b4b7912929da0511d4d3b7e4a72b615`.

Predecessor evidence SHA256: `c52463f7348289f692c09fa581786ec547106448b142c49f8a883b0c6eab0245`.

## Limits and handoff

- Existing screenshots already cover welcome, use selection, ready server/station, completion, cancellation and configured installation. Next WO requires a readable index and final-version walkthrough including active progress.
- Real sign-in, data presence and native transitions are supported by predecessor records and user screenshots; this reviewer did not redo native interaction. Prior evidence explicitly lacks before-update real-team counts, so it proves historical records remain, not exact before/after count equality.
- No LAN/VPN/second-machine homologation or public distribution asserted. No current disk-cleanup amount independently verified; the user's 40 folders/25.8 GB report is context only.
- Checkpoint still describes old stages as pending cleanup; next WO reconciles this after an actual inventory, without deleting historical evidence.
- No application source changes, commit, push, live update or folder cleanup performed by this review. Only review/WO documents created. Resolve the findings in the next engineering delivery.
