"""Practical acceptance of the Boas-vindas process on the installed build (work
order UI-ENGINE-BOAS-VINDAS-20261103). Real app, Core, Runner, Engine, Notepad
and Desktop; synthetic team and synthetic tabs. Run on C: with the private
runtime of the install, computer free, Notepad closed:

    <install>\\runtime\\python\\python.exe -B -X utf8 accept_boas_vindas.py --lab <lab-test> [--only s1,s2]

The app runs isolated: its own data folder and vault namespace, never the
team of the installed app. Stops if someone uses the computer. Files created
on the Desktop are moved to <lab>\\outputs at the end; files that were already
there are compared by hash and never touched. Nothing secret is printed."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from redrise_contracts.client import CoreClient
from redrise_runner import apps, notepad_steps as np, paths, verifiers
from redrise_runner.engine import EngineClient

HERE = Path(__file__).resolve().parent
ROOT = Path(sys.executable).resolve().parents[2]  # <install>\runtime\python\python.exe
SYNTHETIC = "Rascunho sintetico da prova"
PORT = 47810


class _LII(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def idle_s() -> float:
    li = _LII(ctypes.sizeof(_LII), 0)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li))
    return (ctypes.windll.kernel32.GetTickCount() - li.dwTime) / 1000


class Stop(Exception):
    pass


class Lab:
    def __init__(self, lab: Path):
        self.lab = lab
        self.acct = json.loads((lab / "test-account.json").read_text(encoding="utf-8-sig"))
        self.layout = paths.resolve(ROOT, lab / "data")
        self.engine = EngineClient.at(self.layout.engine)
        self.desk = np.UiaDesk()
        self.pid: int | None = None
        self.api: CoreClient | None = None
        self.seq = 0
        self.current: dict | None = None  # result of a scenario whose cleanup is still to come
        self.synthetic = ""  # what the editor shows: Notepad may autocorrect what is typed
        self.tabstate = next(Path(os.environ["LOCALAPPDATA"], "Packages").glob("Microsoft.WindowsNotepad_*")) / "LocalState" / "TabState"

    def guard(self, need: float = 30.0, patience: float = 180.0) -> None:
        """Waits for a quiet computer (the proof's own input also counts); stops if input keeps coming."""
        end = time.monotonic() + patience
        while idle_s() < need:
            if time.monotonic() >= end:
                raise Stop(f"computer in use (idle {int(idle_s())} s); nothing else was started")
            time.sleep(2)

    def ui(self, *a: str) -> subprocess.CompletedProcess:
        env = {**os.environ, "RR_UI_PID": str(self.pid)}
        return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HERE / "ui.ps1"), *a],
                              capture_output=True, encoding="utf-8", errors="replace", env=env)

    def texts(self) -> list[str]:
        return self.ui("-Do", "dump").stdout.splitlines()

    def wait_ui(self, pattern: str, timeout: float = 90.0) -> bool:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if any(line.startswith(pattern) for line in self.texts()):
                return True
            time.sleep(2)
        return False

    def start_app(self) -> None:
        env = {**os.environ, "REDRISE_DATA_ROOT": str(self.lab / "data"), "REDRISE_TEST_VAULT": "rrtest2",
               "WEBVIEW2_USER_DATA_FOLDER": str(self.lab / "webview")}
        p = subprocess.Popen([str(ROOT / "RedRise.exe")], env=env, close_fds=True)
        self.pid = p.pid
        (self.lab / "pid.txt").write_text(str(p.pid), encoding="ascii")
        if not self.wait_ui("Edit|E-mail ou usu"):
            raise Stop("access screen not reached")
        cfg = json.loads((self.lab / "data" / "host" / "host.json").read_text(encoding="utf-8-sig"))
        if cfg.get("lan_port") != PORT:
            raise Stop("not the isolated team")
        self.ui("-Do", "set", "-Name", "E-mail ou usuário", "-Type", "Edit", "-Value", self.acct["admin_user"])
        self.ui("-Do", "set", "-Name", "Senha", "-Type", "Edit", "-Value", self.acct["admin_password"])
        self.ui("-Do", "invoke", "-Name", "Entrar", "-Type", "Button")
        if not self.wait_ui("Button|Sair", 60):
            raise Stop("sign-in failed")
        self.api = CoreClient("127.0.0.1", PORT, cfg["fingerprint"])
        token = self.api.call("POST", "/api/v1/login", {"username": self.acct["admin_user"], "password": self.acct["admin_password"]})["token"]
        self.api = CoreClient("127.0.0.1", PORT, cfg["fingerprint"], token)
        end = time.monotonic() + 60
        while time.monotonic() < end:
            st = self.api.call("GET", "/api/v1/stations")
            if any(s.get("online") and s.get("session_state") == "ready" for s in st):
                return
            time.sleep(2)
        raise Stop("station not ready")

    def close_app(self) -> None:
        if not self.pid:
            return
        self.dismiss_sheet()
        for _ in range(5):  # the window may be behind Notepad: the driver refuses input until it is in front
            self.ui("-Do", "invoke", "-Name", "Fechar", "-Type", "Button")
            end = time.monotonic() + 25
            while time.monotonic() < end:
                if not apps.is_running("redrise.exe"):
                    return
                time.sleep(1)

    def screens(self) -> None:
        """Screens with persisted data, for inspection."""
        self.dismiss_sheet()
        for page, item in (("processo-acao", "Ação"), ("rotina-lista", "Lista"), ("processo-historico", "Histórico")):
            self.ui("-Do", "invoke", "-Name", item, "-Type", "Hyperlink")
            time.sleep(3)
            self.ui("-Do", "shot", "-Out", str(self.lab / f"screen-{page}.png"))

    # -- Notepad preparation, own synthetic tabs only
    def send(self):
        self.seq += 1
        return np.engine_sender(f"proof-{time.strftime('%H%M%S')}-{self.seq}", self.layout, self.engine, threading.Event())

    def launch(self) -> int:
        hwnd = self.desk.launch()
        if hwnd is None:
            raise Stop("notepad did not open")
        return hwnd

    def unsaved_window(self) -> int:
        hwnd = self.launch()
        job = self.send()(hwnd, [np.typed(SYNTHETIC)])
        self.synthetic = self.desk.text(hwnd) or ""
        if job.get("state") != "completed_unverified" or len(self.synthetic) != len(SYNTHETIC):
            raise Stop("synthetic tab not prepared")
        return hwnd

    def discard_synthetic(self, hwnd: int) -> None:
        """Closes the one synthetic tab left by a scenario. Anything else is left alone."""
        tabs = self.desk.tabs(hwnd)
        if len(tabs) != 1 or not self.synthetic or self.desk.text(hwnd) != self.synthetic:
            raise Stop("not the synthetic tab of the proof; left open")
        send = self.send()
        try:
            if not np._bring_forward(self.desk, send, hwnd):
                raise Stop(f"could not bring the synthetic tab forward; foreground {self.desk.foreground()}")
            np._close_tab(self.desk, send, hwnd, tabs[0].tab_id, discardable=(self.synthetic,))
        except np._Stop as e:
            raise Stop(f"synthetic tab not closed: {e.code} {e.detail}; foreground {self.desk.foreground()}") from e

    def require_closed(self) -> None:
        if self.desk.windows():
            raise Stop("a Notepad window is open; this scenario starts with it closed")
        if list(self.tabstate.glob("*")):
            raise Stop("Notepad would restore an earlier session; this scenario starts without one")

    # -- run through the app
    def dismiss_sheet(self) -> None:
        """The execution detail opens in a modal side sheet after each run; it hides the menu until closed."""
        if not any(line.startswith("Button|Sair") for line in self.texts()):
            self.ui("-Do", "invoke", "-Name", "Fechar", "-Type", "Button")
            self.wait_ui("Button|Sair", 10)

    def run_ui(self) -> dict:
        self.guard()
        self.dismiss_sheet()
        known = {e["id"] for e in self.api.call("GET", "/api/v1/executions")}
        self.ui("-Do", "invoke", "-Name", "Ação", "-Type", "Hyperlink")
        if not self.wait_ui("Button|Executar processo", 30):
            raise Stop("Boas-vindas not offered in Processo > Acao: " + self.ui("-Do", "dump").stdout[:600])
        self.ui("-Do", "invoke", "-Name", "Executar processo", "-Type", "Button")
        if not self.wait_ui("Button|Confirmar execu", 15):
            raise Stop("run dialog not shown")
        self.ui("-Do", "invoke", "-Name", "Confirmar execução", "-Type", "Button")
        end = time.monotonic() + 240
        while time.monotonic() < end:
            fresh = [e for e in self.api.call("GET", "/api/v1/executions") if e["id"] not in known]
            if fresh and fresh[0]["state"] == "finished":
                return fresh[0]
            time.sleep(1)
        raise Stop("execution did not finish in time")

    def cli(self, step: str, ctx: dict | None) -> dict:
        self.guard()
        cf = self.lab / "ctx.json"
        args = [sys.executable, "-B", "-X", "utf8", "-m", "redrise_runner", "--data-root", str(self.lab / "data"), "notepad-step", "--step", step]
        if ctx is not None:
            cf.write_text(json.dumps(ctx, ensure_ascii=False), encoding="utf-8")
            args += ["--context-file", str(cf)]
        r = subprocess.run(args, capture_output=True, encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)
        return json.loads(r.stdout)


def summary(e: dict) -> dict:
    ctx = e.get("context") or {}
    steps = ctx.get("steps") or {}
    open_ref = (steps.get("1") or {}).get("notepad") or {}
    save = steps.get("2") or {}
    return {"outcome": e["outcome"], "end_reason": e["end_reason"], "steps": [(s["position"], s["name"], s["state"], s["verified"], s.get("error_code")) for s in e["steps"]],
            "mode": open_ref.get("mode"), "window_of_run": open_ref.get("window_of_run"), "tabs_before": len(open_ref.get("tabs_before") or []),
            "output_name": save.get("output_name"), "name_conflicts": save.get("name_conflicts"), "verification": save.get("verification"),
            "final": (steps.get("3") or {}).get("final")}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def outputs(folder: Path) -> dict[str, str]:
    return {p.name: sha(p) for p in folder.iterdir() if p.is_file() and p.name.startswith(np.STEM)}


def expect(res: dict, cond: bool, what: str) -> None:
    res.setdefault("checks", []).append({"check": what, "ok": bool(cond)})


def check_output(res: dict, folder: Path, expected_name: str) -> None:
    """Independent of the Runner: the name is the first free one and the bytes are the text, nothing else."""
    expect(res, res.get("output_name") == expected_name, f"saved as {expected_name}")
    p = folder / expected_name
    expect(res, p.is_file() and p.read_bytes() == np.TEXT.encode("utf-8"), "the file holds exactly the text")


def s1_clean(lab: Lab, folder: Path) -> dict:
    lab.require_closed()
    name = np.free_name(folder)
    res = summary(lab.run_ui())
    check_output(res, folder, name)
    expect(res, res["outcome"] == "verified" and res["end_reason"] == "sequence_end", "three steps verified, in order")
    expect(res, res["mode"] == "clean" and res["tabs_before"] == 0, "the only empty untitled tab was reused")
    expect(res, res["final"] and res["final"]["window_closed"], "the window of the run closed")
    expect(res, not lab.desk.windows(), "no Notepad window left")
    expect(res, not list(lab.tabstate.glob("*")), "no session left to restore")
    return res


def s2_open_with_unsaved(lab: Lab, folder: Path) -> dict:
    lab.require_closed()
    hwnd = lab.unsaved_window()
    before = [t.tab_id for t in lab.desk.tabs(hwnd)]
    name = np.free_name(folder)
    res = summary(lab.run_ui())
    check_output(res, folder, name)
    expect(res, res["outcome"] == "verified", "three steps verified, in order")
    expect(res, res["mode"] == "already_open" and res["tabs_before"] == 1, "a dedicated tab was created")
    expect(res, lab.desk.is_window(hwnd), "the window stayed open")
    expect(res, [t.tab_id for t in lab.desk.tabs(hwnd)] == before, "only the tab of the run closed")
    expect(res, lab.desk.text(hwnd) == lab.synthetic, "the unsaved tab kept its text")
    lab.current = res
    lab.discard_synthetic(hwnd)
    return res


def s3_restored_session(lab: Lab, folder: Path) -> dict:
    lab.require_closed()
    hwnd = lab.unsaved_window()
    apps.close_windows([hwnd], 5)
    time.sleep(1)
    restored_state = len(list(lab.tabstate.glob("*")))
    name = np.free_name(folder)
    res = summary(lab.run_ui())
    check_output(res, folder, name)
    res["session_state_files"] = restored_state
    expect(res, restored_state > 0 and not lab.desk.is_window(hwnd), "Notepad kept the unsaved tab for the next start")
    expect(res, res["outcome"] == "verified", "three steps verified, in order")
    expect(res, res["mode"] == "restored_session" and res["tabs_before"] == 1, "a dedicated tab next to the restored one")
    wins = lab.desk.windows()
    expect(res, len(wins) == 1, "the window stayed open")
    expect(res, wins and len(lab.desk.tabs(wins[0])) == 1 and lab.desk.text(wins[0]) == lab.synthetic, "the restored tab kept its text")
    lab.current = res
    if wins:
        lab.discard_synthetic(wins[0])
    return res


def s4_extra_tabs(lab: Lab, folder: Path) -> dict:
    lab.require_closed()
    name = np.free_name(folder)
    r1 = lab.cli("open", None)
    r2 = lab.cli("save", r1.get("context"))
    res = {"via": "installed Runner CLI, so that synthetic tabs can be added between the steps", "states": [r1["state"], r2["state"]],
           "output_name": (r2.get("context") or {}).get("output_name")}
    expect(res, res["states"] == ["verified", "verified"], "open and save verified")
    check_output(res, folder, name)
    hwnd = r1["context"]["notepad"]["window"]
    send = lab.send()
    job = send(hwnd, [np.key(np.VK_T, "ctrl")])
    job2 = send(hwnd, [np.typed(np.TEXT)])  # the run's own text: its unsaved change may be discarded
    job3 = send(hwnd, [np.key(np.VK_T, "ctrl")])  # empty and untitled
    expect(res, all(j.get("state") == "completed_unverified" for j in (job, job2, job3)) and len(lab.desk.tabs(hwnd)) == 3, "two extra tabs of the run in its window")
    r3 = lab.cli("close", r2["context"])
    res["close"] = r3.get("context", {}).get("final") if r3["state"] == "verified" else {k: r3.get(k) for k in ("state", "code", "detail")}
    expect(res, r3["state"] == "verified" and res["close"].get("extra_tabs_closed") == 2 and res["close"].get("window_closed"), "extras closed, 'Nao salvar' only on them, window closed")
    expect(res, not lab.desk.windows() and not list(lab.tabstate.glob("*")), "no window or session left")
    return res


def s4b_other_tab_in_window_of_run(lab: Lab, folder: Path) -> dict:
    lab.require_closed()
    name = np.free_name(folder)
    r1 = lab.cli("open", None)
    r2 = lab.cli("save", r1.get("context"))
    res = {"via": "installed Runner CLI", "states": [r1["state"], r2["state"]], "output_name": (r2.get("context") or {}).get("output_name")}
    expect(res, res["states"] == ["verified", "verified"], "open and save verified")
    check_output(res, folder, name)
    hwnd = r1["context"]["notepad"]["window"]
    send = lab.send()
    send(hwnd, [np.key(np.VK_T, "ctrl")])
    send(hwnd, [np.typed(SYNTHETIC)])  # stands for a tab a person opened meanwhile
    lab.synthetic = lab.desk.text(hwnd) or ""
    other = next(t.tab_id for t in lab.desk.tabs(hwnd) if t.selected)
    r3 = lab.cli("close", r2["context"])
    res["close"] = r3.get("context", {}).get("final") if r3["state"] == "verified" else {k: r3.get(k) for k in ("state", "code", "detail")}
    lab.current = res
    expect(res, r3["state"] == "verified" and res["close"].get("window_closed") is False, "verified, and the window stayed open")
    expect(res, lab.desk.is_window(hwnd) and [t.tab_id for t in lab.desk.tabs(hwnd)] == [other], "only the other tab is left")
    expect(res, lab.desk.text(hwnd) == lab.synthetic, "the other tab kept its text, nothing was discarded")
    lab.discard_synthetic(hwnd)
    return res


def s5_collision_in_dialog(lab: Lab, folder: Path) -> dict:
    lab.require_closed()
    target = folder / np.free_name(folder)
    created: list[str] = []

    def rival():
        end = time.monotonic() + 200
        while time.monotonic() < end:
            if lab.desk.dialogs() >= 1:
                target.write_text("arquivo sintetico de outro programa", encoding="utf-8")
                created.append(target.name)
                return
            time.sleep(0.1)
    t = threading.Thread(target=rival, daemon=True)
    t.start()
    res = summary(lab.run_ui())
    t.join(1)
    check_output(res, folder, res.get("output_name") or "missing")
    expect(res, created == [target.name], "a file appeared under the chosen name while Save As was open")
    expect(res, res["outcome"] == "verified", "three steps verified, in order")
    expect(res, res["name_conflicts"] == [target.name], "the overwrite question was refused")
    expect(res, target.read_text(encoding="utf-8") == "arquivo sintetico de outro programa", "the other file was preserved")
    expect(res, res["output_name"] and res["output_name"] != target.name and "[" in res["output_name"], "saved under the next free name")
    return res


def s6_lost_target(lab: Lab, folder: Path) -> dict:
    lab.require_closed()
    r1 = lab.cli("open", None)
    hwnd = r1["context"]["notepad"]["window"]
    before = outputs(folder)
    lab.send()(hwnd, [np.key(np.VK_W, "ctrl")])  # the clean tab closes the window: the target is gone
    time.sleep(1)
    r2 = lab.cli("save", r1["context"])
    res = {"via": "installed Runner CLI", "state": r2["state"], "code": r2.get("code"), "diagnostic_code": (r2.get("diagnostic") or {}).get("error_code")}
    expect(res, r2["state"] == "failed" and r2.get("code") == "notepad_target_lost", "stopped with a diagnostic before typing")
    expect(res, outputs(folder) == before and not lab.desk.windows(), "nothing was saved and nothing was opened")
    return res


SCENARIOS = {"s1": s1_clean, "s2": s2_open_with_unsaved, "s3": s3_restored_session, "s4": s4_extra_tabs,
             "s4b": s4b_other_tab_in_window_of_run, "s5": s5_collision_in_dialog, "s6": s6_lost_target}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lab", type=Path, required=True)
    ap.add_argument("--only", default=",".join(SCENARIOS))
    a = ap.parse_args()
    lab = Lab(a.lab)
    folder = lab.desk.desktop()
    start = outputs(folder)
    report: dict = {"at": time.strftime("%Y-%m-%d %H:%M"), "install": json.loads((ROOT / "manifest.json").read_text(encoding="utf-8-sig")).get("app_version"),
                    "desktop_files_before": sorted(start), "scenarios": {}}
    try:
        lab.guard()
        lab.start_app()
        for name in a.only.split(","):
            print("==", name, flush=True)
            lab.current = None
            try:
                res = SCENARIOS[name](lab, folder)
            except Stop:
                if lab.current:
                    report["scenarios"][name] = lab.current
                    print(json.dumps(lab.current, ensure_ascii=False), flush=True)
                raise
            report["scenarios"][name] = res
            print(json.dumps(res, ensure_ascii=False), flush=True)
            if not all(c["ok"] for c in res.get("checks", [])):
                raise Stop(f"{name}: a check failed")
            time.sleep(3)
        lab.screens()
    except Stop as e:
        report["stopped"] = str(e)
        print("STOPPED:", e, flush=True)
    except Exception as e:  # noqa: BLE001 - a crash of the proof is never a pass
        report["stopped"] = f"{type(e).__name__}: {e}"
        print("STOPPED:", report["stopped"], flush=True)
    finally:
        lab.close_app()
        end = outputs(folder)
        report["originals_unchanged"] = all(end.get(k) == v for k, v in start.items())
        new = [n for n in end if n not in start]
        report["outputs"] = {n: end[n] for n in new}
        keep = a.lab / "outputs" / time.strftime("%Y%m%d-%H%M%S")
        keep.mkdir(parents=True, exist_ok=True)
        for n in new:
            os.replace(folder / n, keep / n)
        report["outputs_moved_to"] = "lab-test/outputs"
        report["originals_checked"] = len(start)
        report["partial"] = set(report["scenarios"]) != set(SCENARIOS)
        report["passed"] = "stopped" not in report and report["originals_unchanged"] and not report["partial"] and \
            all(all(c["ok"] for c in r.get("checks", [])) for r in report["scenarios"].values())
        out = a.lab / f"accept-{time.strftime('%Y%m%d-%H%M%S')}.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("REPORT", out, "passed =", report["passed"], flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
