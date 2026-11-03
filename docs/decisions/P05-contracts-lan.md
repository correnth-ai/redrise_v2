# P05 — integrated contracts, error diagnostics and LAN decisions

Status: implemented incrementally from 2026-10-27 (roadmap rev 4, U27). Reversible technical choices made inside the authorized local scope; product decisions (BASELINE D04–D06, D14–D23, D40–D44) are unchanged.

## Components and boundaries

```text
Desktop (Tauri/Rust + TS Vanilla)  --IPC-->  Rust command `api` --HTTPS (pinned)-->  Core (host)
                                    \--spawns (host)--> Core  --> PostgreSQL (127.0.0.1, private)
                                     \--spawns (every station)--> Runner agent --HTTPS (pinned)--> Core
Runner agent --CLI contract (E01)--> Engine --> Windows / Browser adapter
```

| ID | Decision | Why |
|---|---|---|
| P05-D1 | **Core = Python 3.12 private runtime, stdlib HTTP server** (`ThreadingHTTPServer` + `ssl`), JSON API under `/api/v1`. FastAPI (BASELINE candidate) not adopted for the closed beta | Smaller shipped surface (no pydantic-core/uvicorn binaries) and a contract we fully own; reversible behind the same HTTP contract |
| P05-D2 | **Storage = PostgreSQL 17.6 private binaries** (EDB Windows x64 zip, hash recorded), started by the host Core as an app-managed child bound to `127.0.0.1` on an app-chosen port, data under `%LOCALAPPDATA%\RedRise\host\pgdata`. No Windows service, no admin rights, no DB per station | D04–D06 (one team per server, shared PostgreSQL) without manual setup; stations never reach the DB |
| P05-D3 | **DB access**: cluster superuser is used only by the host for initdb/migrations/backup; Core runs as role `redrise_app` (DML only). Generated passwords live in the OS vault (Windows Credential Manager, DPAPI per user) — never in files, logs or the binary folder. UI and Runner never get DB credentials | AGENTS: no admin DB credentials to UI/Runner; vault separate from binaries |
| P05-D4 | **Driver** psycopg 3.2 (binary wheel, bundled libpq); **TLS certificate** generation with `cryptography` (self-signed, host-generated) | Pinned, wheel-only installs into the private runtime; no pip on the customer machine |
| P05-D5 | **Transport**: HTTPS on the LAN port chosen at host setup (default 47800). Stations pin the host certificate SHA-256 received in the join code (`rr1:<host>:<port>:<fingerprint>`); no trust-on-first-use without the code | Passwords/tokens never cross the LAN in clear text; no CA needed |
| P05-D6 | **Accounts**: first admin created at host setup; login/password (scrypt, stdlib), roles `admin`/`operator` enforced in the API; session tokens random 256-bit, stored hashed, 12 h expiry, revocable. Station/Runner credential: admin registers a station → long-lived runner token (hashed, revocable) | D40–D41, server-enforced roles |
| P05-D7 | **Jobs**: `queued → claimed (lease) → running → terminal` (`completed_unverified`, `verified`, `failed`, `uncertain`, `refused`, `cancelled`, `error`). Claim uses `FOR UPDATE SKIP LOCKED`; lease 60 s renewed by heartbeat. Expired lease of a *claimed* job re-queues it; of a *running* job makes it `uncertain` (never re-run automatically). Creation is idempotent by client `request_id`; result report is idempotent by `(job_id, lease_id)`; a conflicting second report → 409 | B14/B15: duplicates, lease, restart never produce unauthorized or repeated effects |
| P05-D8 | **Compatibility before queueing**: a job targets one station; the API refuses it unless the station's Runner reports the procedure category and platform (Core: STATION-INCOMPATIBLE; Runner local check: PROCEDURE-INCOMPATIBLE), re-checked at claim and by the Runner before the Engine | D46–D51 / B12 incl. direct API calls and resumed jobs |
| P05-D9 | **Session readiness**: the Runner checks readiness before claiming; locked/absent session → it does not claim and reports `waiting: session_unavailable` in its heartbeat (job stays queued with reason) | B11 |
| P05-D10 | **Cancellation**: `cancel_requested` on the job; Runner sees it in heartbeat and signals the Engine stop file; queued jobs cancel immediately | B14 |
| P05-D11 | **Errors across boundaries**: every non-2xx API body and every non-success job result carries `redrise.diagnostic/1` (contracts/schemas/diagnostic.v1.schema.json). `X-Correlation-Id` is propagated UI → Core → Runner → job; wrappers keep the producer diagnostic as `cause` | U27-ERROR-DIAGNOSTICS |
| P05-D12 | **Migrations**: ordered SQL files with `schema_migrations`; a `pg_dump -Fc` backup precedes any pending migration. Backup/restore commands restore into a separate, named target database (never over the live one without explicit choice) | B17, B20 |
| P05-D13 | **Versions**: API `v1`; job/result payloads `redrise.job/1`, `redrise.job-result/1`; diagnostic `redrise.diagnostic/1`; Excel descriptor `redrise.excel-descriptor/1`. Unknown major version → CONTRACT-PAYLOAD | Explicit format/version check at each boundary |

## Error diagnostics (implemented part)

- Catalog `contracts/errors.json` (stable codes, pt-BR texts, category, default module hints, effect, retry policy).
- Registry `contracts/modules.json` (code → responsibility → symbols → paths → conditions), checked by `tests/contracts/test_diagnostics.py`.
- `redrise_contracts.diagnostics`: `make`, `wrap` (cause/correlation/most-uncertain effect preserved), `render` (four topics, footer last), `validate`/`from_dict` (boundary check), `sanitize` (secrets, argv/env, profile paths).
- Runner: `redrise_runner.diagnose` attaches `diagnostic` + `message` to every non-successful CLI result; Excel capabilities return diagnostics directly.

Not yet implemented here: Core/API propagation (P06/P07), UI presentation and copy action (P08). Those are claimed only when built and checked.
