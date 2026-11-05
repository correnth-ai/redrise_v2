"""Practical proof of the end of the boas-vindas template on the real Notepad: a clean start leaves no
window and no tab for the next start; a restored session comes back as it was, without the tab of the run.

    <python> -B -X utf8 accept_template_close.py --install-root R --lab DIR

Lab only, synthetic data, output in a lab folder. Refuses while Notepad is open or keeps tabs of a session,
which would be the person's. Waits for a quiet computer; the Engine guard stops on any input."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import threading
import time
from pathlib import Path

from redrise_runner import __version__, apps, notepad_steps as np, templates, verifiers
from redrise_runner.engine import EngineClient
from redrise_runner.paths import Layout

SYNTHETIC = "Guia de prova 12345"


class _LII(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def idle_s() -> float:
    li = _LII(ctypes.sizeof(_LII), 0)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li))
    return (ctypes.windll.kernel32.GetTickCount() - li.dwTime) / 1000


def session_files() -> set[str]:
    """File names only: the content of a session is never read here."""
    folders = Path(os.environ["LOCALAPPDATA"], "Packages").glob("Microsoft.WindowsNotepad_*/LocalState/TabState")
    return {f.name.split(".")[0] for d in folders for f in d.iterdir()}


def wait_quiet(need_s: float = 45, timeout_s: float = 900) -> bool:
    end = time.time() + timeout_s
    while idle_s() < need_s:
        if time.time() > end:
            return False
        time.sleep(3)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--install-root", type=Path, required=True)
    ap.add_argument("--lab", type=Path, required=True)
    a = ap.parse_args()
    if apps.is_running("notepad.exe") or session_files():
        print(json.dumps({"passed": False, "stopped": "Notepad is open or keeps a session; left alone"}))
        return 2
    run = a.lab / f"template-close-{time.strftime('%Y%m%d-%H%M%S')}"
    engine = a.install_root / "engine" / "redrise-engine.exe"
    client = EngineClient.at(engine)
    report: dict = {"runner": __version__, "scenarios": {}}
    desk = np.UiaDesk()

    def layout(name: str) -> tuple[Layout, Path]:
        (run / name / "Desktop").mkdir(parents=True, exist_ok=True)
        return Layout(a.install_root, a.install_root / "runtime" / "python", engine, run / name / "data"), run / name / "Desktop"

    def windows() -> int:
        return sum(1 for w in verifiers.top_windows() if w["process_image"] == "notepad.exe")

    def checks(name: str, items: list[tuple[str, bool]], **extra) -> bool:
        ok = all(c for _, c in items)
        report["scenarios"][name] = {"passed": ok, "checks": [{"check": k, "ok": bool(c)} for k, c in items], **extra}
        return ok

    try:
        if not wait_quiet():
            report["stopped"] = "computer in use"
            return 1
        # clean start
        lay, folder = layout("clean")
        r = templates.run_template("boas-vindas", lay, client, {}, folder)
        time.sleep(2)
        ok = checks("clean", [("verified", r.get("state") == "verified"),
                              ("the app closed", (r.get("opened_app") or {}).get("action") == "closed"),
                              ("no window left", windows() == 0),
                              ("no tab for the next start", not session_files())],
                    state=r.get("state"), code=r.get("code"), opened_app=r.get("opened_app"))
        if not ok or not wait_quiet():
            return 1

        # restored session: a synthetic tab left by closing the window, as Notepad keeps it
        lay, folder = layout("restored")
        hwnd = desk.launch()
        send = np.engine_sender(f"proof-{time.strftime('%H%M%S')}", lay, client, threading.Event())
        send(hwnd, [np.typed(SYNTHETIC)])
        text = desk.text(hwnd)
        apps.close_windows([hwnd], 5)
        time.sleep(2)
        kept = len(session_files())
        r = templates.run_template("boas-vindas", lay, client, {}, folder)
        time.sleep(2)
        after = len(session_files())
        again = desk.launch()
        tabs = desk.tabs(again)
        back = desk.text(again)
        ok = checks("restored", [("the synthetic tab was kept by the session", kept == 1 and text == SYNTHETIC),
                                 ("verified", r.get("state") == "verified"),
                                 ("the app closed", (r.get("opened_app") or {}).get("action") == "closed"),
                                 ("the session holds only the restored tab", after == 1),
                                 ("reopened with that tab alone, text intact", len(tabs) == 1 and back == SYNTHETIC)],
                    state=r.get("state"), code=r.get("code"), opened_app=r.get("opened_app"))
        if tabs and back == SYNTHETIC:  # leave the lab as it was: only the synthetic tab is discarded
            np._close_tab(desk, send, again, tabs[0].tab_id, discardable=(SYNTHETIC,))
            time.sleep(1)
        report["left"] = {"windows": windows(), "session_files": len(session_files())}
        return 0 if ok and windows() == 0 and not session_files() else 1
    finally:
        desk.close()
        report["passed"] = all(s["passed"] for s in report["scenarios"].values()) and len(report["scenarios"]) == 2 and report.get("left") == {"windows": 0, "session_files": 0}
        run.mkdir(parents=True, exist_ok=True)
        (run / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    sys.exit(main())
