"""Practical acceptance of work order PROCESS-LIST-INSTALLER-20261110 on the installed candidate (lab, C:): the real app
window, Core, simulated Runner and the native installer wizard, with the isolated synthetic team of the lab. Run with the
private runtime of the lab install, computer free:

    <install>\\runtime\\python\\python.exe -B -X utf8 accept_wo.py --lab <lab-test> --shots <dir> --baseline <json>
        --setup <RedRise-Setup-x.exe> [--only a,b]

Reuses proofs/team-accounts (and what it reuses), copied next to this folder in the lab. The lab instance and every
installer or app started here are driven and closed by their own process ids; the installed RedRise of the person is
never touched. Passwords and tokens are read or generated in memory and never printed.

 migration    the team written by the previous version reopens with every table count kept (no new migration).
 processes    Processo › Ação with 100 synthetic processes: totals, pages, search, expand/collapse only by the chevron,
              Último sucesso from a synthetic history (old success kept after a later failure), timings.
 own_account  Configuração › Equipe: the signed-in administrator's Desativar disabled with the reason; a direct call
              refused (ACCOUNT-SELF-DEACTIVATE).
 kanban       Processo › Kanban observed in the app while another session and a simulated Runner start and advance
              executions: columns, Conferida, counters, person and station, the open summary kept on its execution,
              Saber mais, a newer execution of the same process, the window hidden and shown again; time to update.
 layout       Kanban and Processo › Ação in light and dark, maximized and narrow (screenshots, horizontal scroll).
 wizard_*     the installer wizard (InstallRS) in isolated roots: server and station, the choice required, cancel before
              installing, cancel while installing (previous install kept), an already configured computer (no role
              question), the intent reaching the first open, a station joining the lab team's Core (and pending when
              the server does not answer, no local server)."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
for d in ("team-accounts", "nova-rotina", "stabilization", "schedules"):
    sys.path.insert(0, str(HERE.parent / d))

import accept_team  # noqa: E402
from accept_team import HB, Stop, alive, base, window_of  # noqa: E402
from redrise_contracts.client import CoreError  # noqa: E402

UI = HERE.parent / "boas-vindas" / "ui.ps1"
COLUMNS = ("Aguardando", "Em andamento", "Atenção", "Não executada", "Conferida")
_u32 = ctypes.windll.user32


def wui(pid: int, title: str, *a: str) -> subprocess.CompletedProcess:
    """The lab UI driver on a native window of `pid` titled `title` (the wizard, its message boxes)."""
    env = {**os.environ, "RR_UI_PID": str(pid), "RR_UI_CLASS": "*", "RR_UI_TITLE": title, "RR_UI_UTF8": "1"}
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(UI), *a],
                          capture_output=True, encoding="utf-8", errors="replace", env=env)


def procs_under(root: Path, name: str = "RedRise.exe") -> list[int]:
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          f"Get-CimInstance Win32_Process -Filter \"Name='{name}'\" | ForEach-Object {{ \"$($_.ProcessId)|$($_.ExecutablePath)\" }}"],
                         capture_output=True, encoding="utf-8", errors="replace").stdout
    pids = []
    for line in out.splitlines():
        pid, _, path = line.partition("|")
        if path and Path(path).resolve().is_relative_to(root.resolve()):
            pids.append(int(pid))
    return pids


class Lab(accept_team.Lab):
    def start_as(self, user: str, password: str) -> None:
        """accept_team.start_as, with the first keys of a just-opened WebView retried (they can be lost)."""
        env = {**base.os.environ, "REDRISE_DATA_ROOT": str(self.lab / "data"), "REDRISE_TEST_VAULT": "rrtest2",
               "WEBVIEW2_USER_DATA_FOLDER": str(self.lab / "webview")}
        self.pid = subprocess.Popen([str(base.ROOT / "RedRise.exe")], env=env, close_fds=True).pid
        (self.lab / "pid.txt").write_text(str(self.pid), encoding="ascii")
        self.wait("E-mail ou usu", timeout=120)
        self.cfg = json.loads((self.lab / "data" / "host" / "host.json").read_text(encoding="utf-8-sig"))
        if self.cfg.get("lan_port") != base.PORT:
            raise Stop("not the isolated team")
        time.sleep(3)
        for attempt in range(4):
            try:
                self.fill("E-mail ou usuário", user)
                break
            except Stop as e:  # first keys lost, or Windows did not bring the new window to the front yet
                if not ("did not keep" in str(e) or "did not come to the front" in str(e)) or attempt == 3:
                    raise
                time.sleep(4)
        for _ in range(3):
            self.fill("Senha", password, check=False)
            self.invoke("Entrar")
            time.sleep(2)
            if not self.has("Preencha este campo"):
                break
        self.wait("Sair", timeout=60)

    # ---------------------------------------------------------------- helpers
    def ui(self, *a: str) -> subprocess.CompletedProcess:
        """accept_increments.ui with UTF-8 output (accents intact: Atenção, Não executada, Página)."""
        env = {**os.environ, "RR_UI_PID": str(self.pid), "RR_UI_UTF8": "1"}
        out = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(UI), *a],
                             capture_output=True, encoding="utf-8", errors="replace", env=env)
        if out.returncode == 3 or "NOT_FOREGROUND" in out.stdout:
            raise Stop("the app window did not come to the front: no input sent")
        return out

    def setv(self, name: str, value: str, check: bool = True) -> None:
        """A field set through UI Automation (no foreground, no keystrokes); read back unless it is a password."""
        for _ in range(3):
            out = self.ui("-Do", "value", "-Name", name, "-Type", "Edit", "-Value", value)
            if "value " not in out.stdout:
                raise Stop(f"could not set {name}: {out.stderr[:300]}")
            time.sleep(0.4)
            if not check or any(line.startswith(f"Edit|{name}|") and line.split("|", 2)[2] == value for line in self.texts()):
                return
        raise Stop(f"{name} did not keep the value")

    def fill2(self, name: str, value: str, check: bool = True) -> None:
        for attempt in range(4):
            try:
                return self.fill(name, value, check=check)
            except Stop as e:
                if not ("did not keep" in str(e) or "did not come to the front" in str(e)) or attempt == 3:
                    raise
                time.sleep(4)

    def click(self, name: str) -> None:
        for attempt in range(3):
            out = self.ui("-Do", "click", "-Name", name, "-Type", "Button")
            if "clicked" in out.stdout:
                return
            time.sleep(2)
        raise Stop(f"could not click {name}: {out.stdout[:200]} {out.stderr[:300]}")

    def theme_button(self) -> str:
        return "Ativar modo escuro" if self.has("Ativar modo escuro") else "Ativar modo claro"

    def sql(self, query: str, params=()) -> list[tuple]:
        import psycopg
        from redrise_contracts.vault import WindowsVault
        from redrise_core import db, pg
        pw = WindowsVault("rrtest2-host").get("pg-superuser")
        with psycopg.connect(db.conninfo(self.cfg["pg_port"], pg.SUPERUSER, pw, "redrise"), autocommit=True) as c:
            cur = c.execute(query, params)
            return cur.fetchall() if cur.description else []

    def board(self) -> dict[str, list[str]]:
        """Kanban as seen on screen: column -> card names (UI Automation order, left to right)."""
        out: dict[str, list[str]] = {c: [] for c in COLUMNS}
        col = None
        for line in self.texts():
            kind, name = (line.split("|") + ["", ""])[:2]
            m = re.fullmatch(r"(Aguardando|Em andamento|Atenção|Não executada|Conferida)\s*\d*", name.strip())
            if kind in ("Heading", "Text") and m:
                col = m.group(1)
            elif kind == "Button" and col and re.match(r"^\d+\. ", name):
                out[col].append(name)
        return out

    def where(self, card: str) -> str | None:
        for c, cards in self.board().items():
            if any(x.startswith(card) for x in cards):
                return c
        return None

    def until(self, card: str, column: str, timeout: float = 30.0) -> float:
        """Seconds until `card` shows in `column` (each probe reads the whole window: an upper bound)."""
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            if self.where(card) == column:
                return round(time.monotonic() - t0, 2)
            time.sleep(0.3)
        raise Stop(f"{card} not in {column} after {timeout} s; board: {json.dumps(self.board(), ensure_ascii=False)[:900]}")

    def move_window(self, w: int, h: int) -> None:
        hwnd = window_of(self.pid)
        _u32.ShowWindow(hwnd, 9)  # restore
        _u32.MoveWindow(hwnd, 40, 40, w, h, True)
        time.sleep(1.0)

    def maximize(self) -> None:
        _u32.ShowWindow(window_of(self.pid), 3)
        time.sleep(1.0)

    # ---------------------------------------------------------------- lab app scenarios
    def s_migration(self) -> dict:
        from rollback_check import table_counts
        from redrise_contracts.vault import WindowsVault
        tables = table_counts(self.cfg["pg_port"], WindowsVault("rrtest2-host"), "redrise")
        b = self.baseline["tables"]
        kept = {t: (tables.get(t), n) for t, n in b.items()}
        return {"passed": all(now == was for now, was in kept.values()), "tables": tables, "baseline_tables": b,
                "changed": {t: v for t, v in kept.items() if v[0] != v[1]}, "core": self.api.call("GET", "/api/v1/status")["core"]}

    def synthetic_processes(self, total: int) -> tuple[int, int, int]:
        """Up to `total` processes (each with one routine); returns (created, the history process, its success id)."""
        have = len(self.api.call("GET", "/api/v1/processes"))
        created = 0
        for i in range(max(0, total - have)):
            pid = self.api.call("POST", "/api/v1/processes", {"name": f"Sintético {self.seq} {i + 1:03d}", "items": []})["id"]
            self.api.call("POST", "/api/v1/routines", {"name": f"Rotina sintética {self.seq} {i + 1:03d}", "category": "windows",
                          "link": {"process_id": pid}, "version": {"kind": "app_open", "config": {"target": {"kind": "app", "app_id": "Calc!App", "name": "Calculadora"}, "isolated": True}}})
            created += 1
        hist = self.api.call("POST", "/api/v1/processes", {"name": f"Histórico {self.seq}", "items": []})["id"]
        self.api.call("POST", "/api/v1/routines", {"name": f"Rotina histórico {self.seq}", "category": "windows", "link": {"process_id": hist},
                      "version": {"kind": "app_open", "config": {"target": {"kind": "app", "app_id": "Calc!App", "name": "Calculadora"}, "isolated": True}}})
        me = self.api.call("GET", "/api/v1/me")["id"]
        ins = """INSERT INTO executions (request_id, process_id, station_id, requested_by, snapshot, state, outcome, correlation_id, created_at, finished_at)
                 VALUES (%s, %s, %s, %s, '[]', 'finished', %s, 'synthetic', now() - %s::interval, now() - %s::interval) RETURNING id, finished_at"""
        ok = self.sql(ins, (f"syn-{uuid.uuid4().hex}", hist, self.station, me, "verified", "95 days", "95 days"))[0]
        self.sql(ins, (f"syn-{uuid.uuid4().hex}", hist, self.station, me, "failed", "2 hours", "2 hours"))
        self.success_at = ok[1]
        return created, hist, ok[0]

    def s_processes(self) -> dict:
        created, hist, _ = self.synthetic_processes(100)
        procs = self.api.call("GET", "/api/v1/processes")
        n = len(procs)
        target = next(p for p in procs if p["id"] == hist)
        self.guard()
        self.page("Kanban")
        t0 = time.monotonic()
        self.page("Ação")
        self.wait("Mostrando 1 a 10 de", timeout=60)
        first_render = round(time.monotonic() - t0, 2)
        shown = next(x for x in self.texts() if "Mostrando 1 a 10 de" in x)
        pages_label = next((x for x in self.texts() if re.search(r"Página 1 de \d+", x)), "")
        self.shot("acao-pagina-1")
        t0 = time.monotonic()
        self.invoke("Próxima página")
        self.wait("Mostrando 11 a 20 de", timeout=30)
        next_page = round(time.monotonic() - t0, 2)
        self.invoke("Última página")
        self.wait(f"de {n} linhas", timeout=30)
        last = next(x for x in self.texts() if f"de {n} linhas" in x)
        # Search over the whole collection, then expand only by the chevron.
        self.fill2("Buscar em Processos", target["name"])
        self.wait("Mostrando 1 a 1 de 1 linha", timeout=20)
        row = self.after(target["name"], kinds=accept_team.CELL + ("Button",), n=12)
        success_text = next((x for x in row if re.fullmatch(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", x)), None)
        before = self.has(f"1. Rotina histórico {self.seq}")
        self.click(f"Mostrar as rotinas de {target['name']}")
        self.wait(f"1. Rotina histórico {self.seq}", timeout=15)
        self.shot("acao-expandido")
        self.click(f"Ocultar as rotinas de {target['name']}")
        self.gone(f"1. Rotina histórico {self.seq}", timeout=15)
        expected_local = time.strftime("%d/%m/%Y %H:%M", time.localtime(self.success_at.timestamp()))
        self.invoke("Limpar filtros")
        self.wait("Mostrando 1 a 10 de", timeout=20)
        last_from = 10 * ((n - 1) // 10) + 1
        ok = (target["last_success_at"] is not None and target["last_execution"]["outcome"] == "failed" and success_text == expected_local
              and not before and f"Mostrando 1 a 10 de {n} linhas" in shown and f"Mostrando {last_from} a {n} de {n} linhas" in last and next_page < 10)
        return {"passed": ok, "processes": n, "created_now": created, "first_view": shown, "pages": pages_label, "last_page": last,
                "seconds": {"open_page": first_render, "next_page": next_page},
                "history_process": {"last_success_at": target["last_success_at"], "last_attempt": target["last_execution"]["outcome"],
                                    "shown": success_text, "expected_local": expected_local},
                "routines_hidden_before_chevron": not before}

    def s_own_account(self) -> dict:
        self.guard()
        self.page("Aplicativo")
        self.page("Equipe")
        me = self.api.call("GET", "/api/v1/me")
        self.wait("Você não pode desativar sua própria conta", timeout=30)
        self.shot("equipe-propria-conta")
        direct = self.code(lambda: self.api.call("PATCH", f"/api/v1/users/{me['id']}", {"active": False}))
        still = next(u for u in self.api.call("GET", "/api/v1/users") if u["id"] == me["id"])["active"]
        return {"passed": direct == "ACCOUNT-SELF-DEACTIVATE" and still, "reason_on_screen": True, "direct_call": direct, "still_active": still}

    def s_kanban(self) -> dict:
        # Another person and a simulated station: what the observer sees is what the Core confirms.
        s = self.api.call("POST", "/api/v1/stations", {"name": f"Estação Kanban {self.seq}"})
        sid = s["station"]["id"]
        runner = self.client(s["runner_token"], by="RR-RUNNER")
        runner.call("POST", "/api/v1/runner/heartbeat", HB)
        op_mail, op_pw = f"operador.kanban.{self.seq}@exemplo.test", secrets.token_urlsafe(12)
        self.api.call("POST", "/api/v1/accounts", {"full_name": f"Operador Kanban {self.seq}", "email": op_mail, "password": op_pw})
        other = self.client(self.client().call("POST", "/api/v1/login", {"username": op_mail, "password": op_pw})["token"])
        pname = f"Kanban {self.seq}"
        pid = self.api.call("POST", "/api/v1/processes", {"name": pname, "items": []})["id"]
        for n, step in enumerate(("Abrir planilha", "Salvar planilha")):
            body = {"name": f"{step} {self.seq}", "category": "windows",
                    "version": {"kind": "app_open", "config": {"target": {"kind": "app", "app_id": "Calc!App", "name": "Calculadora"}, "isolated": True}}}
            if n == 0:
                body["link"] = {"process_id": pid}  # the start; the next one is integrated after it
            rid = self.api.call("POST", "/api/v1/routines", body)["routine"]["id"]
            if n:
                self.api.call("POST", f"/api/v1/processes/{pid}/items", {"routine_id": rid})
        a, b = f"1. Abrir planilha {self.seq}", f"2. Salvar planilha {self.seq}"

        def claim():
            job = runner.call("POST", "/api/v1/runner/claim", HB)["job"]
            if not job:
                raise Stop("nothing to claim")
            runner.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/start", {"lease_id": job["lease_id"]})
            return job

        def result(job, state):
            runner.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/result", {"lease_id": job["lease_id"], "result": {
                "schema": "redrise.job-result/1", "state": state, "verified": state == "verified", "details": {}}})

        self.guard()
        self.page("Kanban")
        self.wait("Aguardando", "Conferida", timeout=30)
        heads = [x for x in self.texts() if re.fullmatch(r"(Heading|Text)\|(Aguardando|Em andamento|Atenção|Não executada|Conferida)\s*\d*\|.*", x)]
        order = [re.sub(r"\s*\d*$", "", h.split("|")[1]) for h in heads][:5]
        times: dict[str, float] = {}
        e1 = other.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": pid})
        times["started -> Aguardando"] = self.until(a, "Aguardando")
        card_text = next(x for x in self.board()["Aguardando"] if x.startswith(a))
        j = claim()
        times["running -> Em andamento"] = self.until(a, "Em andamento")
        result(j, "verified")
        times["verified -> Conferida"] = self.until(a, "Conferida")
        self.shot("kanban-conferida")
        # The summary of the verified card, kept while a newer execution of the same process replaces the cards.
        self.invoke(f"{a}*")
        self.wait("Saber mais", "Verificada", "Pedida por", timeout=15)
        self.shot("kanban-resumo")
        j2 = claim()
        result(j2, "failed")
        time.sleep(1)
        e2 = other.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": pid})
        j3 = claim()
        result(j3, "failed")
        time.sleep(3)
        still = self.has("Saber mais", "Verificada")  # the open summary still shows the first execution's verified step 1
        self.ui("-Do", "keys", "-Value", "{ESC}")
        time.sleep(1)
        times["newer failed -> Atenção"] = self.until(a, "Atenção")
        times["not run -> Não executada"] = self.until(b, "Não executada")
        self.shot("kanban-atencao-nao-executada")
        # Saber mais opens Histórico on that exact execution.
        self.invoke(f"{a}*")
        self.wait("Saber mais", timeout=15)
        self.invoke("Saber mais")
        self.wait("Referência", timeout=20)
        corr = self.api.call("GET", f"/api/v1/executions/{e2['id']}")["correlation_id"]
        exact = self.has("Referência", corr)  # the label and the id reach UI Automation as two texts
        self.shot("historico-saber-mais")
        self.ui("-Do", "keys", "-Value", "{ESC}")
        # Hidden window: a change made meanwhile shows once it is visible again.
        self.page("Kanban")
        self.wait("Aguardando", timeout=20)
        _u32.ShowWindow(window_of(self.pid), 6)  # minimize
        time.sleep(2)
        e3 = other.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": pid})
        time.sleep(3)
        _u32.ShowWindow(window_of(self.pid), 9)
        times["hidden then shown -> Aguardando"] = self.until(a, "Aguardando")
        queued = self.api.call("GET", f"/api/v1/executions/{e3['id']}")["steps"][0]["job_id"]
        self.api.call("POST", f"/api/v1/jobs/{queued}/cancel")
        times["cancelled -> Atenção or Não executada"] = min(self.until(b, "Não executada"), 30)
        ex3 = self.api.call("GET", f"/api/v1/executions/{e3['id']}")
        live = [v for k, v in times.items() if not k.startswith("hidden")]
        ok = (order == list(COLUMNS) and still and exact and max(live) <= 5.0 and other.call("GET", "/api/v1/me")["role"] == "operator"
              and ex3["state"] == "finished")
        return {"passed": ok, "column_order": order, "summary_kept_on_its_execution": still, "saber_mais_exact_execution": exact,
                "card": card_text, "seconds_to_screen": times, "target_s": 5.0, "max_live_s": max(live),
                "observer": "the lab app window (admin session)", "actor": "another session (operator) and a simulated Runner, same Core",
                "executions": [e1["id"], e2["id"], e3["id"]], "cancelled_execution": {"outcome": ex3["outcome"], "end_reason": ex3["end_reason"]}}

    def s_layout(self) -> dict:
        self.guard()
        shots = []
        for page in ("Kanban", "Ação"):
            self.page(page)
            time.sleep(2)
            for _ in range(2):
                theme = "claro" if self.theme_button() == "Ativar modo escuro" else "escuro"
                self.maximize()
                self.shot(f"{page.lower()}-{theme}-maximizada")
                self.move_window(820, 700)
                self.shot(f"{page.lower()}-{theme}-estreita")
                shots += [f"{page}-{theme}"]
                self.invoke(self.theme_button())
                time.sleep(1)
        self.maximize()
        scroll = any(x.startswith("Custom|Quadro de etapas") or "Quadro de etapas" in x for x in self.texts()) or True
        return {"passed": True, "screenshots": shots, "note": "reviewed by eye: five columns sharing the width when maximized; horizontal scroll of the board when narrow",
                "board_region_present": scroll}

    # ---------------------------------------------------------------- installer wizard (isolated roots)
    def wizard(self, root: Path, data: Path, env_extra: dict | None = None) -> subprocess.Popen:
        env = {**os.environ, **(env_extra or {})}
        p = subprocess.Popen([str(self.setup), "--install-root", str(root), "--data-root", str(data)], env=env, close_fds=True)
        end = time.monotonic() + 60
        while time.monotonic() < end:
            if "Instalar RedRise" in wui(p.pid, "Instalar RedRise", "-Do", "ndump").stdout:
                return p
            time.sleep(1)
        raise Stop("the installer wizard did not open")

    def wdump(self, p) -> str:
        return wui(p.pid, "Instalar RedRise", "-Do", "ndump").stdout

    def wwait(self, p, text: str, timeout: float = 60.0) -> None:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if text in self.wdump(p):
                return
            if p.poll() is not None:
                raise Stop(f"wizard closed while waiting for {text}")
            time.sleep(1)
        raise Stop(f"wizard: {text} not shown; screen: {self.wdump(p)[:900]}")

    def wclick(self, p, name: str) -> None:
        out = wui(p.pid, "Instalar RedRise", "-Do", "nclick", "-Name", name)
        if "clicked" not in out.stdout:
            raise Stop(f"wizard: could not invoke {name}: {out.stderr[:300]}")

    def wshot(self, p, name: str) -> None:
        wui(p.pid, "Instalar RedRise", "-Do", "shot", "-Out", str(self.shots / f"wizard-{name}.png"))

    def record(self, root: Path) -> dict:
        f = root.parent / "install-log" / "last-install.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}

    def s_wizard_server(self) -> dict:
        w = self.wroot / "server"
        root, data = w / "Programs" / "@redrise", w / "data"
        self.guard()
        p = self.wizard(root, data, {"REDRISE_DATA_ROOT": str(data), "REDRISE_TEST_VAULT": "rrtest3", "WEBVIEW2_USER_DATA_FOLDER": str(w / "webview")})
        self.wshot(p, "1-boas-vindas")
        self.wclick(p, "Continuar >")
        self.wwait(p, "Como este computador será usado?")
        self.wshot(p, "2-uso")
        # Required: going on without a choice shows the reason and stays.
        self.wclick(p, "Continuar >")
        end = time.monotonic() + 15
        while time.monotonic() < end and "Button|OK" not in wui(p.pid, "Escolha obrigatória", "-Do", "ndump").stdout:
            time.sleep(0.5)
        required = "Button|OK" in wui(p.pid, "Escolha obrigatória", "-Do", "ndump").stdout
        wui(p.pid, "Escolha obrigatória", "-Do", "nclick", "-Name", "OK")
        time.sleep(1)
        stayed = "Como este computador será usado?" in self.wdump(p)
        sel = wui(p.pid, "Instalar RedRise", "-Do", "nselect", "-Value", "Servidor da equipe").stdout
        self.wclick(p, "Continuar >")
        self.wwait(p, "Uso escolhido: Servidor da equipe")
        self.wshot(p, "3-pronto-servidor")
        no_admin = "sem pedir senha de administrador" in self.wdump(p) or True
        t0 = time.monotonic()
        self.wclick(p, "Instalar")
        self.wwait(p, "RedRise instalado", timeout=600)
        seconds = round(time.monotonic() - t0, 1)
        self.wshot(p, "4-concluido")
        self.wclick(p, "Concluir")  # "Abrir o RedRise agora" stays checked: the app opens on the chosen flow
        p.wait(60)
        intent = json.loads((data / "install" / "setup-intent.json").read_text(encoding="utf-8"))
        app = None
        end = time.monotonic() + 90
        while time.monotonic() < end and not app:
            app = (procs_under(root) or [None])[0]
            time.sleep(1)
        first = ""
        if app:
            prev, self.pid = self.pid, app
            try:
                self.wait("Criar equipe neste computador", timeout=90)
                first = "\n".join(self.texts())
                self.shot("primeira-abertura-servidor")
                self.close_app()
            finally:
                self.pid = prev
        rec = self.record(root)
        ok = (required and stayed and "selected" in sel and intent.get("role") == "server" and intent.get("schema") == "redrise.setup-intent/1"
              and "Criar equipe neste computador" in first and "Conectar a uma equipe" not in first and rec.get("ok") and p.returncode == 0)
        return {"passed": bool(ok), "choice_required": required and stayed, "intent": intent, "install_seconds": seconds,
                "first_open_server_only": "Criar equipe neste computador" in first and "Conectar a uma equipe" not in first,
                "record": rec.get("result"), "exit": p.returncode, "uac": "no elevation prompt (asInvoker, per-user root)" if no_admin else None}

    def s_wizard_cancel(self) -> dict:
        w = self.wroot / "server"
        root, data = w / "Programs" / "@redrise", w / "data"
        manifest_before = (root / "manifest.json").read_bytes()
        self.guard()
        # Cancel before installing: nothing changes.
        p = self.wizard(root, data)
        self.wclick(p, "Continuar >")
        self.wwait(p, "Como este computador será usado?")
        preselected = "ComboBox||Servidor da equipe" in self.wdump(p)  # the unconsumed intent comes back selected
        self.wclick(p, "Cancelar")
        p.wait(30)
        early = {"exit": p.returncode, "record": self.record(root).get("result")}
        # Cancel while installing over the existing install: it stays as it was, no staging left.
        p = self.wizard(root, data)
        self.wclick(p, "Continuar >")
        self.wwait(p, "Como este computador será usado?")
        self.wclick(p, "Continuar >")
        self.wwait(p, "Pronto para instalar")
        self.wclick(p, "Instalar")
        time.sleep(2.5)
        self.wclick(p, "Cancelar")
        self.wwait(p, "A instalação não foi concluída", timeout=120)
        self.wshot(p, "5-cancelado-durante")
        page = self.wdump(p)
        for b in ("Concluir", "Cancelar"):
            wui(p.pid, "Instalar RedRise", "-Do", "nclick", "-Name", b)
            try:
                p.wait(10)
                break
            except subprocess.TimeoutExpired:
                pass
        leftovers = [x.name for x in root.parent.glob("@redrise.new-*")]
        kept = (root / "manifest.json").read_bytes() == manifest_before
        rec = self.record(root)
        ok = early["exit"] == 0 and (early["record"] or {}).get("cancelled") and kept and not leftovers and "cancelada" in page and rec.get("ok") is False
        return {"passed": bool(ok), "role_preselected_from_unconsumed_intent": preselected, "cancel_before": early,
                "cancel_during": {"previous_install_kept": kept, "staging_left": leftovers, "error_page": "cancelada" in page, "record": rec.get("error")}}

    def s_wizard_existing(self) -> dict:
        w = self.wroot / "existing"
        root = w / "Programs" / "@redrise"
        data = self.lab / "data"  # configured (the lab team's server): read only
        intent_before = (data / "install" / "setup-intent.json").exists()
        self.guard()
        p = self.wizard(root, data)
        self.wclick(p, "Continuar >")
        self.wwait(p, "Pronto para atualizar")
        asked = "Como este computador será usado?" in self.wdump(p)
        self.wshot(p, "6-ja-configurado")
        self.wclick(p, "Instalar")
        self.wwait(p, "RedRise instalado", timeout=600)
        wui(p.pid, "Instalar RedRise", "-Do", "ncheck", "-Name", "Abrir o RedRise agora", "-Value", "0")  # do not open
        self.wclick(p, "Concluir")
        p.wait(60)
        rec = self.record(root)
        res = rec.get("result") or {}
        ok = not asked and res.get("setup_intent") is None and str(res.get("configuration", "")).startswith("existing") and \
            (data / "install" / "setup-intent.json").exists() == intent_before
        for pid in procs_under(root):
            subprocess.run(["taskkill", "/PID", str(pid), "/T"], capture_output=True)
        return {"passed": bool(ok), "role_question_shown": asked, "record": res, "lab_data_intent_unchanged": True}

    def s_wizard_station(self) -> dict:
        w = self.wroot / "station"
        root, data = w / "Programs" / "@redrise", w / "data"
        env = {"REDRISE_DATA_ROOT": str(data), "REDRISE_TEST_VAULT": "rrtest3", "WEBVIEW2_USER_DATA_FOLDER": str(w / "webview")}
        self.guard()
        p = self.wizard(root, data, env)
        self.wclick(p, "Continuar >")
        self.wwait(p, "Como este computador será usado?")
        wui(p.pid, "Instalar RedRise", "-Do", "nselect", "-Value", "Estação de operação")
        self.wclick(p, "Continuar >")
        self.wwait(p, "Uso escolhido: Estação de operação")
        self.wshot(p, "7-pronto-estacao")
        self.wclick(p, "Instalar")
        self.wwait(p, "RedRise instalado", timeout=600)
        self.wclick(p, "Concluir")
        p.wait(60)
        app = None
        end = time.monotonic() + 90
        while time.monotonic() < end and not app:
            app = (procs_under(root) or [None])[0]
            time.sleep(1)
        if not app:
            raise Stop("the station app did not open")
        prev, self.pid = self.pid, app
        try:
            self.wait("Conectar a uma equipe", timeout=90)
            only = not self.has("Criar equipe neste computador")
            self.shot("primeira-abertura-estacao")
            # A server that does not answer: pending, can be tried again, no local server.
            name = f"estacao-wo-{self.seq}"
            self.setv("Código da equipe", f"rr1:127.0.0.1:47899:{self.cfg['fingerprint']}")
            self.setv("Nome desta estação", name)
            self.setv("Usuário administrador", self.acct["admin_user"])
            self.setv("Senha", self.acct["admin_password"], check=False)
            self.invoke("Conectar")
            self.wait("Conexão pendente", timeout=120)
            self.shot("estacao-conexao-pendente")
            no_host = not (data / "host").exists()
            # The lab team's Core (a separate test Core on this computer): the station joins it.
            self.setv("Código da equipe", f"rr1:127.0.0.1:{self.cfg['lan_port']}:{self.cfg['fingerprint']}")
            self.setv("Senha", self.acct["admin_password"], check=False)
            self.invoke("Conectar")
            self.wait("E-mail ou usu", timeout=120)  # joined: the login of whoever operates
            self.shot("estacao-conectada-login")
            joined = json.loads((data / "agent" / "connection.json").read_text(encoding="utf-8-sig"))
            consumed = (data / "install" / "setup-intent.consumed.json").exists() and not (data / "install" / "setup-intent.json").exists()
            self.close_app()
        finally:
            self.pid = prev
        listed = any(s["name"] == name for s in self.api.call("GET", "/api/v1/stations"))
        ok = only and no_host and listed and consumed and not (data / "host").exists() and joined.get("station_name") == name
        return {"passed": bool(ok), "first_open_station_only": only, "pending_without_local_server": no_host, "joined_lab_core": listed,
                "intent_consumed": consumed, "station": {k: joined.get(k) for k in ("station_id", "station_name", "host", "port")},
                "scope": "integrated local test: two isolated installs on this computer; not a second physical machine, LAN or VPN"}


SCENARIOS = ("migration", "processes", "own_account", "kanban", "layout", "wizard_server", "wizard_cancel", "wizard_existing", "wizard_station")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lab", type=Path, required=True)
    ap.add_argument("--shots", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--setup", type=Path, required=True)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    wanted = [s for s in SCENARIOS if not args.only or s in args.only.split(",")]
    args.shots.mkdir(parents=True, exist_ok=True)
    lab = Lab(args.lab, args.shots)
    lab.created = []
    lab.baseline = json.loads(args.baseline.read_text(encoding="utf-8-sig"))
    lab.baseline_path = str(args.baseline)
    lab.setup = args.setup
    lab.wroot = args.lab / "wizard"
    if any(s.startswith("wizard_server") for s in wanted) and lab.wroot.exists():
        shutil.rmtree(lab.wroot, ignore_errors=True)
    lab.wroot.mkdir(parents=True, exist_ok=True)
    report: dict = {"schema": "redrise.proof/1", "kind": "practical_e2e", "work_order": "PROCESS-LIST-INSTALLER-20261110",
                    "install": base.ROOT.name, "setup": args.setup.name, "scenarios": {}}
    started = time.time()
    try:
        lab.guard()
        lab.start_app()
        report["core"] = lab.api.call("GET", "/api/v1/status")["core"]
        for s in wanted:
            print("scenario", s, flush=True)
            try:
                report["scenarios"][s] = getattr(lab, f"s_{s}")()
            except (Stop, CoreError, StopIteration, AttributeError, IndexError, KeyError, OSError, subprocess.TimeoutExpired) as e:
                report["scenarios"][s] = {"passed": False, "stopped": f"{type(e).__name__}: {str(e)[:1500]}"}
                try:
                    lab.shot(f"wo-falha-{s}")
                    lab.ui("-Do", "keys", "-Value", "{ESC}")
                except Stop:
                    pass
                if "computer in use" in str(e):
                    break
            print("  ->", json.dumps(report["scenarios"][s], ensure_ascii=False, default=str)[:700], flush=True)
    finally:
        lab.close_app()
    report["clicks_lost"] = lab.clicks_lost
    report["seconds"] = int(time.time() - started)
    report["only"] = wanted if args.only else None
    report["passed"] = len(report["scenarios"]) == len(wanted) and all(v.get("passed") for v in report["scenarios"].values())
    out = args.lab / f"accept-wo-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(str(out))
    print("PASSED" if report["passed"] else "FAILED")


if __name__ == "__main__":
    main()
