# Checkpoint 2026-10-28 — P13 campaign (partial), beta.3 installed

Run: RUN-U27-20261027-01. HEAD unborn; nothing committed or published.

## State
- **Installed:** `0.1.0-beta.3`, installer `3ef717a5…00d8`, at `%LOCALAPPDATA%\Programs\@redrise` (upgraded from beta.2; previous version kept).
- **Built, not installed:** `0.1.0-beta.4`, installer `3772aa89…a645`, at `C:\Users\<user>\RedRise-v2-dev\release\0.1.0-beta.4\`. Purpose: the P11 update test.
- **Channel public key** `y66XYrrJ…GBQ=` is compiled into beta.3 and beta.4. Their default channel is `http://127.0.0.1:47880/releases`, served by `site/serve_local.py`.
- **Tests (all pass):** contracts 15, runtime 41, Core + agent 20, site 4, desktop update 4, Engine 46.

## P13 practical campaign through the UI (beta.2, host `servidor-lab`; synthetic operator, manual-equivalent)
- **Boas-vindas:** verified. Exact literal text written to the real (OneDrive) Desktop.
- **Boas-vindas collision:** refused with four topics and the footer `OUTPUT-EXISTS | RR-FLOW`. Nothing was launched.
- **Excel template:** verified. Independent openpyxl check: labels preserved, B2 "Cliente Teste 01", B3 numeric 1500. The template file is unchanged.
- **Outlook:** opened only, then verified. Its content was not read.
- **Gmail:** "Concluída, não verificada" with LOGIN-REQUIRED (correct).
- **Browser:** record → compile (parameter `cliente`) → replay worked. The synthetic server stored "Cliente Web 02" (independent effect). Shown honestly as not verified.
- **Excel recording with synthetic input:** refused as empty (hardware-only works). A **human** recording of Excel is still pending (B26 pilot).
- **Operator role:** UI restricted correctly. A missing input file is refused before any action.
- **Restart via the Start Menu:** history, routines and users persisted.
- **Defects found and fixed in beta.3, not yet re-checked in the UI:**
  - Gmail: an action to open the RedRise browser for a manual login (Configuração);
  - empty-recording message in four topics (RECORDING-EMPTY);
  - recorded routines show their parameter fields;
  - INPUT-FILE-MISSING names the file;
  - sidebar sticky (**Sair** stays visible);
  - friendly field labels;
  - no native dialogs.
- **Not done:**
  - LAN second station: only one machine; coverage missing.
  - Locked session (native).
  - Excel hardware recording (needs a human).
  - P11 update E2E.
  - Contact Sales real form (B23).

## Update 2026-10-28 (resume)
- **Operator input issue: root cause found.** The Alt tap used to bring RedRise forward put the window into menu mode, which swallowed keystrokes. It is replaced by F24, sent only when needed.
- **Re-check not done.** The user started using RedRise themself (idle 0 ms, window maximized), so UI driving stopped and the beta.3 re-check did not happen.
- **P13 evidence recorded:** `delivery/evidence/P13/campaign.json`, review pending.
- **P14 draft:** `docs/release/0.1.0-beta.3/RELEASE-NOTES.md`.
- **Local site and channel running:** `http://127.0.0.1:47880/`, serving `C:\Users\<user>\RedRise-v2-dev\channel`, which is empty until the user signs beta.4.

## Open issue at cutoff (resolved above)
On beta.3, synthetic login input did not take effect. Capture showed an unchanged login form while RedRise was in front and the session was ready. The first cause considered was CPU starvation from the beta.4 compile, but the last retry ran after that build finished and its result was not inspected. Retry first; if input still has no effect, investigate before continuing.

## Next (exact)
1. Re-check the beta.3 fixes in the UI.
2. User signs beta.4, with PYTHONPATH as for keygen:
   `release_channel.py sign --installer <beta.4 exe> --version 0.1.0-beta.4 --out C:\Users\<user>\RedRise-v2-dev\channel --notes "..."`
   The agent must not read the vault key.
3. Serve the site: `site/serve_local.py --releases C:\Users\<user>\RedRise-v2-dev\channel --data C:\Users\<user>\RedRise-v2-dev\site-data`.
4. In the app:
   - the notice appears;
   - **Ainda não** keeps the version and the indicator;
   - **Pode atualizar** reopens on beta.4;
   - a tampered signature or a corrupted file is refused.
5. Write P13 evidence (screenshots are in `scratch/ui/p13-*.png`, synthetic data only) and get an independent review.
6. Then P14: release notes, inventory, limitations.

The synthetic order server (port 47321) may still be running from the lab; stop it.
