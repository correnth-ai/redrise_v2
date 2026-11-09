"""Scheduled processes (work order SCHEDULE-PROCESS-20261107) on the real Core: isolated PostgreSQL on C:,
HTTPS API with pinning, the scheduler pass called by the test with a controlled clock, Runner calls made by the
test as a declared simulated Runner.

    cd tests/core && <lab python> -B -m unittest test_schedules
Env: RR_PG_BIN, RR_CORE_SITE (as test_core)."""

import unittest
import uuid
from datetime import datetime, timedelta, timezone

import test_core
from test_core import PW, Harness
from redrise_core.service import Core
from psycopg.rows import dict_row

CALC = {"target": {"kind": "app", "app_id": "Calc!App", "name": "Calculadora"}, "isolated": True}
TZ = "America/Sao_Paulo"
ALL_DAYS = [1, 2, 3, 4, 5, 6, 7]


class ScheduleTest(Harness, unittest.TestCase):
    # ---------------------------------------------------------------- helpers
    def process(self, steps=1):
        a = self.admin()
        pid = a.call("POST", "/api/v1/processes", {"name": f"p-{uuid.uuid4().hex[:6]}", "items": []})["id"]
        for i in range(steps):
            body = {"name": f"r-{uuid.uuid4().hex[:6]}", "category": "windows", "version": {"kind": "app_open", "config": CALC}}
            if i == 0:
                body["link"] = {"process_id": pid}
                a.call("POST", "/api/v1/routines", body)
            else:
                rid = a.call("POST", "/api/v1/routines", body)["routine"]["id"]
                a.call("POST", f"/api/v1/processes/{pid}/items", {"routine_id": rid})
        return pid

    def setUp(self):
        # Each pass handles every due schedule of the team: earlier tests' schedules are paused so counts are this test's.
        with self.su() as c:
            c.execute("UPDATE schedules SET enabled = false, next_run_at = NULL, next_slot_local = NULL")
        self.sid, self.runner, self.hb = self.station(f"st-{uuid.uuid4().hex[:6]}")
        self.core = self.h.core

    def schedule(self, pid, client=None, **kw):
        body = {"process_id": pid, "station_id": self.sid, "weekdays": ALL_DAYS, "hour": 3, "minute": 0, "timezone": TZ, **kw}
        return (client or self.admin()).call("POST", "/api/v1/schedules", body)

    def due(self, sched):
        return datetime.fromisoformat(sched["next_run_at"])

    def row(self, sched_id):
        return next(s for s in self.admin().call("GET", "/api/v1/schedules") if s["id"] == sched_id)

    def runs(self, sched_id):
        return self.admin().call("GET", f"/api/v1/schedules/{sched_id}/runs")

    def tick(self, now):
        self.runner.call("POST", "/api/v1/runner/heartbeat", self.hb)  # the station stays connected for the pass
        return self.core.schedule_tick(now)

    def executions_for(self, sched_id):
        with self.su() as c:
            return c.cursor(row_factory=dict_row).execute(
                "SELECT id, request_id, state, outcome FROM executions WHERE schedule_id = %s ORDER BY created_at", (sched_id,)).fetchall()

    def notes(self, client=None):
        return [n for n in (client or self.admin()).call("GET", "/api/v1/notifications")["items"] if n["kind"] == "schedule"]

    def set_due(self, sched_id, at: datetime, slot: str):
        with self.su() as c:
            c.execute("UPDATE schedules SET next_run_at = %s, next_slot_local = %s WHERE id = %s", (at, slot, sched_id))

    # ---------------------------------------------------------------- tests
    def test_01_due_occurrence_starts_once_with_both_links(self):
        s = self.schedule(self.process())
        at = self.due(s)
        self.assertEqual(self.tick(at - timedelta(seconds=5))["started"], 0, "not before its time")
        self.assertEqual(self.tick(at + timedelta(seconds=5))["started"], 1)
        runs = self.runs(s["id"])
        ex = self.executions_for(s["id"])
        self.assertEqual((len(runs), runs[0]["state"], len(ex)), (1, "started", 1))
        self.assertEqual(runs[0]["execution_id"], str(ex[0]["id"]))
        self.assertEqual(ex[0]["request_id"], f"agenda-{s['id']}-{runs[0]['slot_local'].replace('-', '').replace('T', '').replace(':', '')}")
        e = self.admin().call("GET", f"/api/v1/executions/{ex[0]['id']}")
        self.assertEqual((e["schedule_id"], e["requested_by"]), (s["id"], "admin"))
        self.assertEqual(self.tick(at + timedelta(seconds=40))["started"], 0, "a second pass does not repeat it")
        restarted = Core(self.h.database, {})  # what a new Core process does on the same data
        self.assertEqual(restarted.schedule_tick(at + timedelta(seconds=60))["started"], 0)
        self.assertEqual(len(self.executions_for(s["id"])), 1)
        self.assertGreater(self.due(self.row(s["id"])), at + timedelta(hours=23), "next is the following day")

    def test_02_a_crash_before_commit_leaves_neither_occurrence_nor_execution(self):
        s = self.schedule(self.process())
        at = self.due(s)
        real = self.core._schedule_run

        def crash(c, sched, state, *a, **kw):
            if state == "started":
                raise RuntimeError("simulated crash after the execution was created")
            return real(c, sched, state, *a, **kw)

        self.core._schedule_run = crash
        try:
            out = self.tick(at + timedelta(seconds=5))
        finally:
            self.core._schedule_run = real
        self.assertEqual(out["started"], 0)
        self.assertEqual(len(out["errors"]), 1)
        self.assertEqual((self.runs(s["id"]), self.executions_for(s["id"])), ([], []))
        with self.su() as c:
            self.assertIsNone(c.execute("SELECT 1 FROM executions WHERE request_id LIKE %s", (f"agenda-{s['id']}-%",)).fetchone())
        self.assertEqual(self.due(self.row(s["id"])), at, "still due: the next pass handles it")
        self.assertEqual(self.tick(at + timedelta(seconds=35))["started"], 1)
        self.assertEqual(len(self.executions_for(s["id"])), 1)

    def test_03_refused_start_is_skipped_and_pauses_without_a_loose_execution(self):
        pid = self.process()
        s = self.schedule(pid)
        with self.su() as c:
            c.execute("DELETE FROM process_items WHERE process_id = %s", (pid,))  # the process lost its step 1
        out = self.tick(self.due(s) + timedelta(seconds=5))
        self.assertEqual(out["skipped"], 1)
        r = self.runs(s["id"])[0]
        self.assertEqual((r["state"], r["reason"], r["execution_id"]), ("skipped", "process_unavailable", None))
        self.assertEqual(self.executions_for(s["id"]), [])
        row = self.row(s["id"])
        self.assertEqual((row["enabled"], row["paused_reason"], row["next_run_at"]), (False, "process_unavailable", None))
        self.assertTrue(any(n["schedule_reason"] == "process_unavailable" for n in self.notes()))

    def test_04_station_unavailable_and_previous_still_running_are_skipped(self):
        s = self.schedule(self.process())
        at = self.due(s)
        self.hb = {**self.hb, "session_state": "locked", "session_reason": "tela bloqueada"}
        self.assertEqual(self.tick(at + timedelta(seconds=5))["skipped"], 1)
        r = self.runs(s["id"])[0]
        self.assertEqual((r["state"], r["reason"]), ("skipped", "station_unavailable"))
        self.assertEqual(self.executions_for(s["id"]), [], "nothing queued")
        self.assertTrue(any(n["schedule_reason"] == "station_unavailable" and n["schedule_state"] == "skipped" for n in self.notes()))
        self.hb = {**self.hb, "session_state": "ready", "session_reason": None}
        nxt = self.due(self.row(s["id"]))
        self.assertEqual(self.tick(nxt + timedelta(seconds=5))["started"], 1)  # a run waiting in the queue
        nxt2 = self.due(self.row(s["id"]))
        self.set_due(s["id"], nxt + timedelta(minutes=5), "2099-01-01T00:00")  # the next slot comes while it still runs
        self.assertEqual(self.tick(nxt + timedelta(minutes=5, seconds=5))["skipped"], 1)
        self.assertEqual(self.runs(s["id"])[0]["reason"], "previous_still_running")
        self.assertEqual(len(self.executions_for(s["id"])), 1)
        self.assertIsNotNone(nxt2)

    def test_05_not_started_within_the_grace_expires_and_says_so(self):
        s = self.schedule(self.process(steps=2))
        at = self.due(s)
        self.assertEqual(self.tick(at + timedelta(seconds=5))["started"], 1)  # the station then gets busy: nobody claims
        self.assertEqual(self.tick(at + timedelta(minutes=14))["expired"], 0, "still inside the grace")
        self.assertEqual(self.tick(at + timedelta(minutes=16))["expired"], 1)
        r = self.runs(s["id"])[0]
        self.assertEqual((r["state"], r["reason"]), ("expired", "not_started"))
        e = self.admin().call("GET", f"/api/v1/executions/{r['execution_id']}")
        self.assertEqual((e["state"], e["outcome"]), ("finished", "cancelled"))
        self.assertEqual([x["state"] for x in e["steps"]], ["cancelled", None], "step 2 never queued")
        self.assertEqual(e["steps"][0]["error_code"], "SCHEDULE-NOT-STARTED")
        self.assertTrue(any(n["schedule_state"] == "expired" for n in self.notes()))
        self.assertIsNone(self.runner.call("POST", "/api/v1/runner/claim", self.hb)["job"], "nothing left for the station")

    def test_06_claimed_but_never_started_expires_too(self):
        s = self.schedule(self.process())
        at = self.due(s)
        self.tick(at + timedelta(seconds=5))
        job = self.runner.call("POST", "/api/v1/runner/claim", self.hb)["job"]
        self.assertIsNotNone(job)  # claimed, then the station disconnects before starting
        self.assertEqual(self.tick(at + timedelta(minutes=16))["expired"], 1)
        go = self.runner.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/start", {"lease_id": job["lease_id"]})
        self.assertEqual(go, {"proceed": False, "reason": "cancelled"})
        self.assertEqual(self.runs(s["id"])[0]["state"], "expired")

    def test_07_core_stopped_short_runs_late_once_long_is_missed(self):
        s = self.schedule(self.process())
        at = self.due(s)
        self.assertEqual(self.tick(at + timedelta(minutes=10))["started"], 1, "10 min late: still runs")
        self.admin().call("PATCH", f"/api/v1/schedules/{s['id']}", {"enabled": False})
        s2 = self.schedule(self.process(), hour=4)
        at2 = self.due(s2)
        now = at2 + timedelta(days=2, hours=2)  # stopped across three occurrences
        out = self.tick(now)
        self.assertEqual((out["missed"], out["started"]), (1, 0))
        runs = self.runs(s2["id"])
        self.assertEqual([(r["state"], r["reason"]) for r in runs], [("missed", "core_stopped")], "one missed, not three, and no run")
        self.assertEqual(self.executions_for(s2["id"]), [])
        self.assertGreater(self.due(self.row(s2["id"])), now, "the next one is in the future")

    def test_08_pause_edit_resume_never_run_retroactively(self):
        s = self.schedule(self.process())
        at = self.due(s)
        a = self.admin()
        paused = a.call("PATCH", f"/api/v1/schedules/{s['id']}", {"enabled": False})
        self.assertEqual((paused["enabled"], paused["next_run_at"], paused["paused_reason"]), (False, None, "paused_by_user"))
        self.assertEqual(sum(v for k, v in self.tick(at + timedelta(minutes=5)).items() if k != "errors"), 0)
        resumed = a.call("PATCH", f"/api/v1/schedules/{s['id']}", {"enabled": True})
        self.assertGreater(self.due(resumed), datetime.now(timezone.utc), "resume: next future occurrence only")
        edited = a.call("PATCH", f"/api/v1/schedules/{s['id']}", {"hour": 5, "minute": 30})
        self.assertGreater(self.due(edited), datetime.now(timezone.utc))
        self.assertEqual((edited["hour"], edited["minute"]), (5, 30))
        self.assertEqual(self.runs(s["id"]), [])

    def test_09_local_time_identity_with_daylight_saving(self):
        ny = "America/New_York"  # 2026: 02:30 does not exist on 8 March; 01:30 happens twice on 1 November
        slot, at = Core.next_slot(127, 2, 30, ny, datetime(2026, 3, 8, 0, tzinfo=timezone.utc))
        self.assertEqual(slot, "2026-03-09T02:30", "the missing hour skips that day")
        slot, at = Core.next_slot(127, 1, 30, ny, datetime(2026, 11, 1, 4, tzinfo=timezone.utc))
        self.assertEqual((slot, at), ("2026-11-01T01:30", datetime(2026, 11, 1, 5, 30, tzinfo=timezone.utc)), "first of the two 01:30")
        slot2, _ = Core.next_slot(127, 1, 30, ny, at)
        self.assertEqual(slot2, "2026-11-02T01:30", "the repeated 01:30 is not a second occurrence")
        slot, at = Core.next_slot(0b0010001, 9, 0, TZ, datetime(2026, 11, 7, 15, tzinfo=timezone.utc))  # Mon and Fri; 7 Nov is a Saturday
        self.assertEqual(slot, "2026-11-09T09:00")
        s = self.schedule(self.process(), timezone=ny)
        self.assertEqual(self.row(s["id"])["timezone"], ny, "kept with the schedule, not the server's")

    def test_10_owner_demoted_or_deactivated_pauses_and_warns_admins(self):
        a = self.admin()
        name = f"adm-{uuid.uuid4().hex[:5]}"
        uid = a.call("POST", "/api/v1/users", {"username": name, "display": "Admin 2", "password": PW, "role": "admin"})["id"]
        other = self.client(self.client().call("POST", "/api/v1/login", {"username": name, "password": PW})["token"])
        s = self.schedule(self.process(), client=other)
        a.call("PATCH", f"/api/v1/users/{uid}", {"role": "operator"})
        out = self.tick(self.due(s) + timedelta(seconds=5))
        self.assertEqual(out["skipped"], 1)
        r = self.runs(s["id"])[0]
        self.assertEqual((r["state"], r["reason"]), ("skipped", "owner_not_allowed"))
        row = self.row(s["id"])
        self.assertEqual((row["enabled"], row["paused_reason"]), (False, "owner_not_allowed"))
        self.assertEqual(self.executions_for(s["id"]), [])
        self.assertTrue(any(n["schedule_reason"] == "owner_not_allowed" for n in self.notes()), "the remaining admin is told")
        resumed = a.call("PATCH", f"/api/v1/schedules/{s['id']}", {"enabled": True})
        self.assertEqual((resumed["enabled"], resumed["owner_name"]), (True, "Admin"), "resuming makes that administrator the owner")
        s2 = self.schedule(self.process(), client=a)
        with self.su() as c:  # deactivated (an administrator cannot deactivate themself through the API)
            c.execute("UPDATE schedules SET owner_id = %s WHERE id = %s", (uid, s2["id"]))
            c.execute("UPDATE users SET active = false, role = 'admin' WHERE id = %s", (uid,))
        self.tick(self.due(s2) + timedelta(seconds=5))
        self.assertEqual(self.runs(s2["id"])[0]["reason"], "owner_not_allowed")

    def test_11_permissions_and_input(self):
        pid = self.process()
        a = self.admin()
        a.call("POST", "/api/v1/users", {"username": "oper-sch", "display": "Op", "password": PW, "role": "operator"})
        op = self.client(self.client().call("POST", "/api/v1/login", {"username": "oper-sch", "password": PW})["token"])
        s = self.schedule(pid)
        self.assertTrue(any(x["id"] == s["id"] for x in op.call("GET", "/api/v1/schedules")), "operators see them")
        op.call("GET", f"/api/v1/schedules/{s['id']}/runs")
        body = {"process_id": pid, "station_id": self.sid, "weekdays": ALL_DAYS, "hour": 3, "minute": 0, "timezone": TZ}
        for fn in (lambda: op.call("POST", "/api/v1/schedules", body), lambda: op.call("POST", "/api/v1/schedules/preview", body),
                   lambda: op.call("PATCH", f"/api/v1/schedules/{s['id']}", {"enabled": False}),
                   lambda: op.call("DELETE", f"/api/v1/schedules/{s['id']}")):
            self.expect("AUTH-FORBIDDEN", fn, 403)
        self.expect("AUTH-REQUIRED", lambda: self.client().call("GET", "/api/v1/schedules"), 401)
        for bad in ({"weekdays": []}, {"weekdays": [0]}, {"hour": 24}, {"minute": -1}, {"timezone": "Lua/Base"}, {"timezone": "../x"}):
            self.expect("VALIDATION", lambda bad=bad: a.call("POST", "/api/v1/schedules", {**body, **bad}), 400)
        self.expect("NOT-FOUND", lambda: a.call("POST", "/api/v1/schedules", {**body, "process_id": 999999}), 404)
        p = a.call("POST", "/api/v1/schedules/preview", body)
        self.assertGreater(datetime.fromisoformat(p["next_run_at"]), datetime.now(timezone.utc))
        self.assertEqual(a.call("DELETE", f"/api/v1/schedules/{s['id']}"), {"deleted": True})
        self.expect("NOT-FOUND", lambda: a.call("GET", f"/api/v1/schedules/{s['id']}/runs"), 404)


if __name__ == "__main__":
    unittest.main()
