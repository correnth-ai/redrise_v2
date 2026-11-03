# Work Order — P03 private Browser (development; unverifiable until P02)

```text
Task ID / Run ID: TASK-REDRISE-V2-BETA-20261026 / RUN-P03-20261027-01
Human request: 2026-10-27 — start P03 development while the user prepares the P02 VM; P02 stays unverified.
Root: D:/Correnth/products/redrise-v2/repos/app (HEAD unborn). Lab: C:/Users/<user>/RedRise-v2-dev.
Objective: Engine-owned browser record/compile/replay through a packaged Playwright/Chromium adapter; local synthetic page with a server-side store; independent verifier; fault injection (fake success refuted); packaged layout; offline native proof on the dev machine.
Acceptance (later, after P02 verified): same on the candidate build, including on the clean VM (no global cache/download).
Allowed write set: browser/** (adapter package), engine/** (browser IR/compile/executor/adapter client), proofs/browser/**, packaging/runtime/** (layout additions), tests/browser/**, docs/decisions/P03-*.md, delivery/evidence/P03/**, delivery/status.json.
Dependencies: playwright 1.63.0, greenlet 3.5.6, pyee 13.0.1, typing-extensions 4.16.0 (wheels, hashes recorded); Chrome for Testing 153.0.8010.12 from cdn.playwright.dev via `playwright install --no-shell chromium` at build time.
Skills: scope-planning, upstream-license-governance, test-automation (resolved when tests are written).
Stop: browser download at runtime, use of the global ms-playwright cache, replay that bypasses Engine contracts, success inferred from page text.
HITL: none (loopback-only synthetic server, no external sites, no accounts).
```
