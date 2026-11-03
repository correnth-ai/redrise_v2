# Work Order — U27 capabilities, diagnostics and app composition (P01 rev4 items, P02–P04 closure fixes, P05–P08)

```text
Task ID / Run ID: TASK-REDRISE-V2-BETA-20261026 / RUN-U27-20261027-01
Roadmap step: P01 (rev4 items 1-4), P02-P04 localized closure, P05, P06, P07, P08 (in order, one capability at a time)
Human request: 2026-10-27 — "Leia e execute integralmente o prompt atualizado (AGENT-START-BETA.md) ... capacidades pequenas,
  contratos e diagnóstico por módulos; depois, validação prática do closed beta instalado ... Não publique sem minha ordem."
Product / repo / root: product:redrise-v2 / repo:redrise-v2 / D:/Correnth/products/redrise-v2/repos/app (branch main, HEAD unborn)
Lab: C:/Users/<user>/RedRise-v2-dev (builds, runtimes, PostgreSQL test clusters, proofs)
Existing dirty files: the whole tree is untracked (unborn HEAD); preserved.
Objective / acceptance:
  P01 rev4: discover Excel (found/not_found/failed), start blank workbook from a supplied descriptor, absence/failure as
    four-topic diagnostics; routing with fixtures; short native checks only.
  P02-P04: fix review defects (template launch before session lock; Engine timeout handling; browser adapter read deadline;
    silent non-JSON drop; Playwright timeout delivery), re-run localized checks on the current layout.
  P05: error catalog + module registry + redrise_contracts.diagnostics; LAN/API/job decisions (docs/decisions/P05-contracts-lan.md).
  P06: Core (accounts, roles, stations, routines/versions, jobs, leases, backup/restore) on private PostgreSQL.
  P07: Runner agent (heartbeat/claim/start/result outbox/cancel/recovery).
  P08: Tauri desktop with Rotina/Ação/Configuração, four-topic error panel.
Check kinds: component (unit, fixtures), contract (boundary fixtures), native short checks (Excel start; Engine Esc);
  simulated: registry/window/launcher doubles, fake Engine, MemoryVault.
Non-objectives: full E2E campaigns (P13), installer (P10), update (P11), site (P12), publication.
Allowed write set: runner/**, contracts/**, core/**, desktop/**, engine/crates/engine-browser/**, browser/**, packaging/**,
  proofs/excel-capabilities/**, tests/**, docs/decisions/P05-*.md, delivery/**.
Dependencies (lab, pinned): PostgreSQL 17.6-1 EDB Windows x64 binaries (zip sha256 recorded), psycopg 3.2.13 (+binary),
  cryptography 46.0.7 (+cffi 2.1.1, pycparser 3.12), tzdata 2026.5, typing-extensions 4.16.0; Tauri 2.12.5 (cli 2.12.4),
  TypeScript 5.9.3, ureq 2.12.1, rustls 0.23.46 (ring).
Memory: ai-memory unavailable (degraded, recorded); canonical files used. Graph: no registered root; canonical fallback.
Stop: an effect claimed without verifier; secrets in files/logs; executing third-party binaries without authorization.
External/HITL: no commit/push/publication/spending. Executing the downloaded PostgreSQL binaries requires user
  authorization (classifier refusal 2026-10-27) — requested.
Review: independent read-only reviewer before marking any step verified.
```
