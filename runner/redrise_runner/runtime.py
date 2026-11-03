"""Private-runtime self-check: the Runner must run on the packaged
interpreter, isolated from any global Python, PYTHONPATH or user site."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def report(runtime_dir: Path) -> dict:
    exe = Path(sys.executable).resolve()
    prefix = Path(sys.prefix).resolve()
    runtime_dir = runtime_dir.resolve()
    inside = runtime_dir == exe.parent and prefix == runtime_dir
    foreign_paths = [p for p in sys.path if p and not Path(p).resolve().is_relative_to(runtime_dir.parent.parent)]
    checks = {
        "interpreter_is_private": inside,
        "no_user_site": bool(sys.flags.no_user_site) or "site" not in sys.modules,
        "ignores_environment": bool(sys.flags.ignore_environment) or _pth_mode(runtime_dir),
        "sys_path_confined": not foreign_paths,
    }
    return {
        "python": sys.version.split()[0],
        "executable": str(exe),
        "prefix": str(prefix),
        "sys_path": list(sys.path),
        "foreign_sys_path": foreign_paths,
        "env_python_vars_present": sorted(k for k in os.environ if k.upper().startswith("PYTHON")),
        "checks": checks,
        "ok": all(checks.values()),
    }


def _pth_mode(runtime_dir: Path) -> bool:
    """A `pythonXY._pth` next to the interpreter puts CPython in isolated,
    fixed-path mode (environment variables are ignored)."""
    return any(runtime_dir.glob("python*._pth"))
