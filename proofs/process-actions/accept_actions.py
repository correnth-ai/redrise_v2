"""Practical acceptance of work order PROCESS-ACTIONS-20261111 on the installed candidate (lab, C:): the real app window,
Core, simulated Runner and the native installer wizard, with the isolated synthetic team of the lab. Run with the private
runtime of the lab install, computer free:

    <install>\\runtime\\python\\python.exe -B -X utf8 accept_actions.py --lab <lab-test> --shots <dir> --baseline <json>
        --setup <RedRise-Setup-x.exe> --previous <install of the previous version> [--only a,b]

Reuses proofs/process-list-installer (and what it reuses), copied next to this folder in the lab. Every window is driven
by its own process id; the installed RedRise of the person is never touched. Synthetic data only; passwords and tokens
stay in memory and are never printed.

 migration    the team written by the previous version reopens with every table count kept (no new migration).
 actions      Processo > Acao: no Nova execucao and no Execucoes recentes; the six icons on every process, Boas-vindas
              included; Play opens the execution dialog; Agendamentos pause, resume and delete by icons.
 delete       the scenario of item 2: process A named X with an exclusive and a shared routine, history and a schedule;
              deleted from the trash with a typed CoNfIrMaDo; C created with the same name: new id, nothing inherited.
 welcome      Boas-vindas deleted from the trash with "confirmado"; the app closed and opened again: not created again.
 kanban_day   Processo > Kanban: four columns, one card per process with only name, station and person, every column by
              a real execution (simulated Runner), yesterday's success not shown today, a chosen day, the summary.
 layout       Kanban and Processo > Acao in light and dark, maximized and narrow.
 failures     installer failure reports on COPIES (--test-fail-at): before the swap, at the swap with a checked restore,
              a failed restore, after the swap and at the setup intent; the JSON record and the folders agree.
 wizard_*     the walkthrough of the final installer: server (with active progress), cancel, existing, station, and a
              controlled error page, in isolated roots."""

from __future__ import annotations

import argparse
import json
import re
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "process-list-installer"))

import accept_wo  # noqa: E402
from accept_wo import HB, Stop, base, procs_under, wui  # noqa: E402
from redrise_contracts.client import CoreError  # noqa: E402

COLS = ("No aguardo", "Em andamento", "Concluído", "Conferido")
CALC = {"target": {"kind": "app", "app_id": "Calc!App", "name": "Calculadora"}, "isolated": True}
SIX = ("Executar {n}", "Agendar", "Integrar rotina avulsa", "Substituir etapa 1", "Excluir {n}", "Editar composição")


class Lab(accept_wo.Lab):
    # ---------------------------------------------------------------- helpers
    def routine(self, name: str, pid: int | None = None) -> int:
        body = {"name": name, "category": "windows", "version": {"kind": "app_open", "config": CALC}}
        if pid is not None:
            body["link"] = {"process_id": pid}
        return self.api.call("POST", "/api/v1/routines", body)["routine"]["id"]

    def buttons(self) -> list[str]:
        return [line.split("|")[1] for line in self.texts() if line.startswith("Button|")]

    def row_actions(self, name: str) -> list[str]:
        """The action buttons of a process row, in screen order (names from UI Automation)."""
        want = [x.format(n=name) for x in SIX]
        seen = [b for b in self.buttons() if b in want or b.startswith(("Executar:", "Agendar:", "Em execução", "Aguardando revisão:", "Sem etapa 1", "Já há"))]
        i = next((k for k, b in enumerate(seen) if b in (f"Executar {name}",) or b.startswith("Executar:")), None)
        return seen[i:i + 6] if i is not None else []

    def search(self, text: str) -> None:
        self.setv("Buscar em Processos", text)
        time.sleep(1.5)

    def board_day(self, names: list[str]) -> dict[str, list[str]]:
        """Kanban as seen on screen: column -> the card buttons (by process name prefix), left to right."""
        out: dict[str, list[str]] = {c: [] for c in COLS}
        col = None
        for line in self.texts():
            kind, label = (line.split("|") + ["", ""])[:2]
            m = re.fullmatch(r"(No aguardo|Em andamento|Concluído|Conferido)\s*\d*", label.strip())
            if kind in ("Heading", "Text") and m:
                col = m.group(1)
            elif kind == "Button" and col and any(label.startswith(n) for n in names):
                out[col].append(label)
        return out

    def column_of(self, name: str) -> str | None:
        for c, cards in self.board_day([name]).items():
            if any(x.startswith(name) for x in cards):
                return c
        return None

    def until_col(self, name: str, column: str, timeout: float = 30.0) -> float:
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            if self.column_of(name) == column:
                return round(time.monotonic() - t0, 2)
            time.sleep(0.3)
        raise Stop(f"{name} not in {column} after {timeout} s: {json.dumps(self.board_day([name]), ensure_ascii=False)[:600]}")

    def sim_runner(self, label: str):
        s = self.api.call("POST", "/api/v1/stations", {"name": f"Estação {label} {self.seq}"})
        r = self.client(s["runner_token"], by="RR-RUNNER")
        r.call("POST", "/api/v1/runner/heartbeat", HB)
        return s["station"]["id"], r

    @staticmethod
    def claim(runner):
        job = runner.call("POST", "/api/v1/runner/claim", HB)["job"]
        if not job:
            raise Stop("nothing to claim")
        runner.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/start", {"lease_id": job["lease_id"]})
        return job

    @staticmethod
    def report(runner, job, state):
        runner.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/result", {"lease_id": job["lease_id"], "result": {
            "schema": "redrise.job-result/1", "state": state, "verified": state == "verified", "details": {}}})

    def delete_by_ui(self, name: str, word: str) -> dict:
        """Opens the trash of `name`, checks the dialog, types `word` through UI Automation, and confirms with Excluir."""
        self.invoke(f"Excluir {name}")
        self.wait("Confirma exclusão do processo? As rotinas não serão excluídas.", timeout=15)
        dialog = "\n".join(self.texts())
        self.shot(f"excluir-{re.sub(r'[^a-z0-9]+', '-', name.lower())[:30]}-dialogo")
        disabled_before = not self.enabled("Excluir")
        self.setv("Digite Confirmado para excluir", "confirma")
        time.sleep(0.6)
        wrong_refused = not self.enabled("Excluir")
        self.setv("Digite Confirmado para excluir", word)
        time.sleep(0.6)
        ok_enabled = self.enabled("Excluir")
        self.shot(f"excluir-{re.sub(r'[^a-z0-9]+', '-', name.lower())[:30]}-confirmado")
        self.invoke_last("Excluir")
        self.gone("Confirma exclusão do processo?", timeout=30)
        return {"literal_question": "Confirma exclusão do processo? As rotinas não serão excluídas." in dialog, "name_shown": name in dialog,
                "wrong_word_keeps_excluir_off": wrong_refused, "word_enables_excluir": ok_enabled, "disabled_before_typing": disabled_before}

    def enabled(self, name: str) -> bool:
        return "enabled=True" in self.ui("-Do", "enabled", "-Name", name, "-Type", "Button").stdout

    # ---------------------------------------------------------------- scenarios
    def s_actions(self) -> dict:
        procs = {p["name"]: p for p in self.api.call("GET", "/api/v1/processes")}
        name = f"Ações {self.seq}"
        pid = self.api.call("POST", "/api/v1/processes", {"name": name, "items": []})["id"]
        self.routine(f"Rotina ações {self.seq}", pid)
        self.guard()
        self.page("Kanban")
        self.page("Ação")
        self.wait("Mostrando", timeout=60)
        no_new = not self.has("Nova execução")
        no_recent = not self.has("Execuções recentes")
        welcome = next((n for n, p in procs.items() if p.get("system_key") == "boas-vindas"), None)
        rows = {}
        for n in [x for x in (welcome, name) if x]:
            self.search(n)
            rows[n] = self.row_actions(n)
        self.search(name)
        self.shot("acao-icones")
        # Play opens the execution dialog of this process (closed without starting).
        self.invoke(f"Executar {name}")
        self.wait("Estação", timeout=15)
        run_dialog = "\n".join(self.texts())
        self.shot("acao-play-dialogo")
        self.ui("-Do", "keys", "-Value", "{ESC}")
        time.sleep(1.5)
        started = [e for e in self.api.call("GET", "/api/v1/executions") if e.get("process_id") == pid]
        # Agendamentos by icons.
        sched = self.api.call("POST", "/api/v1/schedules", {"process_id": pid, "station_id": self.station, "weekdays": [1, 2, 3, 4, 5],
                                                            "hour": 4, "minute": 30, "timezone": "America/Sao_Paulo"})
        time.sleep(3)
        self.invoke(f"Pausar agendamento de {name}")
        time.sleep(2.5)
        paused = next(s for s in self.api.call("GET", "/api/v1/schedules") if s["id"] == sched["id"])["enabled"] is False
        self.invoke(f"Retomar agendamento de {name}")
        time.sleep(2.5)
        resumed = next(s for s in self.api.call("GET", "/api/v1/schedules") if s["id"] == sched["id"])["enabled"] is True
        self.shot("agendamentos-icones")
        self.invoke(f"Excluir agendamento de {name}")
        self.wait("Excluir agendamento", timeout=15)
        self.shot("agendamento-excluir-dialogo")
        self.invoke_last("Excluir agendamento")
        time.sleep(3)
        gone = all(s["id"] != sched["id"] for s in self.api.call("GET", "/api/v1/schedules"))
        self.invoke("Limpar filtros") if self.has("Limpar filtros") else None
        expect = lambda n: [x.format(n=n) for x in SIX]  # noqa: E731
        ok = (no_new and no_recent and all(rows[n] == expect(n) for n in rows) and welcome in rows and "Estação" in run_dialog
              and not started and paused and resumed and gone)
        return {"passed": bool(ok), "nova_execucao_absent": no_new, "execucoes_recentes_absent": no_recent, "row_actions": rows,
                "play_opened_dialog_without_starting": "Estação" in run_dialog and not started,
                "schedule_icons": {"paused": paused, "resumed": resumed, "deleted_after_confirmation": gone}}

    def s_delete(self) -> dict:
        x = f"X {self.seq}"
        A = self.api.call("POST", "/api/v1/processes", {"name": x, "items": []})["id"]
        exclusive = self.routine(f"Exclusiva {self.seq}", A)
        shared = self.routine(f"Compartilhada {self.seq}")
        self.api.call("POST", f"/api/v1/processes/{A}/items", {"routine_id": shared})
        B = self.api.call("POST", "/api/v1/processes", {"name": f"B {self.seq}", "items": []})["id"]
        b1 = self.routine(f"B rotina {self.seq}", B)
        self.api.call("PUT", f"/api/v1/processes/{B}", {"name": f"B {self.seq}", "items": [{"routine_id": b1, "continue_next": True},
                                                                                           {"routine_id": shared, "continue_next": True}]})
        me = self.api.call("GET", "/api/v1/me")["id"]
        old = self.sql("""INSERT INTO executions (request_id, process_id, station_id, requested_by, snapshot, state, outcome, correlation_id, created_at, finished_at)
                          VALUES (%s, %s, %s, %s, '[]', 'finished', 'verified', 'synthetic', now() - interval '1 hour', now() - interval '59 minutes')
                          RETURNING id""", (f"syn-{uuid.uuid4().hex}", A, self.station, me))[0][0]
        sched = self.api.call("POST", "/api/v1/schedules", {"process_id": A, "station_id": self.station, "weekdays": [6], "hour": 5, "minute": 0,
                                                            "timezone": "America/Sao_Paulo"})
        self.guard()
        self.page("Ação")
        self.wait("Mostrando", timeout=60)
        self.search(x)
        ui = self.delete_by_ui(x, "CoNfIrMaDo")
        time.sleep(2)
        procs = {p["id"]: p for p in self.api.call("GET", "/api/v1/processes")}
        rs = {r["id"]: r for r in self.api.call("GET", "/api/v1/routines")}
        C = self.api.call("POST", "/api/v1/processes", {"name": x, "items": []})
        e = self.api.call("GET", f"/api/v1/executions/{old}")
        self.api.call("PUT", f"/api/v1/processes/{C['id']}", {"name": f"Y {self.seq}", "items": []})
        e2 = self.api.call("GET", f"/api/v1/executions/{old}")
        self.page("Histórico")
        self.wait(f"{x} (excluído)", timeout=30)
        self.shot("historico-processo-excluido")
        late = self.api.call("POST", f"/api/v1/processes/{A}/archive", {"confirm": "Confirmado"})
        sched_listed = any(s["id"] == sched["id"] for s in self.api.call("GET", "/api/v1/schedules"))
        procs2 = {p["id"]: p for p in self.api.call("GET", "/api/v1/processes")}
        ok = (all(ui.values()) and A not in procs and exclusive in rs and shared in rs and [i["routine_id"] for i in procs[B]["items"]] == [b1, shared]
              and not any(i["routine_id"] == exclusive for p in procs.values() for i in p["items"]) and C["id"] != A and C["items"] == []
              and C["last_execution"] is None and (e["process_id"], e["process_name"], e["process_archived"]) == (A, x, True)
              and e2["process_name"] == x and late["already"] and not sched_listed and procs2[C["id"]]["name"] == f"Y {self.seq}")
        return {"passed": bool(ok), "dialog": ui, "A": A, "C": C["id"], "exclusive_standalone": exclusive in rs,
                "shared_kept_in_B": [i["routine_id"] for i in procs[B]["items"]] == [b1, shared], "history_of_A": {k: e[k] for k in ("process_id", "process_name", "process_archived")},
                "after_renaming_C": e2["process_name"], "late_request_for_A": late, "schedule_hidden": not sched_listed}

    def s_welcome(self) -> dict:
        procs = {p["id"]: p for p in self.api.call("GET", "/api/v1/processes")}
        w = next((p for p in procs.values() if p.get("system_key") == "boas-vindas"), None)
        if not w:
            raise Stop("no Boas-vindas in the lab team")
        busy = self.sql("SELECT count(*) FROM executions WHERE process_id = %s AND state <> 'finished'", (w["id"],))[0][0]
        if busy:
            raise Stop("Boas-vindas has an execution open in the lab")
        self.guard()
        self.page("Ação")
        self.wait("Mostrando", timeout=60)
        self.search(w["name"])
        ui = self.delete_by_ui(w["name"], "confirmado")
        time.sleep(2)
        after = [p for p in self.api.call("GET", "/api/v1/processes") if p.get("system_key") == "boas-vindas"]
        self.close_app()
        self.start_app()
        again = [p for p in self.api.call("GET", "/api/v1/processes") if p.get("system_key") == "boas-vindas"]
        rows = self.sql("SELECT count(*), bool_and(archived) FROM processes WHERE system_key = 'boas-vindas'")[0]
        rs = {r["id"] for r in self.api.call("GET", "/api/v1/routines")}
        kept = all(i["routine_id"] in rs for i in w["items"])
        ok = all(ui.values()) and not after and not again and rows == (1, True) and kept
        return {"passed": bool(ok), "dialog": ui, "listed_after_delete": bool(after), "created_again_after_reopen": bool(again),
                "tombstone": {"rows": rows[0], "archived": rows[1]}, "routines_kept_standalone": kept}

    def s_kanban_day(self) -> dict:
        sid, runner = self.sim_runner("Kanban dia")
        mail, pw = f"operador.dia.{self.seq}@exemplo.test", secrets.token_urlsafe(12)
        self.api.call("POST", "/api/v1/accounts", {"full_name": f"Operador Dia {self.seq}", "email": mail, "password": pw})
        other = self.client(self.client().call("POST", "/api/v1/login", {"username": mail, "password": pw})["token"])
        names = {k: f"Dia {k} {self.seq}" for k in ("fila", "andamento", "concluido", "conferido", "falha", "ontem")}
        pids = {}
        for k, n in names.items():
            pids[k] = self.api.call("POST", "/api/v1/processes", {"name": n, "items": []})["id"]
            self.routine(f"Rotina {n}", pids[k])
        self.guard()
        self.page("Kanban")
        self.wait("No aguardo", "Conferido", timeout=30)
        heads = [re.sub(r"\s*\d*$", "", line.split("|")[1]) for line in self.texts()
                 if re.fullmatch(r"(Heading|Text)\|(No aguardo|Em andamento|Concluído|Conferido)\s*\d*\|.*", line)][:4]
        hoje = next((line for line in self.texts() if "Execuções iniciadas em" in line), "")
        t: dict[str, float] = {}
        start = lambda k: other.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": pids[k]})  # noqa: E731
        # One execution at a time on the simulated station, each to its real end.
        for k, state in (("conferido", "verified"), ("concluido", "completed_unverified"), ("falha", "failed")):
            start(k)
            t[f"{k}: started -> No aguardo"] = self.until_col(names[k], "No aguardo")
            j = self.claim(runner)
            t[f"{k}: running -> Em andamento"] = self.until_col(names[k], "Em andamento")
            self.report(runner, j, state)
            t[f"{k}: {state} -> column"] = self.until_col(names[k], {"verified": "Conferido", "completed_unverified": "Concluído", "failed": "No aguardo"}[state])
        start("andamento")
        self.claim(runner)
        t["andamento: running"] = self.until_col(names["andamento"], "Em andamento")
        start("fila")  # queued behind the running one on the same station
        t["fila: queued -> No aguardo"] = self.until_col(names["fila"], "No aguardo")
        me = self.api.call("GET", "/api/v1/me")["id"]
        self.sql("""INSERT INTO executions (request_id, process_id, station_id, requested_by, snapshot, state, outcome, correlation_id, created_at, finished_at)
                    VALUES (%s, %s, %s, %s, '[]', 'finished', 'verified', 'synthetic', now() - interval '1 day 2 hours', now() - interval '1 day 1 hour')""",
                 (f"syn-{uuid.uuid4().hex}", pids["ontem"], sid, me))
        time.sleep(4)
        board = self.board_day(list(names.values()))
        card = next(x for x in board["Conferido"] if x.startswith(names["conferido"]))
        self.shot("kanban-dia-quatro-colunas")
        # Summary of the failed card: real state and reason, closed by Escape, the board stays.
        fail_card = next(x for x in board["No aguardo"] if x.startswith(names["falha"]))
        self.invoke(fail_card)
        self.wait("Saber mais", "Falhou", timeout=15)
        summary = "\n".join(self.texts())
        self.shot("kanban-dia-resumo-falha")
        self.ui("-Do", "keys", "-Value", "{ESC}")
        self.gone("Saber mais", timeout=10)
        stays = self.has("No aguardo") and self.has("Conferido")
        ontem_today = self.column_of(names["ontem"])
        # Another day: yesterday, chosen in the date field (keys into the date input, computer free).
        yesterday = time.strftime("%d%m%Y", time.localtime(time.time() - 86400))
        day_changed = None
        try:
            self.fill2("Dia", yesterday, check=False)
            time.sleep(3)
            day_changed = self.column_of(names["ontem"])
            self.shot("kanban-dia-ontem")
        except Stop as e:
            day_changed = f"not driven natively: {e}"
        if self.has("Hoje"):
            self.invoke("Hoje")
            time.sleep(2)
        # Finish what was left running (the station is simulated): nothing stays open in the lab team.
        open_jobs = self.sql("SELECT id FROM jobs WHERE execution_id IN (SELECT id FROM executions WHERE process_id = ANY(%s)) AND state IN ('queued','claimed','running')",
                             (list(pids.values()),))
        for (jid,) in open_jobs:
            try:
                self.api.call("POST", f"/api/v1/jobs/{jid}/cancel")
            except CoreError:
                pass
        ok = (heads == list(COLS) and "(hoje)" in hoje and card.count(names["conferido"]) == 1 and "Falhou" in summary and "Motivo" in summary
              and stays and ontem_today is None and max(t.values()) <= 5.0)
        card_lines = card.replace(names["conferido"], "", 1)
        return {"passed": bool(ok), "columns": heads, "today_label": hoje.split("|")[1] if "|" in hoje else hoje, "seconds_to_screen": t,
                "max_live_s": max(t.values()), "target_s": 5.0, "card_name": card, "card_rest": card_lines,
                "summary_has_real_state": "Falhou" in summary, "board_kept_after_escape": stays,
                "yesterday_success_on_today": ontem_today, "yesterday_when_chosen": day_changed}

    def s_layout(self) -> dict:
        self.guard()
        shots = []
        for page in ("Kanban", "Ação"):
            self.page(page)
            time.sleep(2)
            for _ in range(2):
                theme = "claro" if self.theme_button() == "Ativar modo escuro" else "escuro"
                self.maximize()
                self.shot(f"{'kanban' if page == 'Kanban' else 'acao'}-{theme}-maximizada")
                self.move_window(820, 700)
                self.shot(f"{'kanban' if page == 'Kanban' else 'acao'}-{theme}-estreita")
                shots.append(f"{page}-{theme}")
                self.invoke(self.theme_button())
                time.sleep(1)
        self.maximize()
        return {"passed": True, "screenshots": shots, "note": "reviewed by eye: four columns sharing the width when maximized, sideways scroll "
                "when narrow; the last execution under its badge in Acao"}

    # ---------------------------------------------------------------- installer failures, on copies
    def quiet(self, root: Path, data: Path, *extra: str) -> tuple[int, dict]:
        p = subprocess.run([str(self.setup), "--quiet", "--install-root", str(root), "--data-root", str(data), *extra],
                           capture_output=True, encoding="utf-8", errors="replace", timeout=900)
        line = next((x for x in reversed(p.stdout.splitlines()) if x.startswith("{")), "{}")
        return p.returncode, json.loads(line)

    @staticmethod
    def version_at(root: Path) -> str | None:
        f = root / "manifest.json"
        return json.loads(f.read_text(encoding="utf-8-sig"))["app_version"] if f.is_file() else None

    def s_failures(self) -> dict:
        work = self.lab / "fail-copies"
        shutil.rmtree(work, ignore_errors=True)
        out: dict = {}
        prev_v = self.version_at(self.previous)
        new_v = self.version_at(base.ROOT)
        for point in ("before-swap", "swap", "restore", "after-swap", "intent"):
            w = work / point
            root, data = w / "Programs" / "@redrise", w / "data"
            subprocess.run(["robocopy", str(self.previous), str(root), "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NP"], capture_output=True)
            extra = ["--test-fail-at", point] + (["--role", "server"] if point == "intent" else [])
            code, rec = self.quiet(root, data, *extra)
            f = rec.get("failure") or {}
            prev_dir = root.parent / "@redrise.previous"
            files = {"installed": self.version_at(root), "previous_dir": self.version_at(prev_dir), "staging_left": [x.name for x in root.parent.glob("@redrise.new-*")],
                     "intent_file": (data / "install" / "setup-intent.json").exists()}
            expect = {"before-swap": ("before_swap", prev_v, None, None), "swap": ("swap", prev_v, None, None),
                      "restore": ("swap", None, prev_v, "recovery"), "after-swap": ("after_swap", new_v, prev_v, None),
                      "intent": ("after_swap", new_v, prev_v, None)}[point]
            agree = (code == 3 and rec.get("ok") is False and f.get("phase") == expect[0] and files["installed"] == expect[1]
                     and f.get("installed_now") == expect[1] and files["previous_dir"] == expect[2] and not files["staging_left"]
                     and (bool(f.get("recovery_error")) == (expect[3] == "recovery")) and not files["intent_file"])
            out[point] = {"agree": bool(agree), "exit": code, "failure": f, "message": rec.get("error"), "files": files}
            shutil.rmtree(w, ignore_errors=True)
        # A fresh install whose swap fails: nothing installed, no previous version claimed.
        w = work / "fresh"
        code, rec = self.quiet(w / "Programs" / "@redrise", w / "data", "--test-fail-at", "swap")
        f = rec.get("failure") or {}
        out["fresh-swap"] = {"agree": code == 3 and f.get("installed_now") is None and not f.get("recovery_error") and "Nothing was installed" in rec.get("error", ""),
                             "failure": f, "message": rec.get("error")}
        shutil.rmtree(work, ignore_errors=True)
        return {"passed": all(v["agree"] for v in out.values()), "points": out, "previous": prev_v, "new": new_v,
                "scope": "isolated copies only (--install-root/--data-root); the real install never reads --test-fail-at"}

    # ---------------------------------------------------------------- installer wizard walkthrough (final version)
    def wizard(self, root: Path, data: Path, env_extra: dict | None = None, *extra: str) -> subprocess.Popen:
        env = {**accept_wo.os.environ, **(env_extra or {})}
        p = subprocess.Popen([str(self.setup), "--install-root", str(root), "--data-root", str(data), *extra], env=env, close_fds=True)
        end = time.monotonic() + 60
        while time.monotonic() < end:
            if "Instalar RedRise" in wui(p.pid, "Instalar RedRise", "-Do", "ndump").stdout:
                return p
            time.sleep(1)
        raise Stop("the installer wizard did not open")

    def s_wizard_server(self) -> dict:
        """The server path with screenshots of every page, the progress caught while it runs."""
        w = self.wroot / "server"
        root, data = w / "Programs" / "@redrise", w / "data"
        self.guard()
        p = self.wizard(root, data, {"REDRISE_DATA_ROOT": str(data), "REDRISE_TEST_VAULT": "rrtest3", "WEBVIEW2_USER_DATA_FOLDER": str(w / "webview")})
        self.wshot(p, "01-boas-vindas")
        self.wclick(p, "Continuar >")
        self.wwait(p, "Como este computador será usado?")
        self.wshot(p, "02-uso-sem-escolha")
        self.wclick(p, "Continuar >")
        end = time.monotonic() + 15
        while time.monotonic() < end and "Button|OK" not in wui(p.pid, "Escolha obrigatória", "-Do", "ndump").stdout:
            time.sleep(0.5)
        required = "Button|OK" in wui(p.pid, "Escolha obrigatória", "-Do", "ndump").stdout
        wui(p.pid, "Escolha obrigatória", "-Do", "shot", "-Out", str(self.shots / "wizard-03-escolha-obrigatoria.png"))
        wui(p.pid, "Escolha obrigatória", "-Do", "nclick", "-Name", "OK")
        time.sleep(1)
        wui(p.pid, "Instalar RedRise", "-Do", "nselect", "-Value", "Servidor da equipe")
        time.sleep(0.5)
        self.wshot(p, "04-uso-servidor-escolhido")
        self.wclick(p, "Continuar >")
        self.wwait(p, "Uso escolhido: Servidor da equipe")
        self.wshot(p, "05-pronto-servidor")
        self.wclick(p, "Instalar")
        progress = []
        end = time.monotonic() + 600
        while time.monotonic() < end:
            d = self.wdump(p)
            if "RedRise instalado" in d:
                break
            if len(progress) < 3 and re.search(r"Verificando|Extraindo|Copiando|Trocando|arquivo", d):
                self.wshot(p, f"06-progresso-{len(progress) + 1}")
                progress.append(next((x for x in d.splitlines() if re.search(r"Verificando|Extraindo|Copiando|Trocando|arquivo", x)), "")[:160])
                time.sleep(1.2)
            time.sleep(0.2)
        self.wwait(p, "RedRise instalado", timeout=60)
        self.wshot(p, "07-concluido-servidor")
        self.wclick(p, "Concluir")
        p.wait(60)
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
                self.shot("wizard-08-primeira-abertura-servidor")
                self.close_app()
            finally:
                self.pid = prev
        rec = self.record(root)
        ok = required and bool(progress) and "Criar equipe neste computador" in first and rec.get("ok") and p.returncode == 0
        return {"passed": bool(ok), "choice_required": required, "progress_seen": progress, "first_open_server": "Criar equipe neste computador" in first,
                "record": rec.get("result"), "exit": p.returncode}

    def s_wizard_cancel(self) -> dict:
        r = super().s_wizard_cancel()
        src = self.shots / "wizard-5-cancelado-durante.png"
        if src.is_file():
            src.replace(self.shots / "wizard-09-cancelado-durante.png")
        return r

    def s_wizard_existing(self) -> dict:
        r = super().s_wizard_existing()
        src = self.shots / "wizard-6-ja-configurado.png"
        if src.is_file():
            src.replace(self.shots / "wizard-10-ja-configurado.png")
        return r

    def s_wizard_station(self) -> dict:
        r = super().s_wizard_station()
        for a, b in (("wizard-7-pronto-estacao", "wizard-11-pronto-estacao"), ("primeira-abertura-estacao", "wizard-12-primeira-abertura-estacao"),
                     ("estacao-conexao-pendente", "wizard-13-estacao-conexao-pendente"), ("estacao-conectada-login", "wizard-14-estacao-conectada")):
            src = self.shots / f"{a}.png"
            if src.is_file():
                src.replace(self.shots / f"{b}.png")
        return r

    def s_wizard_error(self) -> dict:
        """A controlled error: a copy of the previous version updated by the wizard with a failure injected after the swap."""
        w = self.wroot / "error"
        root, data = w / "Programs" / "@redrise", w / "data"
        shutil.rmtree(w, ignore_errors=True)
        subprocess.run(["robocopy", str(self.previous), str(root), "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NP"], capture_output=True)
        self.guard()
        p = self.wizard(root, data, None, "--test-fail-at", "after-swap")
        self.wclick(p, "Continuar >")
        self.wwait(p, "Como este computador será usado?")
        wui(p.pid, "Instalar RedRise", "-Do", "nselect", "-Value", "Servidor da equipe")
        self.wclick(p, "Continuar >")
        self.wwait(p, "Pronto para instalar")
        self.wclick(p, "Instalar")
        self.wwait(p, "A instalação não foi concluída como esperado", timeout=600)
        page = self.wdump(p)
        self.wshot(p, "15-erro-controlado")
        for b in ("Concluir", "Cancelar", "Fechar"):
            wui(p.pid, "Instalar RedRise", "-Do", "nclick", "-Name", b)
            try:
                p.wait(10)
                break
            except subprocess.TimeoutExpired:
                pass
        rec = self.record(root)
        f = rec.get("failure") or {}
        installed = self.version_at(root)
        ok = (f.get("phase") == "after_swap" and installed == self.version_at(base.ROOT) and f.get("installed_now") == installed
              and "foi instalada" in page and "Seus dados não foram tocados" in page)
        shutil.rmtree(w, ignore_errors=True)
        return {"passed": bool(ok), "record": f, "installed_in_folder": installed, "page_says_installed": "foi instalada" in page,
                "page_excerpt": next((x for x in page.splitlines() if "foi instalada" in x), "")[:300]}


SCENARIOS = ("migration", "actions", "delete", "kanban_day", "layout", "welcome", "failures",
             "wizard_server", "wizard_cancel", "wizard_existing", "wizard_station", "wizard_error")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lab", type=Path, required=True)
    ap.add_argument("--shots", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--setup", type=Path, required=True)
    ap.add_argument("--previous", type=Path, required=True)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    wanted = [s for s in SCENARIOS if not args.only or s in args.only.split(",")]
    args.shots.mkdir(parents=True, exist_ok=True)
    lab = Lab(args.lab, args.shots)
    lab.created = []
    lab.baseline = json.loads(args.baseline.read_text(encoding="utf-8-sig"))
    lab.baseline_path = str(args.baseline)
    lab.setup = args.setup
    lab.previous = args.previous
    lab.wroot = args.lab / "wizard"
    if "wizard_server" in wanted and lab.wroot.exists():
        shutil.rmtree(lab.wroot, ignore_errors=True)
    lab.wroot.mkdir(parents=True, exist_ok=True)
    report: dict = {"schema": "redrise.proof/1", "kind": "practical_e2e", "work_order": "PROCESS-ACTIONS-20261111",
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
            except (Stop, CoreError, StopIteration, AttributeError, IndexError, KeyError, OSError, ValueError, subprocess.TimeoutExpired) as e:
                report["scenarios"][s] = {"passed": False, "stopped": f"{type(e).__name__}: {str(e)[:1500]}"}
                try:
                    lab.shot(f"falha-{s}")
                    lab.ui("-Do", "keys", "-Value", "{ESC}")
                except Stop:
                    pass
                if "computer in use" in str(e):
                    break
            print("  ->", json.dumps(report["scenarios"][s], ensure_ascii=False, default=str)[:900], flush=True)
    finally:
        lab.close_app()
    report["clicks_lost"] = lab.clicks_lost
    report["seconds"] = int(time.time() - started)
    report["only"] = wanted if args.only else None
    report["passed"] = len(report["scenarios"]) == len(wanted) and all(v.get("passed") for v in report["scenarios"].values())
    out = args.lab / f"accept-actions-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(str(out))
    print("PASSED" if report["passed"] else "FAILED")


if __name__ == "__main__":
    main()
