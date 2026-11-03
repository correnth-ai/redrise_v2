# P02 — clean-machine acceptance runbook

P02 is verified only by this run on a **clean, disposable Windows 11 x64** machine (roadmap P02.5; Beta B01/B02/B05/B28). The development machine does not count.

## VM prerequisites (owner: the person providing the VM)

1. Fresh Windows 11 x64 (Pro or Enterprise) with an interactive, unlocked user session. Do **not** install Python, Node, Rust, Visual Studio or Git.
2. Microsoft 365 Excel desktop installed and activated under that user. Excel is the *target application*, a precondition of the scenario; it is not part of the RedRise package. Open Excel once by hand to dismiss first-run prompts, then close it.
3. Display at 100–150 % scale, with nothing else in the foreground during the run. The operator script drives the real keyboard and mouse for about 2 minutes per pass.

## Steps

1. On the host, build the bundle (already built for this candidate):
   `packaging\runtime\vm\make-vm-bundle.ps1 -Layout <stage>\@redrise -Out <bundle>`
   Record the `bundle-manifest.json` sha256 (see `delivery/evidence/P02/dev-machine.json`).
2. Copy the whole `<bundle>` folder into the VM, e.g. `C:\p02-bundle`. Files copied from another machine may carry Mark-of-the-Web; in the VM run `Get-ChildItem C:\p02-bundle -Recurse | Unblock-File`.
3. **Disconnect the VM's network** (offline pass, B01).
4. In the VM, open Windows PowerShell **as the normal user** and run:
   `powershell -NoProfile -ExecutionPolicy Bypass -File C:\p02-bundle\run-p02-on-clean-vm.ps1`
   (The execution-policy override is your explicit choice for this disposable VM; nothing is changed permanently.)
5. When it finishes, copy `C:\p02-bundle\results-<timestamp>` back to the host.
6. On the host, for each `p01-plain\run-*` and `p01-incompatible-python\run-*`:
   `<verifier-venv>\Scripts\python.exe proofs\excel-engine\verify_engine_result.py --run <dir>`
7. Hand the results to the agent, which records `delivery/evidence/P02/clean-machine.json` and requests an independent review before changing P02 to `verified`.

## What the VM run must show

| Check | Expected |
|---|---|
| `vm-facts.json` | `cmd_python/py/node/npm/rustc/cargo/pip` = null; no Python registry keys; `network_up` empty |
| Install location | `%LOCALAPPDATA%\Programs\@redrise` of the real user, no folder prompt |
| `health.json` | `healthy`; runtime private; manifest integrity ok; Engine and hooks ok |
| `health-incompatible-python.json` | still `healthy` with a fake `python.exe` first on PATH and bogus `PYTHONHOME`/`PYTHONPATH` |
| P01 plain / incompatible-python | recording complete, compile ok, Runner job `completed_unverified`; host verifier: T07–T09 pass |
| Downloads | none: the run is offline, and no first-use download exists in the package |

## Known gaps this runbook does not cover

The real installer, uninstall/repair and Start-menu entries (P10), signing (P10/P11/P14), Browser runtime (P03), LAN (P10/P13).
