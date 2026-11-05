"""Functional smoke of an installed RedRise candidate (release gate, lab only).

Runs a template through the runner's own run_template (same app launch,
Engine spawn without console, verifier and end-of-run rule as the app), with
the Engine of the installed layout. Output goes to a lab folder, never the
real Desktop. Each trial must be `verified`, close the app it opened and leave
no window of that app behind and no tab for its next start.

    python smoke_templates.py --install-root R --out DIR --template boas-vindas --trials N [--load]

Run with the candidate's own runtime python. Waits for 30 s without user
input before each trial; stops (not passed) if the computer is in use or the
Engine reports foreign input. Prints and writes DIR/smoke.json."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from redrise_runner import apps, templates, verifiers
from redrise_runner.engine import EngineClient
from redrise_runner.paths import Layout

IMAGE = {"boas-vindas": "notepad.exe", "excel-pedido": "excel.exe"}


class _LII(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def idle_s() -> float:
    li = _LII(ctypes.sizeof(_LII), 0)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li))
    return (ctypes.windll.kernel32.GetTickCount() - li.dwTime) / 1000


def session_tabs(image: str) -> set[str]:
    """Tabs Notepad keeps for its next start, by file name only (a file per tab, `<id>[.n].bin`)."""
    if image != "notepad.exe":
        return set()
    folders = Path(os.environ["LOCALAPPDATA"], "Packages").glob("Microsoft.WindowsNotepad_*/LocalState/TabState")
    return {f.name.split(".")[0] for d in folders for f in d.iterdir()}


def burners(on: bool) -> list[subprocess.Popen]:
    """Full CPU load (one busy process per core), as after an update."""
    if not on:
        return []
    code = "while True: sum(range(100000))"
    return [subprocess.Popen([sys.executable, "-c", code], creationflags=subprocess.CREATE_NO_WINDOW)
            for _ in range(os.cpu_count() or 4)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--install-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--template", default="boas-vindas")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--load", action="store_true")
    a = ap.parse_args()
    image = IMAGE[a.template]
    if apps.is_running(image):
        print(json.dumps({"passed": False, "stopped": f"{image} already running; close it first"}))
        return 2
    a.out.mkdir(parents=True, exist_ok=True)
    root = a.install_root
    engine = root / "engine" / "redrise-engine.exe"
    rows, passed, stopped = [], True, None
    load = burners(a.load)
    try:
        for t in range(1, a.trials + 1):
            deadline = time.time() + 300
            while idle_s() < 30 and time.time() < deadline:
                time.sleep(3)
            if idle_s() < 30:
                stopped = "computer in use"
                break
            d = a.out / f"{a.template}-{'load' if a.load else 'idle'}-t{t}"
            (d / "Desktop").mkdir(parents=True, exist_ok=True)
            layout = Layout(root, root / "runtime" / "python", engine, d / "data")
            session = session_tabs(image)
            r = templates.run_template(a.template, layout, EngineClient.at(engine), {}, d / "Desktop")
            time.sleep(2)
            left = [w for w in verifiers.top_windows() if w["process_image"] == image]
            added = session_tabs(image) - session
            row = {"trial": t, "state": r.get("state"), "code": r.get("code"), "opened_app": r.get("opened_app"),
                   "windows_left": len(left), "session_tabs_added": len(added)}
            ok = r.get("state") == "verified" and (r.get("opened_app") or {}).get("action") == "closed" and not left and not added
            row["ok"] = ok
            rows.append(row)
            if left:  # never leave lab windows behind for the person
                subprocess.run(["taskkill", "/F", "/IM", image], capture_output=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
                time.sleep(2)
            if r.get("code") == "user_input_detected":
                stopped = "computer in use (Engine guard)"
                break
            passed = passed and ok
    finally:
        for p in load:
            p.kill()
    result = {"template": a.template, "load": a.load, "trials": a.trials, "rows": rows,
              "stopped": stopped, "passed": passed and stopped is None and len(rows) == a.trials}
    (a.out / f"smoke-{a.template}-{'load' if a.load else 'idle'}.json").write_text(
        json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
