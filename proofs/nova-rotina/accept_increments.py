"""Practical acceptance of increments 1 to 4 of work order UI-ENGINE-BOAS-VINDAS-20261103
on the installed candidate. Real app, Core, Runner and Windows; synthetic team. Run on
C: with the private runtime of the install, computer free:

    <install>\\runtime\\python\\python.exe -B -X utf8 accept_increments.py --lab <lab-test> [--only a,b]

The app runs isolated: its own data folder and vault namespace, never the team of the
installed app. Stops if someone uses the computer. The only application opened is the
Calculator, closed at the end, and only windows this proof opened are closed. Nothing
secret is printed.

 migration  team created by an earlier version reopens: backup taken, data kept.
 list       titles, cards and the table with persisted rows.
 start      Nova Rotina: real app list, preparation opens nothing, Quer testar? opens it.
 picker     Outro...: the real Windows file picker, cancel and choose.
 run        a standalone app routine through its execution on the real Runner.
 review     real run pauses; bell; Marcado para mim; Aprovado!; ends verified.
 step1      replacing step 1 through the screen, refused while running.
 report     a real run saves the PDF; Veja aqui! opens its folder in the Explorer.
 live       a change made elsewhere reaches the open table without waiting for the periodic read."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from redrise_contracts.client import CoreClient
from redrise_runner import apps, verifiers

HERE = Path(__file__).resolve().parent
UI = HERE.parent / "boas-vindas" / "ui.ps1"
ROOT = Path(sys.executable).resolve().parents[2]  # <install>\runtime\python\python.exe
PORT = 47810
APP = "Calculadora"
FRAME = "applicationframehost.exe"


class Stop(Exception):
    pass


class _LII(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def idle_s() -> float:
    li = _LII(ctypes.sizeof(_LII), 0)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li))
    return (ctypes.windll.kernel32.GetTickCount() - li.dwTime) / 1000


def _cursor() -> list[int]:
    p = (ctypes.c_long * 2)()
    ctypes.windll.user32.GetCursorPos(p)
    return [p[0], p[1]]


def calc_windows() -> set[int]:
    return {w["hwnd"] for w in verifiers.top_windows() if w["process_image"] in ("calculatorapp.exe", FRAME)}


class Lab:
    def __init__(self, lab: Path, shots: Path):
        self.lab, self.shots = lab, shots
        self.acct = json.loads((lab / "test-account.json").read_text(encoding="utf-8-sig"))
        self.pid: int | None = None
        self.api: CoreClient | None = None
        self.seq = uuid.uuid4().hex[:4]
        self.clicks_lost: list[dict] = []

    def guard(self, need: float = 20.0, patience: float = 180.0) -> None:
        end = time.monotonic() + patience
        while idle_s() < need:
            if time.monotonic() >= end:
                raise Stop(f"computer in use (idle {int(idle_s())} s); nothing else was started")
            time.sleep(2)

    def ui(self, *a: str) -> subprocess.CompletedProcess:
        env = {**os.environ, "RR_UI_PID": str(self.pid)}
        out = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(UI), *a],
                             capture_output=True, encoding="cp850", errors="replace", env=env)  # the console code page of PowerShell here
        if out.returncode == 3 or "NOT_FOREGROUND" in out.stdout:
            raise Stop("the app window did not come to the front: no input sent")
        return out

    def texts(self) -> list[str]:
        return self.ui("-Do", "dump").stdout.splitlines()

    def has(self, *needles: str) -> bool:
        lines = self.texts()
        return all(any(n in line for line in lines) for n in needles)

    def wait(self, *needles: str, timeout: float = 60.0) -> None:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.has(*needles):
                return
            time.sleep(1.5)
        raise Stop(f"not on screen: {needles}; screen: " + " / ".join(self.texts())[:900])

    def invoke(self, name: str, kind: str = "Button") -> None:
        out = self.ui("-Do", "invoke", "-Name", name, "-Type", kind)
        if "invoked" not in out.stdout:
            raise Stop(f"could not invoke {name}: {out.stderr[:300]}")

    def click(self, name: str, kind: str = "Button") -> None:
        out = self.ui("-Do", "click", "-Name", name, "-Type", kind)
        if "clicked" not in out.stdout:
            raise Stop(f"could not click {name}: {out.stderr[:300]}")

    def pick(self, label: str, then: str, ups: int) -> None:
        """Chooses a radio. Its label, as a person clicks it; if that click does not take, the keyboard, as a
        person would too, and what was lost is recorded. What the choice reveals decides, not the input."""
        self.click(label, "Text")
        end = time.monotonic() + 3
        while time.monotonic() < end:
            if self.has(then):
                return
            time.sleep(0.4)
        rect = self.ui("-Do", "rect", "-Name", label, "-Type", "Text").stdout.strip()
        self.clicks_lost.append({"label": label, "where": rect, "cursor": _cursor()})
        self.ui("-Do", "focus", "-Name", "Nome da rotina", "-Type", "Edit")
        self.ui("-Do", "keys", "-Value", "{TAB}" + "{UP}" * ups)
        end = time.monotonic() + 4
        while time.monotonic() < end:
            if self.has(then):
                return
            time.sleep(0.4)
        raise Stop(f"not on screen after choosing {label}: {then}")

    def fill(self, name: str, value: str, kind: str = "Edit", check: bool = True) -> None:
        # Right after the window comes to the front the first keys can be lost: what the field holds decides.
        for _ in range(3):
            out = self.ui("-Do", "set", "-Name", name, "-Type", kind, "-Value", value)
            if "set " not in out.stdout:
                raise Stop(f"could not fill {name}: {out.stderr[:300]}")
            time.sleep(0.3)
            if not check or any(line.startswith(f"{kind}|{name}|") and line.split("|", 2)[2] == value for line in self.texts()):
                return
        raise Stop(f"{name} did not keep what was typed")

    def choose(self, field: str, text: str) -> None:
        """Types in a searchable list and takes the first match by keyboard."""
        self.fill(field, text, "ComboBox")
        time.sleep(0.6)
        self.ui("-Do", "keys", "-Value", "{ENTER}")
        time.sleep(0.4)

    def shot(self, name: str) -> None:
        self.ui("-Do", "shot", "-Out", str(self.shots / f"inst-{name}.png"))

    def start_app(self) -> None:
        env = {**os.environ, "REDRISE_DATA_ROOT": str(self.lab / "data"), "REDRISE_TEST_VAULT": "rrtest2",
               "WEBVIEW2_USER_DATA_FOLDER": str(self.lab / "webview")}
        self.pid = subprocess.Popen([str(ROOT / "RedRise.exe")], env=env, close_fds=True).pid
        (self.lab / "pid.txt").write_text(str(self.pid), encoding="ascii")
        self.wait("E-mail ou usu", timeout=120)
        cfg = json.loads((self.lab / "data" / "host" / "host.json").read_text(encoding="utf-8-sig"))
        if cfg.get("lan_port") != PORT:
            raise Stop("not the isolated team")
        self.fill("E-mail ou usuário", self.acct["admin_user"])
        self.fill("Senha", self.acct["admin_password"], check=False)  # a password field does not show its value; signing in decides
        self.invoke("Entrar")
        self.wait("Sair", timeout=60)
        c = CoreClient("127.0.0.1", PORT, cfg["fingerprint"])
        token = c.call("POST", "/api/v1/login", {"username": self.acct["admin_user"], "password": self.acct["admin_password"]})["token"]
        self.api = CoreClient("127.0.0.1", PORT, cfg["fingerprint"], token)
        end = time.monotonic() + 90
        while time.monotonic() < end:
            st = self.api.call("GET", "/api/v1/stations")
            ready = [s for s in st if s.get("online") and s.get("session_state") == "ready"]
            if ready:
                self.station = ready[0]["id"]
                return
            time.sleep(2)
        raise Stop("station not ready")

    def close_app(self) -> None:
        if not self.pid:
            return
        self.ui("-Do", "keys", "-Value", "{ESC}")
        for _ in range(4):
            self.ui("-Do", "invoke", "-Name", "Fechar", "-Type", "Button")
            end = time.monotonic() + 20
            while time.monotonic() < end:
                if not apps.is_running("redrise.exe"):
                    return
                time.sleep(1)

    def page(self, item: str) -> None:
        self.invoke(item, "Hyperlink")
        time.sleep(1.2)

    def empty_process(self, name: str) -> dict:
        return self.api.call("POST", "/api/v1/processes", {"name": name, "items": []})

    def close_new_calc(self, before: set[int]) -> list[int]:
        new = [h for h in calc_windows() - before]
        return apps.close_windows(new) if new else []

    def wait_execution(self, eid: str, states: tuple[str, ...], timeout: float = 90.0) -> dict:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            e = self.api.call("GET", f"/api/v1/executions/{eid}")
            if e["state"] in states:
                return e
            time.sleep(1)
        raise Stop(f"execution stayed {e['state']}: {[s['state'] for s in e['steps']]}")

    # ---------------------------------------------------------------- scenarios
    def s_migration(self) -> dict:
        backups = sorted(p.name for p in (self.lab / "data" / "host" / "backups").iterdir())
        procs = self.api.call("GET", "/api/v1/processes")
        welcome = [p for p in procs if p["system_key"]]
        execs = self.api.call("GET", "/api/v1/executions")
        ok = len(welcome) == 1 and len(welcome[0]["items"]) == 3 and bool(execs)
        return {"passed": ok, "backups": backups[-3:], "welcome_steps": len(welcome[0]["items"]) if welcome else 0, "executions_kept": len(execs)}

    def s_list(self) -> dict:
        self.page("Lista")
        self.wait("Nova Rotina", "Testes (em breve)", "Por gravação (em breve)", "Mostrando", "Linhas por página")
        self.shot("rotina-lista")
        self.page("Ação")
        self.wait("Visão Geral", "Marcado para mim", "Executar processo")
        self.shot("processo-acao")
        return {"passed": True}

    def s_start(self) -> dict:
        name = f"Prova inicio {self.seq}"
        self.empty_process(name)
        self.guard()
        self.page("Lista")
        self.invoke("Nova Rotina")
        self.wait("Nome da rotina", "Iniciar um processo")
        self.fill("Nome da rotina", f"Abrir calculadora {self.seq}")
        self.pick("Iniciar um processo", "ComboBox|", 2)
        self.choose("Processo", name)
        self.invoke("Continuar")
        self.wait("O que abrir", "Estação")
        time.sleep(3)  # the list of the real station
        self.choose("O que abrir", APP)
        self.shot("nova-rotina-destino")
        if calc_windows() and any(w["process_image"] == "calculatorapp.exe" for w in verifiers.top_windows()):
            raise Stop("the Calculator is open: close it and repeat")
        before = calc_windows()
        self.invoke("Salvar e preparar")
        self.wait("Deu tudo certo!", "Quer testar?", timeout=90)
        time.sleep(1)
        opened_by_preparing = calc_windows() - before
        self.shot("nova-rotina-preparada")
        self.invoke("Quer testar?")
        self.wait("Janela confirmada na estação.", timeout=60)
        time.sleep(1)
        opened = calc_windows() - before
        self.shot("nova-rotina-testada")
        left = self.close_new_calc(before)
        items = next(p for p in self.api.call("GET", "/api/v1/processes") if p["name"] == name)["items"]
        self.invoke("Concluir")
        passed = not opened_by_preparing and bool(opened) and not left and len(items) == 1 and items[0]["kind"] == "app_open"
        return {"passed": passed, "windows_after_preparing": len(opened_by_preparing), "windows_after_test": len(opened), "not_closed": len(left)}

    def s_picker(self) -> dict:
        synth = self.lab / "prova-seletor"
        synth.mkdir(exist_ok=True)
        (synth / "planilha-sintetica.txt").write_text("sintetico\n", encoding="utf-8")
        self.guard()
        self.page("Lista")
        self.invoke("Nova Rotina")
        self.wait("Nome da rotina")
        self.fill("Nome da rotina", f"Abrir arquivo {self.seq}")
        self.invoke("Continuar")
        self.wait("O que abrir")
        time.sleep(2)

        def picker(*args: str) -> str:
            return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HERE / "open_dialog.ps1"), "-AppPid", str(self.pid), *args],
                                  capture_output=True, encoding="utf-8", errors="replace").stdout.strip()
        self.choose("O que abrir", "Outro")
        if picker("-Probe") != "DIALOG":
            raise Stop("the file picker did not open")
        cancelled = picker("-Cancel") == "CANCELLED"
        time.sleep(1)
        kept_empty = not self.has("Arquivo escolhido")
        self.choose("O que abrir", "Outro")
        if picker("-Folder", str(synth), "-File", "planilha-sintetica.txt") != "OPENED":
            raise Stop("could not use the file picker")
        self.wait("Arquivo escolhido", "planilha-sintetica.txt", timeout=20)
        self.shot("seletor-escolhido")
        self.invoke("Salvar e preparar")
        self.wait("Deu tudo certo!", "A rotina já pode executar pela Lista", timeout=90)
        self.invoke("Concluir")
        row = next(r for r in self.api.call("GET", "/api/v1/routines") if r["name"] == f"Abrir arquivo {self.seq}")
        return {"passed": cancelled and kept_empty and row["config"]["target"]["kind"] == "file", "cancel_kept_nothing": kept_empty, "kind": row["kind"]}

    def s_run(self) -> dict:
        apps_listed = self.api.call("GET", f"/api/v1/stations/{self.station}/apps")["apps"]
        calc = next(a for a in apps_listed if a["name"] == APP)
        rid = self.api.call("POST", "/api/v1/routines", {"name": f"Avulsa calc {self.seq}", "category": "windows", "version": {
            "kind": "app_open", "config": {"target": {"kind": "app", "app_id": calc["id"], "name": calc["name"]}, "isolated": True}}})["routine"]["id"]
        self.guard()
        before = calc_windows()
        e = self.api.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": self.station, "routine_id": rid})
        e = self.wait_execution(e["id"], ("finished",))
        left = self.close_new_calc(before)
        return {"passed": e["outcome"] == "verified" and not left, "outcome": e["outcome"], "opened": (e["context"].get("last") or {}).get("opened", {}).get("image")}

    def s_review(self) -> dict:
        name = f"Prova revisao {self.seq}"
        p = self.empty_process(name)
        calc = next(a for a in self.api.call("GET", f"/api/v1/stations/{self.station}/apps")["apps"] if a["name"] == APP)
        self.api.call("POST", "/api/v1/routines", {"name": f"Abrir calc rev {self.seq}", "category": "windows", "link": {"process_id": p["id"]},
                                                   "version": {"kind": "app_open", "config": {"target": {"kind": "app", "app_id": calc["id"], "name": calc["name"]}, "isolated": True}}})
        self.guard()
        self.page("Lista")
        self.invoke("Nova Rotina")
        self.wait("Nome da rotina")
        self.fill("Nome da rotina", f"Conferir {self.seq}")
        self.pick("Fazer follow-up", "ComboBox|", 1)
        self.choose("Etapa anterior", name)
        self.invoke("Continuar")
        self.wait("Responsável pela revisão", "Solicitar revisão")
        time.sleep(1)
        self.choose("Responsável pela revisão", self.api.call("GET", "/api/v1/me")["display"])
        self.invoke("Salvar")
        self.wait("Deu tudo certo!")
        self.invoke("Concluir")
        items = self.api.call("GET", f"/api/v1/processes/{p['id']}")["items"]
        before = calc_windows()
        unseen_before = self.api.call("GET", "/api/v1/notifications")["unseen"]
        e = self.api.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": self.station, "process_id": p["id"]})
        e = self.wait_execution(e["id"], ("waiting_review", "finished"))
        left = self.close_new_calc(before)
        if e["state"] != "waiting_review":
            raise Stop(f"did not pause: {e['outcome']}")
        unseen = self.api.call("GET", "/api/v1/notifications")["unseen"]
        self.wait(f"Notificações, {unseen} não", timeout=10)  # live: not the 30 s of the periodic read
        self.shot("sino")
        self.click(f"Notificações, {unseen} não {'vista' if unseen == 1 else 'vistas'}")  # menus open on the pointer, as with a person
        time.sleep(0.8)
        self.shot("sino-aberto")
        self.ui("-Do", "keys", "-Value", "{DOWN}{ENTER}")
        self.wait("Aprovado!", "Registro da execução", timeout=30)
        self.shot("pedido")
        self.wait_seen = self.api.call("GET", "/api/v1/notifications")["unseen"]
        still = self.api.call("GET", f"/api/v1/executions/{e['id']}")["state"]
        self.invoke("Aprovado!")
        e = self.wait_execution(e["id"], ("finished",))
        time.sleep(1)
        self.shot("aprovado")
        self.ui("-Do", "keys", "-Value", "{ESC}")
        q = next(x for x in self.api.call("GET", "/api/v1/reviews") if x["execution_id"] == e["id"])
        passed = ([i["kind"] for i in items] == ["app_open", "followup"] and unseen == unseen_before + 1 and self.wait_seen == unseen - 1
                  and still == "waiting_review" and e["outcome"] == "verified" and q["decided_by_name"] and not left)
        return {"passed": bool(passed), "unseen": [unseen_before, unseen, self.wait_seen], "paused_until_click": still, "outcome": e["outcome"], "decided_by": q["decided_by_name"]}

    def s_report(self) -> dict:
        name = f"Prova relatorio {self.seq}"
        p = self.empty_process(name)
        calc = next(a for a in self.api.call("GET", f"/api/v1/stations/{self.station}/apps")["apps"] if a["name"] == APP)
        self.api.call("POST", "/api/v1/routines", {"name": f"Abrir calc rel {self.seq}", "category": "windows", "link": {"process_id": p["id"]},
                                                   "version": {"kind": "app_open", "config": {"target": {"kind": "app", "app_id": calc["id"], "name": calc["name"]}, "isolated": True}}})
        self.guard()
        self.page("Lista")
        self.invoke("Nova Rotina")
        self.wait("Nome da rotina")
        self.fill("Nome da rotina", f"Gerar PDF {self.seq}")
        self.pick("Fazer follow-up", "ComboBox|", 1)
        self.choose("Etapa anterior", name)
        self.invoke("Continuar")
        self.wait("Gerar relatório", "Solicitar revisão")
        self.click("Gerar relatório", "Text")
        time.sleep(0.5)
        self.invoke("Salvar")
        self.wait("Deu tudo certo!")
        self.invoke("Concluir")
        before = calc_windows()
        e = self.api.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": self.station, "process_id": p["id"]})
        e = self.wait_execution(e["id"], ("finished",))
        left = self.close_new_calc(before)
        report = e["context"]["steps"]["2"]["report"]
        folder = apps.known_folder("FDD39AD0-238F-46AF-ADB4-6C85480369C7") / "RedRise" / "Relatorios"
        saved = folder / report["file"]
        raw = saved.read_bytes()
        self.page("Histórico")
        time.sleep(1)
        self.click(name, "")  # the row, as a person clicks it
        self.wait("Veja aqui!", report["file"], timeout=20)
        self.shot("relatorio-historico")
        explorer_before = {w["hwnd"] for w in verifiers.top_windows() if w["class"] == "CabinetWClass"}
        self.invoke("Veja aqui!")
        end = time.monotonic() + 15
        opened: list[int] = []
        while time.monotonic() < end and not opened:
            opened = [w["hwnd"] for w in verifiers.top_windows() if w["class"] == "CabinetWClass" and w["hwnd"] not in explorer_before]
            time.sleep(0.5)
        time.sleep(3)  # a window still opening ignores the request to close
        still = apps.close_windows(opened) if opened else []
        self.ui("-Do", "keys", "-Value", "{ESC}")
        outputs = self.lab / "outputs" / "relatorios"
        outputs.mkdir(parents=True, exist_ok=True)
        moved = outputs / saved.name
        saved.replace(moved)
        ok = (e["outcome"] == "verified" and raw.startswith(b"%PDF-") and len(raw) == report["bytes"] and report["pages"] >= 1 and b"/Logo Do" in raw
              and b"Relat\xf3rio de execu\xe7\xe3o" in raw and name.encode() in raw and bool(opened) and not left and not still)
        return {"passed": ok, "outcome": e["outcome"], "file": report["file"], "bytes": report["bytes"], "pages": report["pages"], "explorer_opened": bool(opened), "not_closed": len(left) + len(still)}

    def s_live(self) -> dict:
        self.page("Lista")
        self.wait("Mostrando", timeout=10)
        name = f"Rotina ao vivo {self.seq}"
        time.sleep(2)  # the store is already waiting for news
        count = next(line for line in self.texts() if "Todas" in line)  # before the change: reading the screen takes a moment
        start = time.monotonic()
        self.api.call("POST", "/api/v1/routines", {"name": name, "category": "windows", "version": {"kind": "app_open", "config": {
            "target": {"kind": "file", "path": r"C:\Exemplos\ao-vivo.txt", "name": "ao-vivo.txt"}, "isolated": True}}})
        end = time.monotonic() + 12
        seen = False
        while time.monotonic() < end and not seen:
            now = next((line for line in self.texts() if "Todas" in line), count)
            seen = now != count
            time.sleep(0.3)
        return {"passed": seen, "seconds": round(time.monotonic() - start, 1)}

    def s_step1(self) -> dict:
        name = f"Prova etapa 1 {self.seq}"
        calc = next(a for a in self.api.call("GET", f"/api/v1/stations/{self.station}/apps")["apps"] if a["name"] == APP)
        cfg = {"kind": "app_open", "config": {"target": {"kind": "app", "app_id": calc["id"], "name": calc["name"]}, "isolated": True}}
        p = self.empty_process(name)
        old = self.api.call("POST", "/api/v1/routines", {"name": f"Etapa antiga {self.seq}", "category": "windows", "version": cfg, "link": {"process_id": p["id"]}})["routine"]["id"]
        new = self.api.call("POST", "/api/v1/routines", {"name": f"Etapa nova {self.seq}", "category": "windows", "version": cfg})["routine"]["id"]
        self.guard()
        for old_q in self.api.call("GET", "/api/v1/step-changes"):  # what an earlier attempt of this proof left
            if old_q["status"] == "pending":
                self.api.call("POST", f"/api/v1/step-changes/{old_q['id']}/cancel")
        q = self.api.call("POST", f"/api/v1/processes/{p['id']}/step1", {"routine_id": new})
        unchanged = self.api.call("GET", f"/api/v1/processes/{p['id']}")["items"][0]["routine_id"] == old
        self.page("Ação")
        self.click(next(line.split("|")[1] for line in self.texts() if line.startswith("TabItem|Marcado para mim")), "TabItem")
        self.wait(f"Etapa nova {self.seq}", "Aprovar substituição", timeout=15)
        self.shot("substituicao")
        self.invoke("Aprovar substituição")
        end = time.monotonic() + 20
        while time.monotonic() < end and self.api.call("GET", f"/api/v1/processes/{p['id']}")["items"][0]["routine_id"] != new:
            time.sleep(1)
        applied = self.api.call("GET", f"/api/v1/processes/{p['id']}")["items"][0]["routine_id"] == new
        return {"passed": unchanged and applied, "request": q["status"], "unchanged_before_approval": unchanged, "applied": applied}


SCENARIOS = ("migration", "list", "start", "picker", "run", "review", "step1", "report", "live")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lab", type=Path, required=True)
    ap.add_argument("--shots", type=Path, required=True)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    args.shots.mkdir(parents=True, exist_ok=True)
    wanted = [s for s in SCENARIOS if not args.only or s in args.only.split(",")]
    lab = Lab(args.lab, args.shots)
    report: dict = {"schema": "redrise.proof/1", "kind": "practical_e2e", "scenarios": {}, "install": str(ROOT.name)}
    started = time.time()
    try:
        lab.guard()
        lab.start_app()
        for s in wanted:
            print("scenario", s, flush=True)
            try:
                report["scenarios"][s] = getattr(lab, f"s_{s}")()
            except Stop as e:
                report["scenarios"][s] = {"passed": False, "stopped": str(e)[:1500]}
                lab.shot(f"falha-{s}")
                try:
                    lab.ui("-Do", "keys", "-Value", "{ESC}")
                except Stop:
                    pass
                if "computer in use" in str(e):
                    break
            print("  ->", json.dumps(report["scenarios"][s], ensure_ascii=False)[:400], flush=True)
    finally:
        lab.close_app()
    report["clicks_lost"] = lab.clicks_lost
    report["seconds"] = int(time.time() - started)
    report["passed"] = bool(report["scenarios"]) and all(v.get("passed") for v in report["scenarios"].values()) and len(report["scenarios"]) == len(wanted)
    out = args.lab / f"accept-inc-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out))
    print("PASSED" if report["passed"] else "FAILED")


if __name__ == "__main__":
    main()
