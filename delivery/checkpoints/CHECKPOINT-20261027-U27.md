# Checkpoint 2026-10-27 (late) — U27, closed beta available

Run: RUN-U27-20261027-01 · Work Order `delivery/work-orders/U27-P01-P08-integration.md` · HEAD unborn (nothing committed).

## State
- `closed_beta_available=true`. Candidate **0.1.0-beta.2**, installed by the product at `%LOCALAPPDATA%\Programs\@redrise`.
  - Installer: `C:\Users\<user>\RedRise-v2-dev\release\0.1.0-beta.2\RedRise-Setup-0.1.0-beta.2.exe`, sha256 `d8383c1a…a4d3`.
  - beta.1 is kept as `@redrise.previous`.
  - Evidence: `delivery/evidence/P10/closed-beta.json`.
- On this machine the host is bootstrapped through the UI:
  - team "Equipe Lab RedRise", admin `admin.lab`, host station `servidor-lab` ready;
  - synthetic lab passwords are in `C:\Users\<user>\RedRise-v2-dev\scratch\lab-accounts.txt` (lab only).
- **Tests** (all pass):
  - contracts 15;
  - runtime 41;
  - Core + agent 20, on a real PostgreSQL 17.6 temporary cluster;
  - desktop update unit 4;
  - Engine 46.
- **P02/P03/P04** localized re-checks passed on the beta layout.
- **Review P05–P10:** P05, P07 and P10 approved. P06 (B1) and P08 (B2) rejected; both are fixed and re-review is pending.

## Blocked on the user
1. **Release channel key (P11).** Writing it to the vault from the agent was refused (secret-store write).
   - The user runs this command with PYTHONPATH set to `contracts\python` plus the Core site-packages: `packaging/release/release_channel.py keygen`.
   - Then put the printed key in `desktop/src-tauri/channel-public-key.b64`; it is `UNSET` today, which refuses every update.
2. **P13 UI campaign.** The synthetic operator takes the foreground of the user's desktop, and the user is active there. A window has to be agreed. Consents still needed:
   - writing `Boas_Vindas.txt` on the real (OneDrive) Desktop;
   - opening Outlook (real mailbox: open only);
   - the Gmail login is done by the user.
   - LAN with a second station: no second machine is available. This is declared coverage missing.

## Next (exact)
- After the key: rebuild desktop → `packaging/release/build-release.ps1 -Version 0.1.0-beta.3`. Then sign it into a local channel folder, configure `%LOCALAPPDATA%\RedRise\config\update.json` `{"channel_url": ...}`, and run the P11 E2E: notice → Ainda não → Pode atualizar → reopened; tampered signature and corrupted download refused.
- P12: local isolated site from the specific site sources. Not started.
- P13 campaign: matrix in `docs/BETA-ACCEPTANCE.md`. Then re-review and P14.
- Safety rule for UI driving: capture with PrintWindow only; the operator aborts unless RedRise is the foreground window.
