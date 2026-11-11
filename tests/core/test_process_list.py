"""Processo › Ação, Kanban and Equipe rules of work order PROCESS-LIST-INSTALLER-20261110 on the real Core: isolated
PostgreSQL on C:, HTTPS API with pinning. The execution history is synthetic, written directly in the database (no
automation is needed to make it, per the work order).

    cd tests/core && <lab python> -B -m unittest test_process_list
Env: RR_PG_BIN, RR_CORE_SITE (as test_core)."""

import json
import unittest
import uuid

import test_core
from test_core import PW, Harness

from redrise_core import auth  # noqa: E402  (on sys.path through test_core)


class ProcessListTest(Harness, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        a = cls.admin()
        cls.station = a.call("POST", "/api/v1/stations", {"name": f"st-{uuid.uuid4().hex[:6]}"})["station"]["id"]
        cls.admin_id = a.call("GET", "/api/v1/me")["id"]

    def setUp(self):
        self.h.core.limits = auth.AttemptLimiter()

    def process(self):
        a = self.admin()
        pid = a.call("POST", "/api/v1/processes", {"name": f"p-{uuid.uuid4().hex[:6]}", "items": []})["id"]
        a.call("POST", "/api/v1/routines", {"name": f"r-{uuid.uuid4().hex[:6]}", "category": "windows", "link": {"process_id": pid},
               "version": {"kind": "app_open", "config": {"target": {"kind": "app", "app_id": "Calc!App", "name": "Calculadora"}, "isolated": True}}})
        return pid

    def execution(self, pid, created, state="finished", outcome="verified", finished=None):
        """A synthetic execution of `pid`, `created`/`finished` as SQL intervals before now()."""
        with self.su() as c:
            return str(c.execute(
                """INSERT INTO executions (request_id, process_id, station_id, requested_by, snapshot, state, outcome, correlation_id, created_at, finished_at)
                   VALUES (%s, %s, %s, %s, '[]', %s, %s, 'c', now() - %s::interval, CASE WHEN %s::text IS NULL THEN NULL ELSE now() - %s::interval END)
                   RETURNING id""",
                (uuid.uuid4().hex, pid, self.station, self.admin_id, state, outcome, created, finished, finished)).fetchone()[0])

    def finished_at(self, eid):
        with self.su() as c:
            return c.execute("SELECT finished_at FROM executions WHERE id = %s", (eid,)).fetchone()[0].isoformat()

    def listed(self, pid):
        return next(p for p in self.admin().call("GET", "/api/v1/processes") if p["id"] == pid)

    # ---------------------------------------------------------------- item 1: last success
    def test_01_last_success_survives_a_later_failure_and_is_older_than_30_days(self):
        pid = self.process()
        self.assertIsNone(self.listed(pid)["last_success_at"])  # never: null, shown as "Nunca"
        ok = self.execution(pid, "90 days", finished="89 days 23 hours")  # outside the 30-day summary
        self.execution(pid, "1 hour", outcome="failed", finished="50 minutes")
        p = self.listed(pid)
        self.assertEqual(p["last_success_at"], self.finished_at(ok))  # its end, not its creation
        self.assertEqual(p["last_execution"]["outcome"], "failed")  # the last attempt stays as it was

    def test_02_only_a_finished_verified_execution_counts(self):
        pid = self.process()
        self.execution(pid, "5 hours", state="running", outcome=None)
        self.execution(pid, "4 hours", outcome="cancelled", finished="4 hours")
        self.execution(pid, "3 hours", outcome="completed_unverified", finished="3 hours")
        self.execution(pid, "2 hours", state="waiting_review", outcome=None)
        self.assertIsNone(self.listed(pid)["last_success_at"])
        a = self.execution(pid, "10 days", finished="10 days")
        b = self.execution(pid, "2 days", finished="2 days")
        self.assertEqual(self.listed(pid)["last_success_at"], self.finished_at(b))
        self.assertNotEqual(self.finished_at(a), self.finished_at(b))

    # ---------------------------------------------------------------- item 4: the Kanban's latest execution per process
    def test_03_latest_per_process_is_not_capped_by_the_general_list(self):
        old = self.process()
        first = self.execution(old, "400 days", finished="400 days")
        latest_old = self.execution(old, "300 days", outcome="failed", finished="300 days")
        busy = self.process()
        for i in range(105):  # pushes the old process out of the general list (100 most recent)
            self.execution(busy, f"{i + 1} minutes", finished=f"{i + 1} minutes")
        a = self.admin()
        general = [e["id"] for e in a.call("GET", "/api/v1/executions")]
        self.assertEqual(len(general), 100)
        self.assertNotIn(latest_old, general)
        board = a.call("GET", "/api/v1/executions?latest=process")
        by_process = {e["process_id"]: e["id"] for e in board}
        self.assertEqual(by_process[old], latest_old)  # its newest one, whatever its age
        self.assertNotIn(first, [e["id"] for e in board])
        self.assertEqual(len([e for e in board if e["process_id"] == busy]), 1)
        self.assertTrue(all(e["process_id"] is not None for e in board))
        self.expect("VALIDATION", lambda: a.call("GET", "/api/v1/executions?latest=routine"), 400)

    def test_04_an_archived_process_leaves_the_board(self):
        pid = self.process()
        eid = self.execution(pid, "1 hour", finished="1 hour")
        with self.su() as c:
            c.execute("UPDATE processes SET archived = true WHERE id = %s", (pid,))
        self.assertNotIn(eid, [e["id"] for e in self.admin().call("GET", "/api/v1/executions?latest=process")])

    def test_05_the_board_is_visible_to_an_operator_whoever_started_it(self):
        pid = self.process()
        eid = self.execution(pid, "1 minute", state="running", outcome=None)
        name = f"op{uuid.uuid4().hex[:6]}"
        self.admin().call("POST", "/api/v1/users", {"username": name, "display": name, "password": PW, "role": "operator"})
        op = self.client(self.client().call("POST", "/api/v1/login", {"username": name, "password": PW})["token"])
        self.assertIn(eid, [e["id"] for e in op.call("GET", "/api/v1/executions?latest=process")])

    def test_06_execution_changes_reach_the_change_feed(self):
        a = self.admin()
        start = a.call("POST", "/api/v1/changes", {"epoch": None, "seq": None, "wait_s": 0})
        pid = self.process()
        eid = self.execution(pid, "1 minute", state="running", outcome=None)
        with self.su() as c:
            c.execute("UPDATE executions SET state = 'finished', outcome = 'verified', finished_at = now() WHERE id = %s", (eid,))
        out = a.call("POST", "/api/v1/changes", {"epoch": start["epoch"], "seq": start["seq"], "wait_s": 2})
        self.assertIn("executions", out["domains"])

    # ---------------------------------------------------------------- item 3: own account
    def test_07_nobody_deactivates_their_own_account_even_with_another_admin(self):
        a = self.admin()
        name = f"adm{uuid.uuid4().hex[:6]}"
        other = a.call("POST", "/api/v1/users", {"username": name, "display": name, "password": PW, "role": "admin"})
        me = self.client(self.client().call("POST", "/api/v1/login", {"username": name, "password": PW})["token"])
        self.expect("ACCOUNT-SELF-DEACTIVATE", lambda: me.call("PATCH", f"/api/v1/users/{other['id']}", {"active": False}), 409)
        self.assertTrue(next(u for u in a.call("GET", "/api/v1/users") if u["id"] == other["id"])["active"])
        me.call("PATCH", f"/api/v1/users/{other['id']}", {"active": True})  # a no-op on itself stays allowed
        # Another administrator may still deactivate it; the last active administrator stays protected.
        a.call("PATCH", f"/api/v1/users/{other['id']}", {"active": False})
        self.assertFalse(next(u for u in a.call("GET", "/api/v1/users") if u["id"] == other["id"])["active"])
        self.expect("ACCOUNT-SELF-DEACTIVATE", lambda: a.call("PATCH", f"/api/v1/users/{self.admin_id}", {"active": False}), 409)
        with self.su() as c:  # the only active admin left: the old rule answers for another actor too
            others = c.execute("SELECT count(*) FROM users WHERE role = 'admin' AND active AND id <> %s", (self.admin_id,)).fetchone()[0]
        self.assertEqual(others, 0)


if __name__ == "__main__":
    unittest.main()
