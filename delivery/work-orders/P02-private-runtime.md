# Work Order — P02 Engine/Runner/private runtime

```text
Task ID / Run ID: TASK-REDRISE-V2-BETA-20261026 / RUN-P02-20261027-01
Roadmap step: P02 (predecessor P01 verified: delivery/evidence/P01-engine/proof.json)
Human request: 2026-10-27 — user will provide a clean disposable Windows 11 x64 VM; meanwhile continue P02 development that does not need it, keeping P02 unverified.
Product / Repository / Root: product:redrise-v2 / repo:redrise-v2 / D:/Correnth/products/redrise-v2/repos/app (HEAD unborn)
Objective (this run): minimal Python Runner (stdlib only) that resolves the private runtime, reports health/session/capabilities, refuses incompatible categories before any Engine action, and runs an approved procedure through redrise-engine.exe; a layout builder that assembles app-managed binaries (Engine + private CPython + Runner) with a hash manifest; a dev-machine proof of the P01 Excel scenario through the staged layout; a clean-machine runbook.
Acceptance for P02 VERIFIED (not reachable in this run): the same staged package on a clean Windows 11 x64 machine without Python/Node/Rust runs health and the P01 scenario, offline, and with an incompatible global Python present (roadmap P02.5; B01/B02/B05/B28).
Non-objectives: installer (P10), Core/LAN (P05+), UI, PyInstaller unless needed.
Decisions to make: runtime layout; launcher form; isolation flags.
Dependencies: CPython 3.12.10 x64 from nuget.org package `python` 3.12.10 (PSF; SHA512 u9pNz2iK…AeHMDw== matches the NuGet catalog; PSF licence file shipped). No pip packages in the runtime.
Allowed write set: runner/**, packaging/runtime/**, tests/runtime/**, delivery/evidence/P02/**, delivery/work-orders/P02-*.md, delivery/status.json, docs/decisions/P02-*.md. Lab: C:/Users/<user>/RedRise-v2-dev/{downloads/p02-python,stage,proofs/p02-*}.
Skills: scope-planning fd7b13af…; upstream-license-governance 74699dbd… (CPython redistribution); local-app-runtime (resolved at runtime-layout step).
Stop: hidden download at first run, global Python/PATH use, missing DLL, or a need for the customer to install anything.
Recovery: staging dirs are disposable and recreated per run; no writes to the real %LOCALAPPDATA%\Programs in this run.
HITL: none (no installation into the user's profile, no system settings).
```
