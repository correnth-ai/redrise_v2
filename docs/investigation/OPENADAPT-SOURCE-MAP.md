# I00 — OpenAdapt source map

Run: `RUN-I00-20261026-01`. Date: 2026-10-26. Method: static source reading (no upstream code executed or installed). Checkouts live in the C: lab `C:\Users\raulv\RedRise-v2-dev\research\` (not part of this repository). All findings below are **documented in source** unless labelled otherwise; none is a reproduction.

## 1. Pinned revisions

| Target | URL | Commit | Commit date | Role in this investigation |
|---|---|---|---|---|
| Catalogue | https://github.com/morluto/awesome-reverse-engineering | `63d23e3197245a28028b21c8f342df18a9ac7859` | 2026-10-25 | Method selection (matches the snapshot recorded in ENGINE.md) |
| OpenAdapt monorepo | https://github.com/OpenAdaptAI/OpenAdapt | `a016fd67ed28a14ef624f765840b9ab92448e8cc` | 2026-10-25 | **Canonical source**: launcher `openadapt` 1.18.0, `packages/capture` 1.3.0, `packages/flow` 2.4.0 |
| openadapt-capture (standalone) | https://github.com/OpenAdaptAI/openadapt-capture | `6e2e1ad6e882a99b6e6e742a85cb812aee82c59f` | 2026-10-18 | Frozen mirror; README states the package moved into the monorepo. Used only for diffs |
| openadapt-flow (standalone) | https://github.com/OpenAdaptAI/openadapt-flow | `c31f23d07e442dbcde2d58cbf23ae4fe7d0c5df1` | 2026-10-18 | Frozen at 2.1.0; README: "2.2.0 and later ship from" `packages/flow`. Used only for diffs |

Permalink form: `https://github.com/OpenAdaptAI/OpenAdapt/blob/a016fd67ed28a14ef624f765840b9ab92448e8cc/<path>#L<n>`.

### Relationship evidence (not inferred from names)

- `OpenAdapt/pyproject.toml:87-88` — extra `capture = ["openadapt-capture>=1.2.0,<2.0.0", "openadapt-flow[capture]>=2.2.0,<3.0.0"]`; `:94` `windows` extra = `openadapt-flow[windows]`; `:159` project URL "Canonical Engine" = `packages/flow`.
- `OpenAdapt/platform-manifest.json` — published selection `capture 1.2.2`, `flow 2.3.0`, `launcher 1.17.0` (generated 2026-10-20). The source tree at the pinned commit is newer than the last published selection; we study source, not PyPI.
- Standalone vs monorepo capture differ in `recorder.py`, `capture.py`, `events.py`, `cli.py` (+ `narration.py`, `share_scrub.py` only in monorepo) → the standalone repos are **not** equivalent snapshots.
- Flow's capture adapter (`packages/flow/openadapt_flow/adapters/capture.py:1-60`) reads Capture's `recording.db` only through Capture's public API (`CaptureSession.load`, `.actions(include_moves=False)`).

### Licence/obligation check (upstream-license-governance)

- Monorepo `LICENSE`: MIT (© 2023 MLDSAI Inc., Richard Abrich, contributors); `packages/capture/LICENSE` MIT (© 2025-2026 OpenAdapt.AI); `packages/flow/LICENSE` MIT (© 2026 OpenAdapt.AI (MLDSAI Inc.)).
- `packages/flow/THIRD_PARTY_NOTICES.md`: benchmark configurations fetched at run time are **AGPL-3.0-only** (openIMIS) and **GPL-3.0** (OpenEMR). Licensing is therefore **not uniform**; RedRise copies none of these.
- Decision: RedRise incorporates **no upstream code**. Upstream material informs behaviour only. If a future increment proposes a derivation, it must be registered (origin, file, lines, MIT notice) before incorporation.

## 2. Catalogue use — question → method → primary doc → target → result

| # | Investigation question | Catalogue section / resource selected | Primary documentation consulted | Target / revision | Result / evidence |
|---|---|---|---|---|---|
| Q1 | Which code actually implements capture/compile/replay, and in which revision? | "Start here" table → source is available, so no binary triage is needed. Method: static source analysis plus manifest/import tracing | The repositories' own pyproject/README/platform-manifest | Monorepo `a016fd6`; standalone mirrors | Canonical = monorepo `packages/*`; standalone repos frozen (§1) |
| Q2 | How are events acquired, queued, persisted and finalized? | Static source reading. "Dynamic instrumentation and tracing" → **Sysinternals Process Monitor** evaluated for observing writer/file behaviour at stop | learn.microsoft.com/sysinternals (Process Monitor) | `packages/capture` | Answered from source (see BEHAVIOR-SPEC §2). ProcMon **not run**: source answered the question, and observing the upstream recorder would require installing it (non-goal) |
| Q3 | What does the recording/bundle format contain? | "File formats" → **Construct** / **Kaitai Struct** evaluated for binary formats | kaitai.io, construct docs | Capture SQLite `recording.db`; Flow `events.jsonl`/`workflow.json` | Dismissed: formats are SQLite + JSON/PNG and documented in `packages/flow/DESIGN.md:56-87`; no binary-format parser is needed |
| Q4 | How is the recording compiled into the IR, and is code executed? | Static source reading. "Language runtimes and packagers" → **pyinstxtractor/pycdc** evaluated for the packaged desktop build | Tool READMEs (pycdc, pyinstxtractor) | `packages/flow/openadapt_flow/compiler/*`, `ir.py` | Answered from source; codegen is for review only (`compiler/codegen.py:1-7`). Bytecode extraction dismissed because source is the ground truth and the packaged desktop is out of scope |
| Q5 | How does replay reach the Windows desktop and verify effects? | "Web and protocols" → reading an undocumented HTTP agent protocol; **mitmproxy / Wireshark** evaluated | mitmproxy docs | `backends/windows_backend.py`, `backends/win_agent/server.py` | The protocol is documented in the source docstrings, so traffic capture was dismissed. The client docstring describes the third-party WAA Flask server, which runs `exec(command)` (`windows_backend.py:1-12`); OpenAdapt's own replacement agent keeps `/execute_windows` disabled and allow-listed (`win_agent/server.py:20-24`). Which server a deployment uses is configuration, not established here [hyp] |
| Q6 | Are known failure modes in stop/replay real? | "Debuggers" → **WinDbg / x64dbg**, and "Dynamic instrumentation" → **Frida** evaluated | Microsoft WinDbg docs; frida.re | Upstream recorder process | Not executed. Upstream failure modes are recorded as *documented* or *hypothesis*; the RedRise Engine proves its own behaviour with new regressions (E02) instead of reproducing upstream defects |
| Q7 | Which subsystems are excluded, and how coupled are they? | "Binary diffing and patch analysis" → BinDiff/ghidriff dismissed (source diff is enough); `git diff`/`diff -rq` used | — | Monorepo vs mirrors; `ir.py` imports | `ir.py:46` imports `qualification_faults` and `ir.py:5916` imports `qualification.QualificationProject`. Certification is wired into the IR module, a coupling RedRise must not copy |
| Q8 | Do AI/MCP analysis aids help? | "AI-assisted analysis" (Ghidra/IDA/WinDbg MCP) | Section text | — | Dismissed: native-binary aids, not needed for Python source; MCP is also an excluded app feature (agent-side tools are unaffected) |

Linux-only tracers (strace, bpftrace, uftrace, rr) were dismissed because the target is Windows. Nothing from the catalogue was installed.

## 3. Module map of the essential path (monorepo `a016fd6`)

Upstream tests consulted for stop/finalization (names and intent read; none executed): `packages/capture/tests/test_writer_shutdown_drain.py` (terminate before start, mid-stream tail, write error never swallowed), `test_child_process_failure_reporting.py`, `test_control.py` (finalization timeout is not success; staged-but-unsealed is marked crashed), `test_input_observer.py`. Flow tests (`tests/test_compiler.py`, `test_desktop_recorder.py`, `test_effect_*`) were identified but not read in detail. No upstream test covers a writer that hangs after a successful start.

| Function | Path | Key symbols |
|---|---|---|
| Recording (Windows input/screen) | `packages/capture/openadapt_capture/recorder.py`, `capture.py`, `events.py` | see BEHAVIOR-SPEC §2 |
| Capture → Flow adapter | `packages/flow/openadapt_flow/adapters/capture.py` | `_flow_events` (:841), `convert_capture` (:1045), `_capture_structural_locator` (:760) |
| Compiler | `packages/flow/openadapt_flow/compiler/compile.py` | `_load_events` (:221), `_compile_recording` (:1908), `lint_param_leakage` (:1131) |
| IR | `packages/flow/openadapt_flow/ir.py` | `SCHEMA_VERSION = 2` (:81), `ActionKind` (:91), `Anchor` (:381), `PostconditionKind` (:526), `Postcondition` (:558), `Step` (:1678), `ActionDeliveryUncertainty` (:3545) |
| Replayer | `packages/flow/openadapt_flow/runtime/replayer.py` (18,978 lines) | `_run_step_on_active_surface` (:7811), `_verify_typed_input` (:17168) |
| Backend protocol | `packages/flow/openadapt_flow/backend.py` | `ActionDeliveryUncertain` (:33) |
| Windows replay | `backends/windows_backend.py` (WAA HTTP client), `backends/win_agent/server.py` (in-session agent), `backends/win32_window_client.py` (local SendInput/PrintWindow) | `/input/guarded`, `/uia/act` |
| Effect verification | `runtime/effects/effect.py`, `desktop_readback.py` | CONFIRMED / REFUTED / INDETERMINATE |

Excluded (boundary only): `hosted.py`, `cloud_seal.py`, `agent/mcp.py`, `registry.py`, `qualification_*`, `runner/hosted_adapter.py`, `bundle_sealing.py`, `crypto.py`, `benchmark/`, `packages/agent`, `packages/desktop`, `packages/tray`, `packages/privacy`.

Capture-side citations are in [ENGINE-BEHAVIOR-SPEC.md](ENGINE-BEHAVIOR-SPEC.md) §2.
