"""Practical acceptance of work order SCHEDULE-PROCESS-20261107 on the installed candidate: real app,
Core, Runner and Windows, with the isolated synthetic team of the lab. Run on C: with the private
runtime of the install, computer free:

    <install>\\runtime\\python\\python.exe -B -X utf8 accept_schedule.py --lab <lab-test> --shots <dir> --baseline <json>

Reuses the harness of proofs/nova-rotina/accept_increments.py and the Empresa helpers of
proofs/stabilization/accept_s4.py (both copied next to this folder in the lab). Stops if someone
uses the computer, opens only the Calculator (through the Runner) and closes only windows it opened.
Passwords and the runner token of the synthetic station stay in memory and are never printed.

 migration   the team written by the previous version reopens on this one: every table it had keeps its
             count, migration 010 is the only new migration, the schedule tables start empty, and a backup
             was written before migrating.
 scheduled   Processo > Acao > Agendar on a one-step Calculator process, through the screen: the dialog shows
             the next time computed by the Core; scheduled 2 min ahead, it starts with no click, ends verified,
             is marked "Agendada" in Historico and is counted in Empresa (cards equal the Core).
 skipped     a schedule on a registered station that never connected: at the time the occurrence is skipped
             (station_unavailable), no execution is created, and the notice reaches the bell.
 roles       an operator reads the schedules and cannot create, edit or delete one; no token is refused.
At the end the proof's schedules are paused (kept as evidence) and its synthetic station is revoked."""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "nova-rotina"))  # the private runtime runs isolated: no script folder on sys.path
sys.path.insert(0, str(HERE.parent / "stabilization"))

import accept_increments as base  # noqa: E402
import accept_s4  # noqa: E402
from redrise_contracts.client import CoreClient, CoreError  # noqa: E402

Stop = base.Stop


class Lab(accept_s4.Lab):
    created: list[int]
    offline_station: int | None = None

    # ---------------------------------------------------------------- helpers
    def calc_process(self, name: str) -> dict:
        calc = self.calc()
        cfg = {"kind": "app_open", "config": {"target": {"kind": "app", "app_id": calc["id"], "name": calc["name"]}, "isolated": True}}
        p = self.empty_process(name)
        self.api.call("POST", "/api/v1/routines", {"name": f"{name} - abrir", "category": "windows", "version": cfg, "link": {"process_id": p["id"]}})
        return self.api.call("GET", f"/api/v1/processes/{p['id']}")

    @staticmethod
    def target(lead_s: int = 120) -> datetime:
        """A local minute at least lead_s ahead (the dialog and the Core both work in whole minutes)."""
        now = datetime.now()
        t = (now + timedelta(seconds=lead_s)).replace(second=0, microsecond=0)
        return t if (t - now).total_seconds() >= lead_s - 20 else t + timedelta(minutes=1)

    def runs(self, sid: int) -> list[dict]:
        return self.api.call("GET", f"/api/v1/schedules/{sid}/runs")

    def wait_run(self, sid: int, slot: datetime, timeout: float) -> dict:
        key = slot.strftime("%Y-%m-%dT%H:%M")
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            for r in self.runs(sid):
                if r["slot_local"] == key:
                    return r
            time.sleep(2)
        raise Stop(f"no occurrence recorded for {key} within {int(timeout)} s")

    def type_time(self, t: datetime) -> str:
        for kind in ("Edit", "Spinner", "Group", "Custom"):
            out = self.ui("-Do", "focus", "-Name", "Horário", "-Type", kind)
            if "focused" in out.stdout:
                self.ui("-Do", "keys", "-Value", t.strftime("%H%M"))
                return kind
        raise Stop("the time field could not be focused")

    def preview_text(self) -> str:
        return next((line.split("|")[1] for line in self.texts() if "Próxima execução:" in line), "")

    def open_schedule_dialog(self, proc: dict) -> int:
        """Agendar is an icon action on every process row with steps: open each until the dialog names this process."""
        n = sum(1 for line in self.texts() if line.startswith("Button|Agendar|"))
        for i in range(n):
            self.ui("-Do", "invoke", "-Name", "Agendar", "-Type", "Button", "-Index", str(i))
            time.sleep(1.2)
            if self.has(f"Agendar {proc['name']}"):
                return i
            self.ui("-Do", "keys", "-Value", "{ESC}")
            time.sleep(0.8)
        raise Stop(f"no Agendar action opened the dialog of {proc['name']}")

    # ---------------------------------------------------------------- scenarios
    def s_migration(self) -> dict:
        if not self.baseline:
            raise Stop("no --baseline: data preservation cannot be compared")
        from rollback_check import table_counts
        from redrise_contracts.vault import WindowsVault
        cfg = json.loads((self.lab / "data" / "host" / "host.json").read_text(encoding="utf-8-sig"))
        tables = table_counts(cfg["pg_port"], WindowsVault("rrtest2-host"), "redrise")
        b = self.baseline["tables"]
        kept = {t: (tables.get(t), n) for t, n in b.items() if t != "schema_migrations"}
        backups = sorted((self.lab / "data" / "host" / "backups").glob("pre-migration-*.dump"), key=lambda p: p.stat().st_mtime)
        b_time = Path(self.baseline_path).stat().st_mtime
        newest = backups[-1] if backups else None
        ok = (all(now == was for now, was in kept.values()) and tables.get("schema_migrations") == b.get("schema_migrations", 0) + 1
              and tables.get("schedules") == 0 and tables.get("schedule_runs") == 0
              and newest is not None and newest.stat().st_mtime >= b_time)
        return {"passed": ok, "baseline_from": self.baseline.get("install"), "tables": tables, "baseline_tables": b,
                "backup_before_migration": newest.name if newest else None}

    def s_scheduled(self) -> dict:
        proc = self.calc_process(f"Prova agendada {self.seq}")
        stations = [s for s in self.api.call("GET", "/api/v1/stations") if not s.get("revoked")]
        if not stations or stations[0]["id"] != self.station:
            raise Stop(f"the dialog's default station is not the ready lab station: {[s['name'] for s in stations][:5]}")
        before = self.api.call("GET", "/api/v1/executions/summary")["total"]
        self.guard()
        self.page("Ação")
        self.wait("Agendamentos", timeout=30)
        self.open_schedule_dialog(proc)
        t = self.target()
        day = t.isoweekday()
        days = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        if day >= 6:  # the dialog starts on Monday to Friday
            self.invoke(days[day - 1], "CheckBox")
            time.sleep(0.5)
        field = self.type_time(t)
        want = f"Próxima execução: {t:%d/%m/%Y %H:%M}"
        end = time.monotonic() + 15
        while time.monotonic() < end and self.preview_text() != want:
            time.sleep(0.5)
        shown = self.preview_text()
        self.shot("agendar-dialogo")
        if shown != want:
            self.ui("-Do", "keys", "-Value", "{ESC}")
            raise Stop(f"preview {shown!r}, expected {want!r}")
        n = sum(1 for line in self.texts() if line.startswith("Button|Agendar|"))
        self.ui("-Do", "invoke", "-Name", "Agendar", "-Type", "Button", "-Index", str(n - 1))  # the dialog's own button is last in the tree
        end = time.monotonic() + 15
        mine = []
        while time.monotonic() < end and not mine:
            mine = [s for s in self.api.call("GET", "/api/v1/schedules") if s["process_id"] == proc["id"]]
            time.sleep(0.5)
        if len(mine) != 1:
            raise Stop(f"the dialog did not create exactly one schedule: {len(mine)}")
        s = mine[0]
        self.created.append(s["id"])
        time.sleep(1.5)
        listed = self.has(proc["name"], f"{t:%d/%m/%Y %H:%M}")
        self.shot("agendamentos-lista")

        wins = base.calc_windows()
        wait_s = (t - datetime.now()).total_seconds() + 90  # the Core looks every 30 s
        run = self.wait_run(s["id"], t, wait_s)
        e = self.wait_execution(run["execution_id"], ("finished",), timeout=120) if run.get("execution_id") else None
        time.sleep(1)
        left = self.close_new_calc(wins)
        late_s = None
        if e:
            started = datetime.fromisoformat(e["created_at"]).astimezone().replace(tzinfo=None)
            late_s = round((started - t).total_seconds(), 1)

        self.page("Histórico")
        self.wait(proc["name"], timeout=30)
        time.sleep(1.5)
        marked = self.has("Agendada")
        self.shot("historico-agendada")
        self.empresa()
        self.wait("Ver no histórico", timeout=30)
        time.sleep(2)
        emp = self.compare_empresa()
        after = self.api.call("GET", "/api/v1/executions/summary")["total"]
        self.shot("empresa-depois-agendada")
        ok = (s["timezone"] and s["next_slot_local"] == t.strftime("%Y-%m-%dT%H:%M") and listed and run["state"] == "started"
              and e is not None and e["state"] == "finished" and e["outcome"] == "verified" and e.get("schedule_id") == s["id"]
              and e["request_id"] == f"agenda-{s['id']}-{t:%Y%m%d%H%M}" and late_s is not None and 0 <= late_s <= 45
              and marked and emp["passed"] and after == before + 1 and not left)
        return {"passed": bool(ok), "process": proc["name"], "time_field": field, "preview": shown, "schedule": {k: s[k] for k in (
                    "id", "weekdays", "hour", "minute", "timezone", "next_slot_local", "owner_name")},
                "listed_on_screen": listed, "run": {k: run.get(k) for k in ("slot_local", "state", "reason", "execution_id")},
                "execution": {k: e.get(k) for k in ("state", "outcome", "schedule_id", "request_id")} if e else None,
                "started_seconds_after_time": late_s, "marked_agendada": marked, "empresa_equal_core": emp["passed"],
                "empresa_diff": emp["diff"], "executions_30d": [before, after], "windows_not_closed": len(left)}

    def s_skipped(self) -> dict:
        proc = next(p for p in self.api.call("GET", "/api/v1/processes") if p["name"] == f"Prova agendada {self.seq}")
        st = self.api.call("POST", "/api/v1/stations", {"name": f"prova-desligada-{self.seq}"})  # its runner token is never kept
        self.offline_station = st["station"]["id"]
        execs_before = {x["id"] for x in self.api.call("GET", "/api/v1/executions")}
        t = self.target(80)
        zone = next(s["timezone"] for s in self.api.call("GET", "/api/v1/schedules") if s["id"] in self.created)
        s = self.api.call("POST", "/api/v1/schedules", {"process_id": proc["id"], "station_id": self.offline_station,
                                                         "weekdays": [t.isoweekday()], "hour": t.hour, "minute": t.minute, "timezone": zone})
        self.created.append(s["id"])
        unseen0 = self.api.call("GET", "/api/v1/notifications")["unseen"]
        run = self.wait_run(s["id"], t, (t - datetime.now()).total_seconds() + 90)
        new = [x for x in self.api.call("GET", "/api/v1/executions") if x["id"] not in execs_before]
        notes = [n for n in self.api.call("GET", "/api/v1/notifications")["items"] if n.get("schedule_run_id") == run["id"]]
        nxt = next(x for x in self.api.call("GET", "/api/v1/schedules") if x["id"] == s["id"])
        self.guard()
        self.page("Ação")
        self.wait("Agendamentos", timeout=30)
        time.sleep(2)
        bell_name = next((line.split("|")[1] for line in self.texts() if line.startswith("Button|Notificações")), "")
        self.click(bell_name)
        time.sleep(1.2)
        text = "Agendamento pulado: estação indisponível no horário"
        in_bell = self.has(text)
        self.shot("sino-agendamento-pulado")
        self.ui("-Do", "keys", "-Value", "{ESC}")
        time.sleep(0.8)
        listed = self.has("Estação indisponível no horário")
        ok = (run["state"] == "skipped" and run["reason"] == "station_unavailable" and run["execution_id"] is None and not new
              and len(notes) == 1 and in_bell and bell_name.startswith("Notificações, ") and nxt["enabled"]
              and nxt["next_slot_local"] > t.strftime("%Y-%m-%dT%H:%M") and listed)
        return {"passed": bool(ok), "run": {k: run.get(k) for k in ("slot_local", "state", "reason", "execution_id")},
                "executions_created": len(new), "notifications": len(notes), "unseen_before": unseen0, "bell_button": bell_name,
                "bell_text_seen": in_bell, "listed_reason": listed, "next_slot_local": nxt["next_slot_local"]}

    def s_roles(self) -> dict:
        name = f"oper.agenda.{self.seq}"
        pw = secrets.token_urlsafe(12)
        self.api.call("POST", "/api/v1/users", {"username": name, "display": f"Operador agenda {self.seq}", "password": pw, "role": "operator"})
        cfg = json.loads((self.lab / "data" / "host" / "host.json").read_text(encoding="utf-8-sig"))
        tok = CoreClient("127.0.0.1", base.PORT, cfg["fingerprint"]).call("POST", "/api/v1/login", {"username": name, "password": pw})["token"]
        op = CoreClient("127.0.0.1", base.PORT, cfg["fingerprint"], tok)
        sid = self.created[0]
        body = {"process_id": 1, "station_id": self.station, "weekdays": [1], "hour": 8, "minute": 0, "timezone": "America/Sao_Paulo"}

        def code(fn):
            try:
                fn()
                return "allowed"
            except CoreError as e:
                return e.diagnostic.error_code

        out = {"operator_lists": code(lambda: op.call("GET", "/api/v1/schedules")),
               "operator_reads_runs": code(lambda: op.call("GET", f"/api/v1/schedules/{sid}/runs")),
               "operator_creates": code(lambda: op.call("POST", "/api/v1/schedules", body)),
               "operator_pauses": code(lambda: op.call("PATCH", f"/api/v1/schedules/{sid}", {"enabled": False})),
               "operator_deletes": code(lambda: op.call("DELETE", f"/api/v1/schedules/{sid}")),
               "no_token_lists": code(lambda: CoreClient("127.0.0.1", base.PORT, cfg["fingerprint"]).call("GET", "/api/v1/schedules"))}
        uid = next(u["id"] for u in self.api.call("GET", "/api/v1/users") if u["username"] == name)
        self.api.call("PATCH", f"/api/v1/users/{uid}", {"active": False})
        want = {"operator_lists": "allowed", "operator_reads_runs": "allowed", "operator_creates": "AUTH-FORBIDDEN",
                "operator_pauses": "AUTH-FORBIDDEN", "operator_deletes": "AUTH-FORBIDDEN", "no_token_lists": "AUTH-REQUIRED"}
        return {"passed": out == want, **out}

    def cleanup(self) -> dict:
        done = {"paused": [], "station_revoked": None}
        for sid in self.created:
            try:
                self.api.call("PATCH", f"/api/v1/schedules/{sid}", {"enabled": False})
                done["paused"].append(sid)
            except CoreError as e:
                done.setdefault("errors", []).append(e.diagnostic.error_code)
        if self.offline_station:
            try:
                self.api.call("DELETE", f"/api/v1/stations/{self.offline_station}")
                done["station_revoked"] = True
            except CoreError as e:
                done["station_revoked"] = e.diagnostic.error_code
        return done


SCENARIOS = ("migration", "scheduled", "skipped", "roles")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lab", type=Path, required=True)
    ap.add_argument("--shots", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=True, help="counts recorded by the previous version (rollback_check.py --baseline-with)")
    args = ap.parse_args()
    args.shots.mkdir(parents=True, exist_ok=True)
    lab = Lab(args.lab, args.shots)
    lab.created = []
    lab.baseline = json.loads(args.baseline.read_text(encoding="utf-8-sig"))
    lab.baseline_path = str(args.baseline)
    report: dict = {"schema": "redrise.proof/1", "kind": "practical_e2e", "work_order": "SCHEDULE-PROCESS-20261107",
                    "install": base.ROOT.name, "scenarios": {}}
    started = time.time()
    try:
        lab.guard()
        lab.start_app()
        report["core"] = lab.api.call("GET", "/api/v1/status")["core"]
        for s in SCENARIOS:
            print("scenario", s, flush=True)
            try:
                report["scenarios"][s] = getattr(lab, f"s_{s}")()
            except (Stop, CoreError, StopIteration) as e:
                report["scenarios"][s] = {"passed": False, "stopped": f"{type(e).__name__}: {str(e)[:1500]}"}
                try:
                    lab.shot(f"agenda-falha-{s}")
                    lab.ui("-Do", "keys", "-Value", "{ESC}")
                except Stop:
                    pass
                if "computer in use" in str(e):
                    break
            print("  ->", json.dumps(report["scenarios"][s], ensure_ascii=False)[:600], flush=True)
        if lab.api:
            report["cleanup"] = lab.cleanup()
    finally:
        lab.close_app()
    report["clicks_lost"] = lab.clicks_lost
    report["seconds"] = int(time.time() - started)
    report["passed"] = len(report["scenarios"]) == len(SCENARIOS) and all(v.get("passed") for v in report["scenarios"].values())
    out = args.lab / f"accept-schedule-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out))
    print("PASSED" if report["passed"] else "FAILED")


if __name__ == "__main__":
    main()
