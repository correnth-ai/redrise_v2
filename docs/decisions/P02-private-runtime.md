# P02 — private runtime layout and Runner (decisions)

Status: accepted for development (2026-10-27); **P02 acceptance pending the clean-machine run** ([runbook](../../packaging/runtime/CLEAN-MACHINE-P02.md)).

| ID | Decision | Why / evidence |
|---|---|---|
| P02-D1 | Layout `@redrise\{engine,runtime\python,runner,licenses}` + `manifest.json`, installed per user at `%LOCALAPPDATA%\Programs\@redrise`; mutable data at `%LOCALAPPDATA%\RedRise\{jobs,locks,logs}` (Runner resolves the real folder with `SHGetKnownFolderPath`) | U25/U26-INSTALL; binaries and data are separate; the install tree stays byte-identical after a run (manifest re-check) |
| P02-D2 | Private CPython **3.12.10 x64** from the official nuget.org package `python` (PSF). SHA512 is checked against the NuGet catalog at build time. Pruned: pip/site-packages, tests, Tk/IDLE, venv, ensurepip, dev headers | No customer Python or pip. The PSF licence is shipped in `licenses/` |
| P02-D3 | `python312._pth` fixes `sys.path` to `Lib`, `DLLs`, `..\..\runner`; CPython then ignores `PYTHON*` variables and the user site | Proven on the dev machine with bogus PYTHONHOME/PYTHONPATH/PYTHONSTARTUP and no Python on PATH |
| P02-D4 | PyInstaller **not used**: the Runner is stdlib-only source on the private interpreter, launched with `-B` (no `.pyc` written into the install) | Simpler, inspectable, no bootloader; the manifest covers every file |
| P02-D5 | Launcher `redrise-runner.cmd` is a development form; the end-user launcher is the desktop app (P08) and the installer entries (P10) | The `.cmd` is not called a distributable product |
| P02-D6 | Runner → Engine via the E01 CLI contract, cancellation via `--stop-file` (cooperative, never killed mid-input); one UI job per session (OS file lock); a job id runs at most once; category/platform checked before any Engine action; `verified` is never set by the Runner | B11–B15 groundwork; Runner tests |
| P02-D7 | `health` verifies manifest integrity (missing/modified/unexpected files) | Tamper test: modified `jobs.py` → unhealthy |
| P02-D8 | Engine crate inventory generated with `cargo tree` into `licenses/engine-crates.json` (a superset that includes build-time proc-macros) | Licences: MIT / Apache-2.0 / Unlicense / Unicode-3.0; no copyleft |

Not decided here: installer technology, code signing, update channel (P10/P11), session-unavailable *waiting* policy (P07; the Runner currently refuses with the reason).
