# E01 — Engine contracts and language decision

Status: **accepted** (2026-10-26, run `RUN-E01-20261026-01`). Inputs: [I00 build plan](../investigation/ENGINE-BUILD-PLAN.md), [behaviour spec](../investigation/ENGINE-BEHAVIOR-SPEC.md). All code is new; **no upstream (OpenAdapt) code was copied or derived**.

## Decisions

| ID | Decision | Consequence |
|---|---|---|
| E01-D1 | Engine in **Rust**, Cargo workspace `engine/`, shipped as the app-managed binary `redrise-engine.exe`. Core/Runner (Python) drive it as a child process: JSON files for procedures/reports, stdin lines `stop`/`cancel` (or a stop file) for control. No port, service or customer setup. | Core/Runner stay Python and the Tauri/Rust bridge stays as confirmed. The Engine crates can later be linked into Tauri without changing the domain |
| E01-D2 | `windows-sys` 0.61 only inside `engine-win` | Every `unsafe` block lives in one crate |
| E01-D3 | Recording = directory with `events.jsonl` + `manifest.json` (written last, temp+rename, events sha256, gap-free `seq`) | Only `status=complete` with a matching hash and count is loadable |
| E01-D4 | IR v1 = `procedure.json`, `ir_version: 1`, closed actions `click`/`key`/`type_text`, `deny_unknown_fields`, params `output_path`/`text` | Scripts and unknown actions are rejected at parse time |
| E01-D5 | Independent verifier = Python + openpyxl (pinned 3.1.5) in an isolated C: venv; read-only | It never writes a workbook and does not import the Engine |
| E01-D6 | First slice targets window identity (process image + class) + window-relative geometry + keyboard; geometry drift halts | UIA structural targeting is a later increment |
| E01-D7 | Default capture accepts **hardware input only**. `--accept-injected` is a lab flag for synthetic operators; the manifest records `input_origin` | The Engine never records its own replay; lab provenance is explicit |

## Crate graph (dependency inversion)

```
redrise-engine (bin: composition root)
 ├── engine-core   (domain + ports; deps: serde, serde_json, sha2 — no OS crates)
 └── engine-win    (adapters: hooks, window identity, SendInput, session/UIPI)
      └── engine-core
```

## Ports (`engine/crates/engine-core/src/ports.rs`)

| Port | Responsibility | Adapter (Windows) |
|---|---|---|
| `InputSource` / `RunningSource` | Produce events; dropping the only `EventTx` ends the stream | `WinInputSource` (WH_KEYBOARD_LL / WH_MOUSE_LL) |
| `EventTx::offer` | Non-blocking `try_send`; seq assigned on accept; Full → dropped count; Disconnected → writer gone | — |
| `RecordingWriter` | Durable write + seal | `FsRecordingWriter` (std fs, in core) |
| `WindowInspector` | Foreground identity, activation | `WinWindows` |
| `InputInjector` | Click, key chord, Unicode char, release modifiers | `WinInjector` (SendInput) |
| `SessionProbe` | Interactive input desktop, UIPI integrity | `WinSession` |
| `FileProbe`, `Pacer`, `CancelToken` | Output collision checks, time, cooperative cancel | `StdFiles`, `StdPacer` |

## State contracts

- **Recording:** `complete | cancelled | finalize_timeout | writer_failed | producer_failed | lossy | empty`.
- **Run outcome:** `completed_unverified | failed | cancelled | uncertain | refused`. Each step's delivery is `not_attempted | delivered | partial`. `verified` is never set by the Engine.
- **CLI exit codes:** 0 ok, 1 usage/io, 2 refused, 3 failed, 4 uncertain, 5 cancelled, 6 recording not complete, 7 compile diagnostics.

## Contract examples

- Valid: [engine/contracts/ir-v1/valid/p01-excel.procedure.json](../../engine/contracts/ir-v1/valid/p01-excel.procedure.json) (compiled by the Engine in P01).
- Invalid cases are executable tests in `engine/crates/engine-core/tests/compile_ir.rs::ir_rejects_unknown_version_fields_and_scripts` (version 2, unknown field `script`, action `shell`, undeclared param).

## As-built reconciliation with the I00 behaviour spec

The independent E01–P01 review (2026-10-27) compared the [spec](../investigation/ENGINE-BEHAVIOR-SPEC.md) with the code. The spec stays as reviewed in I00; these are the as-built facts:

| Spec statement | As built |
|---|---|
| `events.jsonl.partial` + atomic rename | Events are written directly to `events.jsonl`. Integrity comes from `manifest.json`, which is written last via temp+rename and carries the count and sha256 of the events. Without a complete manifest a recording is not loadable |
| IR action `focus_window` | Not an action. Every step carries `expect` (process image + class), and the executor waits for it; activation is attempted once before the first step |
| Hook heartbeat / `last_callback_age_ms` | Replaced by an active check: before stop, `check_liveness` injects an F24 tap that this capture's hook never records; it is still passed on (`CallNextHookEx`), so the foreground app receives a benign F24. No callback within 500 ms → `source_stale`. Plus `readiness --probe-hooks` before capture. **Covers the keyboard hook only**: a silently removed mouse hook alone would go undetected (open item) |
| CPU-idle check | Not measured. No-spin holds by construction (blocking `recv`, `recv_timeout` in 200 ms slices). The hung-producer test asserts only the elapsed deadline |
| "Inject only after re-checking" | The executor injects right after the bounded wait has matched the surface (stable for 400 ms on a surface change). Inside `type_text`, the foreground and cancellation are re-checked before every character |
| Cancel completes "one atomic SendInput batch" | Clicks and key chords are single batches. Modifier chords are staged (down / key / up, with 30 ms holds), and text is sent one character per batch with cancellation checked in between |
| "cached foreground pid" in the hook | Each event resolves the window (Win32 calls) and the process image through a pid cache with a 5 s TTL (bounded, not O(1)) |

Other review fixes now in code: max-duration stop → `truncated` (not compilable); a lone modifier tap becomes a `key` step; a VK_PACKET without a printable character → `vk_packet_unsupported` (surrogate pairs are reassembled in capture); any key or click in a `#32770` dialog is effectful; UIPI before any input → `refused`; zero accepted inputs → `not_attempted`.

**Windows meaning in core (accepted for v1):** `compile.rs` holds `#32770` (standard dialog class) and VK constants. This is Windows-specific domain knowledge inside `engine-core` and a known Open/Closed debt, to move behind a platform-profile port when a second native platform arrives.

**Hardware-only demonstration not yet proven:** the product default (hardware input only) has been exercised natively only negatively: injected input ignored, the recording `empty` and the compile refused. Every successful native recording so far used `--accept-injected` with the synthetic lab operator. A human-performed recording in default mode is an outstanding confirmation.

## Known limits

Geometry clicks require the same window rect (a mismatch halts the run). Dead keys and IME composition are refused at compile time. The Engine has no postcondition on the effect of a key step. Dialog waits, file-collision refusal and the independent verifier cover the first slice; richer postconditions are a P05+ topic.
