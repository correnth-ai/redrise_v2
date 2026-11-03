# I00 — Engine behaviour specification (independent)

Run `RUN-I00-20261026-01`, 2026-10-26. Inputs: [source map](OPENADAPT-SOURCE-MAP.md), [ENGINE.md](../ENGINE.md), [requirements](../requirements.json). Evidence labels: **[doc]** seen in upstream source at the pinned commit; **[hyp]** inference not reproduced; **[own]** RedRise requirement or decision. No upstream defect is claimed reproduced. The RedRise Engine proves its own behaviour with new regressions.

## 1. Pipeline and ownership

```
acquire (hook thread) -> bounded channel -> writer thread -> events.jsonl.partial
      -> finalize (drain to disconnect, fsync, manifest last, atomic rename)
      -> compile (validate manifest+hash -> IR v1 procedure.json)
      -> execute (readiness -> per-step precondition -> inject -> observe)
      -> report (run.json: per-step delivery + run outcome)
      -> independent verifier (separate process/language, read-only) -> verified | refuted
```

Every resource has a single owner: the hook thread owns the OS hooks and message loop; the writer owns the file handle; the controller owns the deadline and the terminal state. [own]

## 2. Upstream behaviour observed in source (capture)

Paths are relative to `OpenAdapt/packages/capture/openadapt_capture/` @ `a016fd6`.

| ID | Finding | Label | Citation |
|---|---|---|---|
| C1 | Windows input comes from raw ctypes `SetWindowsHookExW(WH_KEYBOARD_LL/WH_MOUSE_LL)` plus a `GetMessageW` loop, woken with `PostThreadMessageW(WM_QUIT)` | doc | `input_observer/windows.py:32-36, 551-593` |
| C2 | Injected input (`LLKHF_INJECTED`, `LLMHF_INJECTED`, lower-IL variants) is dropped and never recorded | doc | `input_observer/windows.py:61-64, 317, 940` |
| C3 | Keyboard fields: vk, scan, flags, foreground layout, `time.time()` stamp (the OS event time is unused); frames use a separate `perf_counter` clock | doc | `windows.py:391, 935, 946-955`; `utils.py:79` (`get_timestamp`) |
| C4 | Pipeline: hook → bounded translation queue (default 4096) → delivery queue → ordered journal (`source_ordinal`) → per-type `multiprocessing` queues → writer processes → SQLite in WAL mode, 20 s lock-retry budget per write | doc | `windows.py:387, 416, 812`; `recorder.py:546, 1121`; `db/__init__.py:49`; `db/crud.py:47` (lock budget constant) |
| C5 | The writer drain is `while not terminate.is_set() or not write_q.empty(): try get_nowait() except Empty: continue`, a loop with no blocking or sleep | doc | `recorder.py:1608-1629` |
| C6 | `empty()`/`qsize` rely on a shared counter updated after `put()` and after `get()`, separate from the pipe contents | doc | `extensions/synchronized_queue.py:104-113` (put/get), `:115`/`:123` (qsize/empty) |
| C7 | After startup, the task and record-thread joins have no timeout. Only the remote `_control_stop` has a deadline, and its timeout returns `finalization_timeout` (not success) | doc | `recorder.py:994, 4612, 4641, 4417-4445` |
| C8 | The main wait loop does not check whether writer processes are alive | doc | `recorder.py:3701-3704` |
| C9 | Finalization verifies counts, runs `PRAGMA quick_check`, checkpoints the WAL and seals with sha256; any exception marks the session failed | doc | `recorder.py:4208-4299, 4521-4532` |
| C10 | Keystrokes, titles and pixels are stored locally unscrubbed; scrubbing happens only at share time | doc | `share_scrub.py` |
| C11 | Writer busy-spin consumes a CPU core during recording | hyp | follows from C5 |
| C12 | A slow LL-hook callback may be silently unhooked by Windows (`LowLevelHooksTimeout`), and a health check that only watches the thread would not notice | hyp | Win32 documented behaviour; upstream `check_health` at `recorder.py:4649` |

## 3. Upstream behaviour observed in source (compile / replay / verify)

Paths are relative to `OpenAdapt/packages/flow/openadapt_flow/` @ `a016fd6`.

| ID | Finding | Label | Citation |
|---|---|---|---|
| F1 | Character key runs coalesce into a `type` event; unknown kinds, middle clicks and right drags raise errors instead of being dropped | doc | `adapters/capture.py:841-985, 1015-1036` |
| F2 | IR is a pydantic `Workflow` with `SCHEMA_VERSION = 2` and ActionKinds click/type/key/hotkey/scroll/wait/…; targets are anchors (template crop, OCR, landmarks, optional UIA locator) | doc | `ir.py:81, 91, 381, 1678` |
| F3 | `workflow.py` codegen is for human review only and is never executed | doc | `compiler/codegen.py:1-7` |
| F4 | `ir.py` imports qualification modules, so the IR is coupled to certification | doc | `ir.py:46, 5916` |
| F5 | Windows replay goes through an HTTP agent that must run in the interactive session 1, with guarded input checking frame hash, context and focus | doc | `backends/windows_backend.py:1-12, 408, 455`, `backends/win_agent/server.py:18-38, 1774-1820` |
| F6 | `ActionDeliveryUncertain` is never retried; success requires the full postcondition and effect contract | doc | `backend.py:33`; `packages/flow/CHANGELOG.md:2016` |
| F7 | Delivery receipts are fixed `outcome_verified: False`; run outcomes are VERIFIED / COMPLETED_UNVERIFIED / HALTED / FAILED / ROLLED_BACK | doc | `ir.py:3530, 4751` |
| F8 | A type step is retried once only when the field provably did not change | doc | `runtime/replayer.py:17168-17228` |
| F9 | The replayer is one file of 18,978 lines | doc | `runtime/replayer.py` |
| F10 | `pyautogui.write` drops non-ASCII characters, so non-ASCII text is pasted through the clipboard | doc | `windows_backend.py:28-33` |
| F11 | No explicit cancellation token was found in the replayer | hyp | grep only |

## 4. RedRise need → upstream finding → own behaviour → mechanism → future proof

| Need (RedRise) | Upstream finding | Own behaviour | Mechanism | Proof (increment) |
|---|---|---|---|---|
| Capture only the authorized surface | C1, C10 | Record only events whose foreground window belongs to the declared target process; others are counted, not stored | Filter in the hook callback on the cached foreground pid; manifest `filtered_out` count | E02 test plus native capture |
| Capture/replay separation | C2 | By default, reject injected input so the Engine never records its own replay. A lab-only `--accept-injected` flag records synthetic-operator input and labels the manifest `input_origin=injected-accepted` | Flag check in the callback; field in the manifest | E02 unit test plus native |
| Monotonic, single-clock ordering | C3 | One monotonic clock (`QueryPerformanceCounter` via `Instant`) and one sequence number per event; wall clock only in the manifest | Sequence assigned in the callback | E02 test |
| Never block the hook | C12 | The callback does O(1) work and a non-blocking `try_send`. When the channel is full the event is counted as `dropped`, and a recording with drops is never complete | Bounded `sync_channel`, `try_send` | E02 overflow regression |
| Bounded, deterministic stop | C5–C8 | No busy loop and no counter/empty-based termination. The writer blocks on `recv`; end of stream is channel disconnection (all senders dropped). The controller waits for completion with a deadline; on timeout the state is `FinalizeTimeout` and the recording stays incomplete | `PostThreadMessageW(WM_QUIT)` → hook thread unhooks and drops its sender → writer drains to `Disconnected` → fsync → manifest written last → atomic rename. Completion travels on a dedicated channel with `recv_timeout` | E02 regressions: producer interrupted, writer error, deadline, cancel, pending events, CPU-idle check |
| Producer/writer failure visible | C8, C9 | A writer error stops capture (the callback sees the receiver dropped) and yields terminal `WriterFailed`; a producer panic yields `ProducerFailed`; both are incomplete | Join results mapped to the terminal state | E02 tests |
| No partial promoted | C9 | The manifest `status=complete` exists only after a successful fsync and rename, with event count and sha256. The compiler refuses anything else | Manifest written last; compiler validates the hash | E02/E03 tests |
| Explicit IR with no code | F2–F4 | Versioned IR v1 (`ir_version: 1`) with a closed set of actions (`focus_window`, `click`, `key`, `type_text`) and no scripts; serde `deny_unknown_fields`; independent of any certification module | Rust enums; JSON schema doc | E03 tests (valid/invalid/unknown/version) |
| Ambiguity refused | F1 | Dead keys, unmapped keys, unsupported mouse buttons, an absent or ambiguous parameter literal, or an empty recording produce a diagnostic and the compile fails | Compiler `Diagnostic` list | E03 negative tests |
| Output destination distinct | own | Optional explicit parameter: the caller declares which typed literal is the output path, the compiler replaces it with a slot, and the executor requires a binding and refuses if the target exists | `--param name=literal`, `--bind name=value` | E03/E04/P01 |
| Hook liveness | C12 | Detect a silently removed hook instead of trusting thread liveness: the hook callback refreshes a heartbeat; the manifest records `last_callback_age_ms`; `readiness --probe-hooks` installs hooks, injects one benign synthetic key-up of an unused key and expects the callback within 500 ms, else `HooksUnavailable` and capture is refused | Heartbeat atomic + probe | E02 native probe test |
| Focus/session safety | F5 | Before every step, wait (bounded) until the foreground window matches the recorded process and window class. Inject only after re-checking; otherwise halt with `FocusLost` and no input. Readiness checks the input desktop, lock state and integrity level (UIPI) | Win32 `GetForegroundWindow`, `OpenInputDesktop`, `WTSQuerySessionInformation`, token integrity | E04 tests plus native |
| Uncertain effects not retried | F6, F8 | No automatic retry of any injected step. A failure after an effectful step (such as Enter in a save dialog) yields `uncertain`. Held modifiers are always released | Executor state machine; `release_all_modifiers` | E04 tests |
| Delivery ≠ outcome | F7 | Engine run outcomes are `completed_unverified`, `failed`, `cancelled` and `uncertain`. `verified` comes only from the independent verifier | Separate verifier process | E04/P01 |
| Cancellation | F11 | A cancel request is honoured between steps; the step in progress completes as one atomic `SendInput` batch, then modifiers are released and the outcome is `cancelled` | Shared atomic flag; stdin `cancel` | E04 test |
| Non-ASCII text | F10 | `type_text` uses `KEYEVENTF_UNICODE` per character, independent of the keyboard layout and without the clipboard | `SendInput` | E04 native (pt-BR) |
| Small modules | F9 | Ports and responsibilities split into crates and modules, each under a few hundred lines | Workspace layout | Review |

## 5. SOLID mapping (own)

| Principle | Concrete decision | Ports / states |
|---|---|---|
| S | Capture lifecycle (controller), durable writing (writer), compilation, execution and verification are separate modules; the verifier is a different process and language | `capture.rs`, `recording.rs`, `compile.rs`, `execute.rs`, external verifier |
| O | New surfaces (Browser, P03) arrive as new adapters and new IR actions behind a version bump; domain code holds no OS switches | one adapter crate per platform |
| L | Every adapter honours the same contracts: an `InputSource` ends its stream by dropping `EventTx`; an injector that cannot deliver returns `InjectError` and never claims success; fakes and Win32 adapters pass the same domain behaviour | `InjectError::Partial`, `Offer::WriterGone` |
| I | Small traits: `InputSource`/`RunningSource`, `RecordingWriter`, `WindowInspector`, `InputInjector`, `SessionProbe`, `FileProbe`, `Pacer`; no universal plugin interface | `engine-core/src/ports.rs` |
| D | `engine-core` has no OS dependencies (serde/sha2 only); `engine-win` implements the ports; the CLI composes them | crate graph enforced by Cargo |

## 6. States and errors (own)

- **Recording terminal states:** `Complete`, `Cancelled`, `FinalizeTimeout`, `WriterFailed`, `ProducerFailed`, `Lossy` (any drop), `Empty`. Only `Complete` is compilable.
- **Compile:** `Ok(Procedure)` or `Err(Vec<Diagnostic>)`, where each diagnostic has a code, the event sequence number and a message.
- **Run outcome:** `CompletedUnverified`, `Failed{step, code}`, `Cancelled{step}`, `Uncertain{step, reason}`, `Refused{readiness code}` (no input sent). Each step records `delivery: not_attempted|delivered|partial`.
- **Verifier:** `verified` / `refuted` / `indeterminate`, with per-check evidence.

## 7. Exclusions

No cloud, MCP, qualification/certification, plugin registry, sealing/crypto, VLM grounding, OCR or template matching in the first slice. Structural (UIA) targeting is a later rung, decided after P01 (the first slice targets window identity plus window-relative geometry and keyboard). No functional verifiers are created for excluded features.

## 8. Limits of this specification

Hypotheses C11, C12 and F11 were not reproduced. Geometry-based clicks are fragile under layout drift (upstream LIMITS.md); the first slice therefore prefers keyboard navigation, restores window placement and halts on mismatch instead of guessing. Raw keystrokes are sensitive data: recordings live on C: under the lab/data directory and use synthetic data only.
