# Checkpoint 2026-10-28 (night) — candidate 0.1.0-beta.6

HEAD unborn; nothing committed or published.

## State
- Installed: **0.1.0-beta.6**, installer `4f4de214…5e`, at `%LOCALAPPDATA%\Programs\@redrise`. The previous version is kept as `@redrise.previous` (beta.5, restored by the rollback test and then replaced again).
- Local site and update channel: `http://127.0.0.1:47880/`. The channel offers beta.6, signed. It is a background process and may need restarting.
- Tests: contracts 15, runtime 41, site 4, Core + agent 20, desktop update 4, Engine 46. All pass.

## Review (2026-10-28) and fixes
- **P06 B1 / P08 B2:** APPROVE.
- **P11 REJECT, fixed in beta.5/beta.6:**
  - host-wide safe point before an update;
  - apply uses only the release verified in Rust;
  - installer started before the children are stopped;
  - update apply is async; diagnostic texts aligned;
  - update log;
  - rollback from the installed `uninstall.exe` (hand-over to a temp copy);
  - installer working directory set to `%TEMP%`;
  - isolated tests never touch the real Start Menu entry, HKCU key or install record.
- **P12:** APPROVE as a local slice. The canon gaps are listed as missing coverage.
- **P13:** partial. The evidence and status were corrected so they no longer overstate.

## Practical results on the real install
- App updates beta.4 → beta.5 → beta.6 passed.
- Documented rollback beta.6 → beta.5, then reinstall of beta.6, passed.
- B09 on beta.6:
  - The first run was garbled; the verifier refuted it. Probable cause: concurrent human input, not confirmed.
  - The second run produced the exact literal.
  - The collision run was refused.
- Not repeated on beta.6: B03 Excel, B10 Outlook/Gmail, B04 Browser.

## Open defect
- **RR-ENGINE-EXEC:** the executor does not detect concurrent hardware input during a replay. It should stop as uncertain, and not keep typing.

## Update 2026-10-29 (not packaged yet)
- Implemented a replay guard in the Engine:
  - `engine_win::guard`: LL hooks during native runs.
  - The Engine tags its own `SendInput` (`ENGINE_TAG`). Any other key or button press stops the run with `user_input_detected`: `uncertain` once our input reached the desktop, otherwise `failed`. A guard that cannot be armed refuses the run (`input_monitor_unavailable`).
  - New catalog code `RUN-INTERRUPTED-BY-INPUT` (RR-ENGINE-EXEC). The Runner now passes the Engine message as `detail`.
- Tests:
  - Engine 51 (5 new).
  - Contracts 15, runtime 42 (1 new), site 4, core 20.
  - All pass.
- Native smoke on C:, run with the new Engine CLI, outside the app:
  - The clean run completed. All 13 steps were delivered and the guard did not flag the Engine's own input.
  - **The text was still garbled** ("RedRise!EEstamos eelizes"), with the computer idle for 60 s before and no foreign input seen. So the beta.6 garbling is most likely **not** human input. It is an Engine/Notepad typing defect, intermittent, right after "RedRise! ". Root cause not confirmed; hypothesis: Notepad spellcheck/autocorrect at the word boundary racing with typed characters.
  - The deliberate interference run was not done: the computer was in use, so it was aborted before any input.
  - Proof folder: `C:\Users\raulv\RedRise-v2-dev\proofs\p14-guard\`.

## Update 2026-10-29 (afternoon)

### Scope decisions (user)
- Deferred until after the beta release: human Excel recording; LAN second station and the firewall decision.
- Not doing: Authenticode (cost).
- After the roadmap: full site and Contact Sales.

### Template end state (implemented, unit-tested, not yet in an installed build)
- The runner notes whether the app was already running before launching it.
- After a **verified** result, it closes only the windows the run opened. It sends the window's own close request (as the title-bar X), never a forced kill.
- An app that was already open stays open. Failed, uncertain or refuted runs keep the app open for checking.
- Outlook (`close_opened_app: false`) stays open, because opening it is the result.
- The Gmail browser is run-scoped and already closes.
- Template versions: Boas-vindas 1.2.0, Excel 1.2.0, Outlook 1.0.1.
- Result field: `opened_app.action`.

### Typing garbling: findings
- Harness: Engine typing into a lab Notepad, read back through UI Automation (`C:\Users\raulv\RedRise-v2-dev\scratch\garble\`).
- At normal load: 24/24 correct. This covers typing only, typing with a file tab loading, typing plus zoom, and the full procedure with save.
- Under full CPU load (6 busy processes): reproduced, 2/5 garbled ("RedRise!Estamos eelizes"). Always right after the word "RedRise!".
- Layout-key typing (VkKeyScan instead of Unicode packets) did not help: still garbled. Reverted.
- Waiting for input-idle after each character: inconclusive. Under load the UIA readback often returned an empty tab, so the results are unreliable. Reverted, so no experiment code remains in the Engine.
- Next harness: full procedure with save under load, comparing the **saved file** (reliable), A/B.
- Leading hypothesis: Notepad's spell check or autocorrect running on the unknown word "RedRise" races with typed characters when the CPU is busy. Not confirmed.
- The batch stopped when the guard detected someone using the computer. This is also a real-world check that the guard detects human input.

## Update 2026-10-30: beta.7 and beta.8 (installed in the lab, NOT ready)

### Lab A/B (Engine CLI, Notepad, full CPU load, scored on the saved file)
| Variant | Correct |
|---|---|
| Current | 6/8 |
| WaitForInputIdle after each character | 8/8, then 16/16 |
| 300 ms pause after spaces/punctuation | 8/8 |

The wait was adopted in `engine_win::inject` (Engine sha `390df966…`, 51 tests pass).

### beta.7
- Installer `cb543aec…`, signed in the local channel. Updated beta.6 → beta.7 through the app.
- Boas-vindas failed at once with `runner_exception` (AttributeError), so it was marked Incerta.
- Cause: `apps.is_running` decoded `tasklist` output as UTF-8. Without a console, tasklist writes its localized "no match" message in the OEM code page (byte 0x80 = "Ç").
- Fix: decode as OEM with `errors=replace`. New test runs the check in a console-less UTF-8 child process; the old code is reproduced failing.

### beta.8
- Installer `a5eb43e8…`, signed in the local channel. Updated beta.7 → beta.8 through the app.
- Boas-vindas on the real Desktop: **severely garbled** ("Boas aaaaaaaaaaaaaaaaaaaaaamos ccccccccccccccconosco! …").
  - The verifier refuted it, so the app showed "not verified". Notepad was kept open, as the end-state rule requires.
  - The Notepad process the run started (08:28) has **19 top-level windows**, most with unsaved synthetic text, and does not respond to SC_CLOSE.
  - The garbled file was moved to `proofs/p13/desktop-archive/Boas_Vindas-beta8-run1-garbled.txt`.
- This is a regression that appears only through the app. Under the Engine CLI the same Engine was 24/24 correct.
- Suspects, untested: the new input guard (LL hooks in the Engine process, which slow all system input when the hook thread is starved), the per-character WaitForInputIdle, or both together. beta.7 never reached typing, so beta.8 was the first in-app run with both. The run also came right after an update (antivirus scanning about 700 MB, high load).
- The window title pattern hints at repeated key handling (Ctrl+N or Ctrl+S repeated). Not established.
- **Do not promote beta.7 or beta.8.** beta.6 remains the last candidate with acceptable Boas-vindas behaviour.

## Update 2026-10-30 (late morning): language split, release gate, beta.9 blocked

### Language (user decision)
- Backend codes, messages and params are English ASCII. The pt-BR text is a UI mask (`desktop/locale/pt-BR.json`, rendered by `desktop/src/locale.ts`), and the diagnostic now carries `params`.
- The installer keeps pt-BR dialogs through its own mask.
- The process check uses Win32 (`EnumProcesses`), not `tasklist`.
- Contract tests cover: ASCII catalog, mask coverage with the same placeholders, and no non-ASCII literals in backend code.
- Tests: contracts 17, runtime 48, core 20, site 4, desktop 4. All pass.

### Typing pace
- Boas-vindas `char_delay_ms` 80 (was 45); Excel 60 (was the Engine default of 25).

### Release gate (docs/decisions/P11-release-gate.md)
- `verify-candidate.ps1` runs an isolated install, health, the Boas-vindas smoke (idle and under load) from the installed layout, and an isolated uninstall.
- `release_channel.py sign` refuses an installer without a passed `verification.json` for its SHA-256.

### beta.9 (installer 89a2fc7c...): BLOCKED by the gate, not signed
- Install, health (3734 files, integrity ok) and uninstall passed.
- All 3 Boas-vindas trials failed with `focus_timeout`, and **19 Notepad windows** were present after each launch.
- Root cause (most likely, consistent with all observations): the Windows Notepad session restore was polluted by the lab harness force-killing Notepad many times (2026-10-29/30). Each launch restores those windows. This also explains the beta.8 in-app garbling: the Engine matches any `notepad.exe`/`Notepad` window, so with many windows restoring, the typed text was spread across them. It is not an Engine typing defect.
- Product gap revealed: Notepad templates must not depend on Notepad having no restored windows. The Engine/runner should bind to the window the run opened. Not implemented yet.
- Lab rule from now on: never force-kill Notepad in harnesses. Close through the app's own close request, after saving.
- The user cleans the restored Notepad windows by hand (decision 2026-10-30); the agent does not touch Notepad's TabState.

## Update 2026-10-30 (afternoon): bind the run to the window it opened (beta.10)
- Engine: `RunOptions.bound_window` / `--bound-window <hwnd>`. When set, a step's surface must match the expected image/class AND its root owner (`GetAncestor(GA_ROOTOWNER)`) must be the bound window, so the Save As dialog it owns still counts. The first step activates exactly that window. The per-character focus check uses the same rule, so typing stops (`focus_lost_during_input`) if another window of the same app takes focus.
- Runner: after the launch, `apps.launched_window` waits until the set of new windows of the first step's image/class stops changing (2 s quiet, 30 s max; an app may restore several windows), takes the foreground one if it is new, else the topmost new one, and passes it to the Engine. No new window: `launched_window_not_found` (new catalog code `APP-WINDOW-NOT-FOUND`, pt-BR mask), before the Engine runs. Browser procedures and procedures whose first step targets another image are not bound.
- Tests: Engine 54 (3 new: another window of the app in front, own window plus its dialog, focus moves to a sibling while typing); runtime 53 (5 new); contracts 17; core 20; site 4. All pass.
- Built as 0.1.0-beta.10 on C: (installer 188b613d..., Engine 057ed445...). Not signed until `verify-candidate.ps1` passes.
- Build-order pitfall: `build-release.ps1` packs the prebuilt `target\engine\release\redrise-engine.exe`. The first beta.10 build reused the beta.9 Engine (same hash 390df966...) and was deleted unsigned. Build the Engine release binary (`CARGO_TARGET_DIR=<lab>\target\engine`) before `build-release.ps1`, and compare `engine_sha256` with the previous candidate.

- Gate 2026-10-30 19:37-19:45 (user cleaned Notepad; computer free): **passed**. Install ok; health 3734 files, integrity ok; Boas-vindas 3/3 idle and 3/3 under load `verified`, each `opened_app.action: closed`, 0 windows left; uninstall ok. Record: `release/0.1.0-beta.10/verification.json`.
- Signed into the local lab channel (`channel/`, loopback only, not published). Local site/channel server restarted on 127.0.0.1:47880.

## Next
1. Update the lab install through the app; B09 in the app (including the close of the verified run).
2. With the computer free: B03/B10/B04 and a deliberate concurrent-input check.
3. Re-review; release notes for the final candidate.
- Still missing coverage: human Excel recording, LAN second station, native locked session, Contact Sales, full canon site, Authenticode.
