"""Processo > Acao rules of work order PROCESS-ACTIONS-20261111 on the real Core: isolated PostgreSQL on C:, HTTPS API with
pinning, simulated Runner calls (declared). Deleting ONLY the process with the typed word, the ready-made Boas-vindas managed
like any process and not created again once deleted, homonyms that never share an identity, concurrency with starts,
compositions, replacements and the scheduler, and the Kanban of one day in the team time zone. Synthetic data only.

    cd tests/core && <lab python> -B -m unittest test_process_actions
Env: RR_PG_BIN, RR_CORE_SITE (as test_core)."""

import threading
import unittest
import uuid
from datetime import datetime, timedelta, timezone

import test_core
from test_core import PW, Harness

from redrise_core import auth  # noqa: E402  (on sys.path through test_core)
from redrise_core.service import Core  # noqa: E402

CALC = {"target": {"kind": "app", "app_id": "Calc!App", "name": "Calculadora"}, "isolated": True}
DEL = "/api/v1/processes/{}/archive"


class ProcessActionsTest(Harness, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        a = cls.admin()
        cls.admin_id = a.call("GET", "/api/v1/me")["id"]

    def setUp(self):
        self.h.core.limits = auth.AttemptLimiter()
        self.h.core.team_tz = None

    # ---------------------------------------------------------------- helpers
    def routine(self, pid=None):
        body = {"name": f"r-{uuid.uuid4().hex[:6]}", "category": "windows", "version": {"kind": "app_open", "config": CALC}}
        if pid is not None:
            body["link"] = {"process_id": pid}
        return self.admin().call("POST", "/api/v1/routines", body)["routine"]["id"]

    def process(self, name=None, steps=1):
        a = self.admin()
        pid = a.call("POST", "/api/v1/processes", {"name": name or f"p-{uuid.uuid4().hex[:6]}", "items": []})["id"]
        rids = []
        for i in range(steps):
            rid = self.routine(pid if i == 0 else None)
            if i:
                a.call("POST", f"/api/v1/processes/{pid}/items", {"routine_id": rid})
            rids.append(rid)
        return pid, rids

    def delete(self, pid, word="Confirmado", client=None):
        return (client or self.admin()).call("POST", DEL.format(pid), {"confirm": word})

    def processes(self):
        return {p["id"]: p for p in self.admin().call("GET", "/api/v1/processes")}

    def routines(self):
        return {r["id"]: r for r in self.admin().call("GET", "/api/v1/routines")}

    def execution(self, pid, created, sid, state="finished", outcome="verified"):
        """A synthetic execution of `pid` started at `created` (aware datetime or SQL interval before now())."""
        at = created if isinstance(created, datetime) else None
        with self.su() as c:
            return str(c.execute(
                """INSERT INTO executions (request_id, process_id, station_id, requested_by, snapshot, state, outcome, correlation_id,
                                           created_at, finished_at)
                   VALUES (%s, %s, %s, %s, '[]', %s, %s, 'c', coalesce(%s::timestamptz, now() - %s::interval),
                           CASE WHEN %s = 'finished' THEN coalesce(%s::timestamptz, now() - %s::interval) END) RETURNING id""",
                (uuid.uuid4().hex, pid, sid, self.admin_id, state, outcome, at, None if at else created, state, at,
                 None if at else created)).fetchone()[0])

    def ready_station(self):
        return self.station(f"st-{uuid.uuid4().hex[:6]}")

    def operator(self):
        name = f"op{uuid.uuid4().hex[:6]}"
        self.admin().call("POST", "/api/v1/users", {"username": name, "display": name, "password": PW, "role": "operator"})
        return self.client(self.client().call("POST", "/api/v1/login", {"username": name, "password": PW})["token"])

    # ---------------------------------------------------------------- confirmation word and access
    def test_01_the_typed_word_is_checked_trimmed_without_case(self):
        a = self.admin()
        for word in (None, "", "   ", "confirma", "Confirmado!", "confirmado sim", "Confirmad", "nao", "x confirmado"):
            pid, _ = self.process()
            self.expect("PROCESS-DELETE-UNCONFIRMED", lambda: a.call("POST", DEL.format(pid), {"confirm": word} if word is not None else {}), 400)
            self.assertIn(pid, self.processes(), f"{word!r} deleted nothing")
        for word in ("confirmado", "CONFIRMADO", "CoNfIrMaDo", "  Confirmado  "):
            pid, _ = self.process()
            out = self.delete(pid, word)
            self.assertEqual((out["archived"], out["already"]), (True, False))
            self.assertNotIn(pid, self.processes())

    def test_02_operators_and_unknown_ids_are_refused(self):
        pid, _ = self.process()
        op = self.operator()
        self.expect("AUTH-FORBIDDEN", lambda: self.delete(pid, client=op), 403)
        with self.assertRaises(test_core.CoreError) as cm:
            self.client().call("POST", DEL.format(pid), {"confirm": "Confirmado"})  # no session
        self.assertEqual(cm.exception.status, 401)
        self.expect("NOT-FOUND", lambda: self.delete(999999), 404)
        self.assertIn(pid, self.processes())

    # ---------------------------------------------------------------- only the process
    def test_03_exclusive_routines_become_standalone_shared_ones_keep_the_other_process(self):
        a = self.admin()
        pid, (r1, r2) = self.process(steps=2)
        other, (o1,) = self.process()
        a.call("PUT", f"/api/v1/processes/{other}", {"name": "B", "items": [{"routine_id": o1, "continue_next": True},
                                                                             {"routine_id": r2, "continue_next": False}]})
        out = self.delete(pid)
        self.assertEqual(out["routines"], [r1, r2])
        rs = self.routines()
        self.assertIn(r1, rs)  # nothing archived
        self.assertIn(r2, rs)
        procs = self.processes()
        self.assertFalse(any(i["routine_id"] == r1 for p in procs.values() for i in p["items"]), "r1 is standalone")
        self.assertEqual([(i["routine_id"], i["continue_next"]) for i in procs[other]["items"]], [(o1, True), (r2, False)])
        # The standalone routine is the same routine: its kind and configuration (and isolation rule) are untouched.
        self.assertEqual((rs[r1]["kind"], rs[r1]["config"]), ("app_open", CALC))
        with self.su() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM routines WHERE id = ANY(%s) AND archived", ([r1, r2],)).fetchone()[0], 0)

    def test_04_an_empty_process_is_deleted_the_same_way_and_a_repeat_changes_nothing(self):
        a = self.admin()
        pid = a.call("POST", "/api/v1/processes", {"name": "vazio", "items": []})["id"]
        keep = a.call("POST", "/api/v1/processes", {"name": "vazio", "items": []})["id"]
        self.assertEqual(self.delete(pid)["routines"], [])
        again = self.delete(pid)
        self.assertEqual((again["already"], again["process_id"]), (True, pid))
        self.assertIn(keep, self.processes())  # the homonym is not touched by the repeat
        for fn in (lambda: a.call("PUT", f"/api/v1/processes/{pid}", {"name": "x", "items": []}),
                   lambda: a.call("POST", f"/api/v1/processes/{pid}/items", {"routine_id": self.routine()}),
                   lambda: a.call("GET", f"/api/v1/processes/{pid}")):
            self.expect("NOT-FOUND", fn, 404)

    def test_05_running_or_waiting_for_review_refuses_without_touching_the_execution(self):
        sid, r, hb = self.ready_station()
        for state in ("running", "waiting_review"):
            pid, (rid,) = self.process()
            eid = self.execution(pid, "1 minute", sid, state=state, outcome=None)
            self.expect("PROCESS-BUSY", lambda: self.delete(pid), 409)
            self.assertIn(pid, self.processes())
            with self.su() as c:
                self.assertEqual(c.execute("SELECT state FROM executions WHERE id = %s", (eid,)).fetchone()[0], state)
                c.execute("UPDATE executions SET state = 'finished', outcome = 'cancelled', finished_at = now() WHERE id = %s", (eid,))
            self.assertTrue(self.delete(pid)["archived"])
        # Another process sharing a routine with a busy one is not blocked by it.
        busy, (shared,) = self.process()
        self.execution(busy, "1 minute", sid, state="running", outcome=None)
        free = self.admin().call("POST", "/api/v1/processes", {"name": "f", "items": [{"routine_id": shared, "continue_next": True}]})["id"]
        self.assertTrue(self.delete(free)["archived"])
        self.assertEqual([i["routine_id"] for i in self.processes()[busy]["items"]], [shared])

    def test_06_pending_replacements_are_cancelled_and_never_applied(self):
        a = self.admin()
        pid, (r1,) = self.process()
        new = self.routine()
        q = a.call("POST", f"/api/v1/processes/{pid}/step1", {"routine_id": new})
        self.assertEqual(self.delete(pid)["changes_cancelled"], 1)
        row = next(x for x in a.call("GET", "/api/v1/step-changes") if x["id"] == q["id"])
        self.assertEqual(row["status"], "cancelled")
        self.expect("CHANGE-ALREADY-DECIDED", lambda: a.call("POST", f"/api/v1/step-changes/{q['id']}/approve"), 409)
        self.assertFalse(any(n.get("change_id") == q["id"] for n in a.call("GET", "/api/v1/notifications")["items"]))
        self.assertFalse(any(i["routine_id"] == new for p in self.processes().values() for i in p["items"]))

    def test_07_schedules_are_disabled_hidden_and_never_fire_their_history_stays(self):
        a = self.admin()
        sid, r, hb = self.ready_station()
        pid, _ = self.process()
        with self.su() as c:
            c.execute("UPDATE schedules SET enabled = false, next_run_at = NULL, next_slot_local = NULL")
        s = a.call("POST", "/api/v1/schedules", {"process_id": pid, "station_id": sid, "weekdays": [1, 2, 3, 4, 5, 6, 7],
                                                 "hour": 3, "minute": 0, "timezone": "America/Sao_Paulo"})
        due = datetime.fromisoformat(s["next_run_at"])
        r.call("POST", "/api/v1/runner/heartbeat", hb)
        self.assertEqual(self.h.core.schedule_tick(due + timedelta(seconds=5))["started"], 1)
        with self.su() as c:  # the first run ends, so the deletion is allowed
            c.execute("UPDATE executions SET state = 'finished', outcome = 'verified', finished_at = now() WHERE schedule_id = %s", (s["id"],))
        runs_before = a.call("GET", f"/api/v1/schedules/{s['id']}/runs")
        self.assertEqual(self.delete(pid)["schedules_disabled"], 1)
        self.assertNotIn(s["id"], [x["id"] for x in a.call("GET", "/api/v1/schedules")])
        with self.su() as c:
            row = c.execute("SELECT enabled, paused_reason, next_run_at FROM schedules WHERE id = %s", (s["id"],)).fetchone()
            self.assertEqual(row, (False, "process_deleted", None))
            c.execute("UPDATE schedules SET next_run_at = now() - interval '1 minute' WHERE id = %s", (s["id"],))  # even if due
        r.call("POST", "/api/v1/runner/heartbeat", hb)
        self.assertEqual(self.h.core.schedule_tick(datetime.now(timezone.utc) + timedelta(days=2))["started"], 0)
        self.assertEqual([x["id"] for x in a.call("GET", f"/api/v1/schedules/{s['id']}/runs")], [x["id"] for x in runs_before])
        self.expect("NOT-FOUND", lambda: a.call("PATCH", f"/api/v1/schedules/{s['id']}", {"enabled": True}), 404)  # no resume
        self.expect("NOT-FOUND", lambda: a.call("POST", "/api/v1/schedules", {"process_id": pid, "station_id": sid, "weekdays": [1],
                                                                               "hour": 3, "minute": 0, "timezone": "America/Sao_Paulo"}), 404)

    # ---------------------------------------------------------------- Boas-vindas
    def test_08_boas_vindas_is_managed_like_any_process_and_not_created_again(self):
        a = self.admin()
        w = next(p for p in self.processes().values() if p["system_key"] == "boas-vindas")
        ids = [i["routine_id"] for i in w["items"]]
        extra = self.routine()
        a.call("POST", f"/api/v1/processes/{w['id']}/items", {"routine_id": extra})  # integrate
        a.call("PUT", f"/api/v1/processes/{w['id']}", {"name": "Boas-vindas", "items": [{"routine_id": x, "continue_next": True} for x in ids]})
        sid, r, hb = self.ready_station()
        s = a.call("POST", "/api/v1/schedules", {"process_id": w["id"], "station_id": sid, "weekdays": [1], "hour": 4, "minute": 0,
                                                 "timezone": "America/Sao_Paulo"})
        a.call("DELETE", f"/api/v1/schedules/{s['id']}")
        q = a.call("POST", f"/api/v1/processes/{w['id']}/step1", {"routine_id": extra})  # replace step 1 (request)
        a.call("POST", f"/api/v1/step-changes/{q['id']}/cancel")
        self.assertTrue(self.delete(w["id"])["archived"])
        self.assertFalse(any(p["system_key"] == "boas-vindas" for p in self.processes().values()))
        self.h.core.ensure_welcome_process()  # what every start of the Core does
        Core(self.h.database, {}).ensure_welcome_process()
        self.h.stop()
        self.info = type(self).info = self.h.start(lan_port=self.port, bind="127.0.0.1")
        self.assertFalse(any(p["system_key"] == "boas-vindas" for p in self.processes().values()), "deleted stays deleted")
        with self.su() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM processes WHERE system_key = 'boas-vindas'").fetchone()[0], 1)
        rs = self.routines()
        self.assertTrue(all(x in rs for x in ids), "its routines stay, standalone")
        # Its routines are standalone now and keep their rule: they run only inside a process (not isolated).
        self.expect("ROUTINE-NOT-ISOLATED", lambda: a.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid,
                                                                                           "routine_id": ids[0]}), 409)
        # They can be composed again into a new process (the editor accepts their kind).
        new = a.call("POST", "/api/v1/processes", {"name": "Boas-vindas", "items": [{"routine_id": x, "continue_next": True} for x in ids]})
        self.assertNotEqual(new["id"], w["id"])
        self.assertIsNone(new["system_key"])

    # ---------------------------------------------------------------- identity of homonyms (the scenario of item 2)
    def test_09_a_new_process_of_the_same_name_inherits_nothing(self):
        a = self.admin()
        sid, r, hb = self.ready_station()
        name = f"X-{uuid.uuid4().hex[:6]}"
        A, (exclusive, shared) = self.process(name, steps=2)
        B, (b1,) = self.process()
        a.call("PUT", f"/api/v1/processes/{B}", {"name": "B", "items": [{"routine_id": b1, "continue_next": True}, {"routine_id": shared, "continue_next": True}]})
        old = self.execution(A, "2 hours", sid)
        with self.su() as c:
            c.execute("UPDATE schedules SET enabled = false, next_run_at = NULL, next_slot_local = NULL")
        s = a.call("POST", "/api/v1/schedules", {"process_id": A, "station_id": sid, "weekdays": [1], "hour": 5, "minute": 0, "timezone": "America/Sao_Paulo"})
        self.delete(A)
        C = a.call("POST", "/api/v1/processes", {"name": name, "items": []})
        self.assertNotEqual(C["id"], A)
        self.assertEqual((C["items"], C["last_execution"], C["last_success_at"], C["pending_change"]), ([], None, None, None))
        self.assertNotIn(s["id"], [x["id"] for x in a.call("GET", "/api/v1/schedules")])
        self.assertEqual([i["routine_id"] for i in self.processes()[B]["items"]], [b1, shared])
        self.assertFalse(any(i["routine_id"] == exclusive for p in self.processes().values() for i in p["items"]))
        e = a.call("GET", f"/api/v1/executions/{old}")
        self.assertEqual((e["process_id"], e["process_name"], e["process_archived"]), (A, name, True))
        a.call("PUT", f"/api/v1/processes/{C['id']}", {"name": "Y renomeado", "items": []})
        e = a.call("GET", f"/api/v1/executions/{old}")
        self.assertEqual((e["process_id"], e["process_name"]), (A, name), "renaming C never renames A's history")
        self.assertIn(old, [x["id"] for x in a.call("GET", "/api/v1/executions?days=1")])
        # A late request for A never reaches C.
        self.assertTrue(self.delete(A)["already"])
        self.expect("NOT-FOUND", lambda: a.call("PUT", f"/api/v1/processes/{A}", {"name": name, "items": []}), 404)
        self.expect("NOT-FOUND", lambda: a.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": A}), 404)
        self.assertEqual(self.processes()[C["id"]]["name"], "Y renomeado")
        # After a restart, the same answers.
        self.h.stop()
        self.info = type(self).info = self.h.start(lan_port=self.port, bind="127.0.0.1")
        e = a.call("GET", f"/api/v1/executions/{old}")
        self.assertEqual((e["process_id"], e["process_name"], e["process_archived"]), (A, name, True))
        self.assertNotIn(A, self.processes())
        self.assertEqual(self.processes()[C["id"]]["items"], [])

    # ---------------------------------------------------------------- concurrency
    def test_10_a_start_and_a_deletion_at_once_never_both_win(self):
        sid, r, hb = self.ready_station()
        outcomes = set()
        for _ in range(12):
            pid, _ = self.process()
            res = {}
            go = threading.Barrier(2)

            def start():
                go.wait()
                try:
                    res["start"] = self.admin().call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": pid})["id"]
                except test_core.CoreError as e:
                    res["start"] = e.diagnostic.error_code

            def delete():
                go.wait()
                try:
                    res["delete"] = self.delete(pid)["archived"]
                except test_core.CoreError as e:
                    res["delete"] = e.diagnostic.error_code

            ts = [threading.Thread(target=start), threading.Thread(target=delete)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            started = res["start"] not in ("NOT-FOUND",)
            if started:
                self.assertEqual(res["delete"], "PROCESS-BUSY", res)
                self.assertIn(pid, self.processes())
                with self.su() as c:
                    c.execute("UPDATE jobs SET state = 'cancelled', finished_at = now() WHERE execution_id = %s", (res["start"],))
                    c.execute("UPDATE executions SET state = 'finished', outcome = 'cancelled', finished_at = now() WHERE id = %s", (res["start"],))
            else:
                self.assertIs(res["delete"], True, res)
                with self.su() as c:
                    self.assertEqual(c.execute("SELECT count(*) FROM executions WHERE process_id = %s", (pid,)).fetchone()[0], 0)
            outcomes.add("start" if started else "delete")
        self.assertTrue(outcomes)  # each pair has exactly one winner (which one depends on timing)

    def test_11_a_composition_or_an_approval_at_the_same_time_is_never_partial(self):
        a = self.admin()
        for _ in range(8):
            pid, (r1, r2) = self.process(steps=2)
            new = self.routine()
            q = a.call("POST", f"/api/v1/processes/{pid}/step1", {"routine_id": new})
            res = {}
            go = threading.Barrier(3)

            def edit():
                go.wait()
                try:
                    self.admin().call("PUT", f"/api/v1/processes/{pid}", {"name": "n", "items": [{"routine_id": r1, "continue_next": True}]})
                    res["edit"] = "ok"
                except test_core.CoreError as e:
                    res["edit"] = e.diagnostic.error_code

            def approve():
                go.wait()
                try:
                    self.admin().call("POST", f"/api/v1/step-changes/{q['id']}/approve")
                    res["approve"] = "ok"
                except test_core.CoreError as e:
                    res["approve"] = e.diagnostic.error_code

            def delete():
                go.wait()
                res["delete"] = self.delete(pid)["archived"]

            ts = [threading.Thread(target=f) for f in (edit, approve, delete)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            self.assertIs(res["delete"], True)
            with self.su() as c:
                self.assertEqual(c.execute("SELECT count(*) FROM process_items WHERE process_id = %s", (pid,)).fetchone()[0], 0, res)
                self.assertTrue(c.execute("SELECT archived FROM processes WHERE id = %s", (pid,)).fetchone()[0])
                self.assertEqual(c.execute("SELECT count(*) FROM routines WHERE id = ANY(%s) AND archived", ([r1, r2, new],)).fetchone()[0], 0)
                self.assertNotEqual(c.execute("SELECT status FROM step_change_requests WHERE id = %s", (q["id"],)).fetchone()[0], "pending")

    # ---------------------------------------------------------------- Kanban of one day (item 4.3)
    def board(self, day=None):
        return self.admin().call("GET", "/api/v1/kanban" + (f"?day={day}" if day else ""))

    def test_12_today_by_default_and_a_day_is_local_midnight_to_midnight(self):
        self.h.core.team_tz = "America/New_York"
        b = self.board()
        self.assertEqual((b["timezone"], b["day"]), ("America/New_York", b["today"]))
        self.assertEqual(b["today"], datetime.now(timezone.utc).astimezone(__import__("zoneinfo").ZoneInfo("America/New_York")).date().isoformat())
        # 2026-03-08: the clocks go forward, a day of 23 hours.
        utc = timezone.utc
        span = lambda d: (datetime.fromisoformat(d["since"]), datetime.fromisoformat(d["until"]))  # noqa: E731
        self.assertEqual(span(self.board("2026-03-08")), (datetime(2026, 3, 8, 5, tzinfo=utc), datetime(2026, 3, 9, 4, tzinfo=utc)))
        # back again on 2026-11-01: 25 hours
        self.assertEqual(span(self.board("2026-11-01")), (datetime(2026, 11, 1, 4, tzinfo=utc), datetime(2026, 11, 2, 5, tzinfo=utc)))
        for bad in ("2026-13-01", "ontem", "2026-3-8", "2026-02-30"):
            self.expect("VALIDATION", lambda: self.board(bad), 400)

    def test_13_one_card_per_process_started_that_day_latest_of_the_day_not_the_global_latest(self):
        self.h.core.team_tz = "America/New_York"
        sid, r, hb = self.ready_station()
        utc = timezone.utc
        p, _ = self.process()
        yesterday_ok = self.execution(p, datetime(2026, 3, 7, 15, tzinfo=utc), sid, outcome="verified")
        today_fail = self.execution(p, datetime(2026, 3, 8, 14, tzinfo=utc), sid, outcome="failed")
        today_late = self.execution(p, datetime(2026, 3, 8, 20, tzinfo=utc), sid, outcome="completed_unverified")
        self.execution(p, datetime(2026, 3, 10, 12, tzinfo=utc), sid)  # a later day: never on the 8th
        edge, _ = self.process()
        before = self.execution(edge, datetime(2026, 3, 8, 4, 59, 59, tzinfo=utc), sid)  # 23:59:59 on the 7th, local
        first = self.execution(edge, datetime(2026, 3, 8, 5, 0, tzinfo=utc), sid)  # 00:00 on the 8th
        night, _ = self.process()
        crossing = self.execution(night, datetime(2026, 3, 9, 3, 59, 59, tzinfo=utc), sid, state="running", outcome=None)  # 23:59:59
        after, _ = self.process()
        nextday = self.execution(after, datetime(2026, 3, 9, 4, 0, tzinfo=utc), sid)  # 00:00 on the 9th
        cards = {e["process_id"]: e["id"] for e in self.board("2026-03-08")["executions"]}
        self.assertEqual(cards.get(p), today_late, "the latest of the day")
        self.assertEqual(cards.get(edge), first)
        self.assertEqual(cards.get(night), crossing, "started that day, still running after midnight")
        self.assertNotIn(after, cards)
        self.assertEqual({e["process_id"]: e["id"] for e in self.board("2026-03-07")["executions"]}.get(p), yesterday_ok)
        nine = {e["process_id"]: e for e in self.board("2026-03-09")["executions"]}
        self.assertNotIn(night, nine, "a crossing execution is not repeated on the next day")
        self.assertEqual(nine[after]["id"], nextday)
        self.assertNotIn(p, nine, "no card inherited from another day")
        self.assertEqual(self.board("2026-01-01")["executions"], [], "a day without executions is empty")
        self.assertNotIn(before, [e["id"] for e in self.board("2026-03-08")["executions"]])
        with self.su() as c:  # a tie of start times goes to the id
            same = datetime(2026, 4, 2, 15, tzinfo=utc)
            ids = sorted([self.execution(p, same, sid) for _ in range(3)])
        self.assertEqual({e["process_id"]: e["id"] for e in self.board("2026-04-02")["executions"]}[p], ids[-1])
        self.assertNotIn(today_fail, [e["id"] for e in self.board("2026-03-08")["executions"]])

    def test_14_deleted_processes_keep_their_day_homonyms_are_separate_routines_are_not_cards(self):
        self.h.core.team_tz = "America/Sao_Paulo"
        a = self.admin()
        sid, r, hb = self.ready_station()
        name = f"H-{uuid.uuid4().hex[:6]}"
        old, _ = self.process(name)
        e_old = self.execution(old, "3 minutes", sid, outcome="failed")
        self.delete(old)
        new, _ = self.process(name)
        e_new = self.execution(new, "1 minute", sid)
        rid = a.call("POST", "/api/v1/routines", {"name": "solta", "category": "windows", "version": {"kind": "app_open", "config": CALC}})["routine"]["id"]
        with self.su() as c:
            c.execute("""INSERT INTO executions (request_id, process_id, station_id, requested_by, snapshot, state, outcome, correlation_id)
                         VALUES (%s, NULL, %s, %s, '[]', 'finished', 'verified', 'c')""", (uuid.uuid4().hex, sid, self.admin_id))
        today = self.board()
        by = {e["process_id"]: e for e in today["executions"]}
        self.assertEqual((by[old]["id"], by[old]["process_name"], by[old]["process_archived"]), (e_old, name, True))
        self.assertEqual((by[new]["id"], by[new]["process_name"], by[new]["process_archived"]), (e_new, name, False))
        self.assertTrue(all(e["process_id"] is not None for e in today["executions"]), "standalone routines are not cards")
        self.assertGreater(len(rid.__str__()), 0)
        op = self.operator()
        self.assertEqual({e["id"] for e in op.call("GET", "/api/v1/kanban")["executions"]}, {e["id"] for e in today["executions"]})

    def test_15_the_server_zone_is_the_database_time_zone(self):
        with self.su() as c:
            tz = c.execute("SELECT current_setting('TimeZone')").fetchone()[0]
        self.assertEqual(self.board()["timezone"], tz)


if __name__ == "__main__":
    unittest.main()
