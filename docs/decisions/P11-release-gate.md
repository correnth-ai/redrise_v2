# P11 release gate: only verified updates enter the channel

Decision by the user, 2026-10-30, after beta.7 and beta.8 reached the lab channel with defects that only showed in the installed app (a runner exception, then a typing regression).

## Rule

A candidate is built, verified, and only then signed into the update channel:

1. `packaging/release/build-release.ps1 -Version V` builds the layout and the installer on C:.
2. `packaging/release/verify-candidate.ps1 -Version V` runs, with the computer free:
   - an isolated quiet install (`--install-root`, never the real install, shortcut or registry);
   - health and file integrity of the installed layout;
   - a functional smoke from the installed layout through the runner's own `run_template`. Boas-vindas runs N times idle and N times under full CPU load (the post-update condition). Every trial must be `verified`, close the app it opened, and leave none of its windows behind;
   - an isolated uninstall.

   It writes `release/V/verification.json` with the installer SHA-256.
3. `packaging/release/release_channel.py sign` refuses an installer without a `passed` record for the same version and SHA-256.

A failed or interrupted verification (computer in use) is not a pass. Fix the defect and build a new version; the channel is not touched.

## Limits

- The smoke covers the Notepad template. Excel, Outlook and the browser templates are checked in the practical campaign (P13), not in the gate.
- The gate uses the installed layout and the runner code path, not the desktop UI or the in-app update. The in-app update is exercised when the candidate is offered to the lab install after signing.
