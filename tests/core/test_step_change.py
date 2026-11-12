"""Replacing step 1 of a process on the real Core (isolated PostgreSQL on C:, HTTPS API
with pinning): only out of execution, only with approval of an eligible member,
applied once, apart from the review that pauses an execution. Runner calls are made
by the test as a declared simulated Runner.

    cd tests/core && <lab python> -B -m unittest test_step_change
Env: RR_PG_BIN, RR_CORE_SITE (as test_core)."""

import threading
import unittest
import uuid

import test_core
from test_core import Harness

CALC = {"target": {"kind": "app", "app_id": "Calc!App", "name": "Calculadora"}, "isolated": True}


class StepChangeTest(unittest.TestCase):
    setUpClass = classmethod(Harness.setUpClass.__func__)
    tearDownClass = classmethod(Harness.tearDownClass.__func__)
    client, expect, admin, station = Harness.client, Harness.expect, classmethod(Harness.admin.__func__), Harness.station

    def login(self, name, role="operator"):
        cls = type(self)
        cls._users = vars(cls).get("_users", {})
        if name not in cls._users:
            u = self.admin().call("POST", "/api/v1/users", {"username": name, "display": name.capitalize(), "password": test_core.PW, "role": role})
            cls._users[name] = (u["id"], self.client().call("POST", "/api/v1/login", {"username": name, "password": test_core.PW})["token"])
        uid, tok = cls._users[name]
        return uid, self.client(tok)

    def routine(self, link=None):
        body = {"name": f"a-{uuid.uuid4().hex[:6]}", "category": "windows", "version": {"kind": "app_open", "config": CALC}}
        if link:
            body["link"] = {"process_id": link}
        return self.admin().call("POST", "/api/v1/routines", body)["routine"]["id"]

    def process(self):
        p = self.admin().call("POST", "/api/v1/processes", {"name": f"p-{uuid.uuid4().hex[:6]}", "items": []})
        return p["id"], self.routine(link=p["id"])

    def first(self, pid):
        return next(i["routine_id"] for i in self.admin().call("GET", f"/api/v1/processes/{pid}")["items"] if i["position"] == 1)

    def run_one(self, r, hb):
        job = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/start", {"lease_id": job["lease_id"]})
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/result", {"lease_id": job["lease_id"], "result": {"schema": "redrise.job-result/1", "state": "verified", "verified": True}})

    def test_01_composition_cannot_put_another_routine_ahead_of_step_1(self):
        a = self.admin()
        pid, one = self.process()
        two, three = self.routine(), self.routine()
        put = lambda ids: a.call("PUT", f"/api/v1/processes/{pid}", {"name": "x", "items": [{"routine_id": r, "continue_next": True} for r in ids]})
        self.expect("STEP1-NEEDS-APPROVAL", lambda: put([two, one]), 409)  # step 1 stays but is no longer first
        self.expect("STEP1-NEEDS-APPROVAL", lambda: put([three, one, two]), 409)
        put([one, three])  # the rest can change
        self.assertEqual(self.first(pid), one)
        # TEAM-ACCOUNTS-20261108 item 5 (user order, 2026-11-08): removing step 1 needs no approval; the next one starts.
        put([three])
        self.assertEqual(self.first(pid), three)

    def test_02_approval_applies_once_and_old_routine_becomes_standalone(self):
        a = self.admin()
        _, other = self.login("sc-admin", "admin")
        pid, one = self.process()
        new = self.routine()
        q = a.call("POST", f"/api/v1/processes/{pid}/step1", {"routine_id": new})
        self.assertEqual((q["status"], self.first(pid)), ("pending", one))  # nothing changes before the approval
        self.assertEqual(a.call("GET", f"/api/v1/processes/{pid}")["pending_change"], q["id"])
        self.expect("CHANGE-PENDING-EXISTS", lambda: a.call("POST", f"/api/v1/processes/{pid}/step1", {"routine_id": self.routine()}), 409)
        n = other.call("GET", "/api/v1/notifications")
        self.assertIn(q["id"], [x["change_id"] for x in n["items"] if x["seen_at"] is None])
        self.assertTrue(next(x for x in other.call("GET", "/api/v1/step-changes") if x["id"] == q["id"])["can_approve"])
        self.expect("CHANGE-NOT-ELIGIBLE", lambda: a.call("POST", f"/api/v1/step-changes/{q['id']}/approve"), 403)  # not who asked
        done = other.call("POST", f"/api/v1/step-changes/{q['id']}/approve")
        self.assertEqual((done["status"], done["decided_by_name"], self.first(pid)), ("approved", "Sc-admin", new))
        self.assertTrue(done["decided_at"])
        self.assertIsNone(a.call("GET", f"/api/v1/processes/{pid}")["pending_change"])
        self.expect("CHANGE-ALREADY-DECIDED", lambda: other.call("POST", f"/api/v1/step-changes/{q['id']}/approve"), 409)
        sid, _, _ = self.station("sc-free")
        self.assertTrue(a.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "routine_id": one})["id"])  # the old one runs alone now

    def test_03_only_out_of_execution_both_at_request_and_at_approval(self):
        a = self.admin()
        _, other = self.login("sc-admin", "admin")
        sid, r, hb = self.station("sc-run")
        pid, _ = self.process()
        eid = a.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": pid})["id"]
        new = self.routine()
        e = self.expect("PROCESS-RUNNING", lambda: a.call("POST", f"/api/v1/processes/{pid}/step1", {"routine_id": new}), 409)
        self.assertTrue(e.diagnostic.params["process"])
        self.run_one(r, hb)
        self.assertEqual(a.call("GET", f"/api/v1/executions/{eid}")["state"], "finished")
        q = a.call("POST", f"/api/v1/processes/{pid}/step1", {"routine_id": new})
        a.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": pid})
        self.expect("PROCESS-RUNNING", lambda: other.call("POST", f"/api/v1/step-changes/{q['id']}/approve"), 409)
        self.assertEqual(next(x for x in other.call("GET", "/api/v1/step-changes") if x["id"] == q["id"])["status"], "pending")  # it can still be approved later
        self.run_one(r, hb)
        self.assertEqual(other.call("POST", f"/api/v1/step-changes/{q['id']}/approve")["status"], "approved")

    def test_04_paused_execution_also_counts_as_running(self):
        a = self.admin()
        reviewer, rv = self.login("sc-rev")
        sid, r, hb = self.station("sc-pause")
        pid, _ = self.process()
        a.call("POST", "/api/v1/routines", {"name": "rev", "category": "windows", "version": {"kind": "followup", "config": {"action": "review", "assignee_id": reviewer}},
                                            "link": {"process_id": pid, "after_position": 1}})
        a.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": pid})
        self.run_one(r, hb)
        self.expect("PROCESS-RUNNING", lambda: a.call("POST", f"/api/v1/processes/{pid}/step1", {"routine_id": self.routine()}), 409)
        rv.call("POST", f"/api/v1/reviews/{rv.call('GET', '/api/v1/reviews')[0]['id']}/approve")

    def test_05_eligibility(self):
        a = self.admin()
        linked_id, linked = self.login("sc-linked")
        _, outsider = self.login("sc-out")
        pid, _ = self.process()
        a.call("POST", "/api/v1/routines", {"name": "rev2", "category": "windows", "version": {"kind": "followup", "config": {"action": "review", "assignee_id": linked_id}},
                                            "link": {"process_id": pid, "after_position": 1}})
        q = a.call("POST", f"/api/v1/processes/{pid}/step1", {"routine_id": self.routine()})
        self.expect("CHANGE-NOT-ELIGIBLE", lambda: outsider.call("POST", f"/api/v1/step-changes/{q['id']}/approve"), 403)
        self.assertNotIn(q["id"], [x["id"] for x in outsider.call("GET", "/api/v1/step-changes")])
        self.expect("AUTH-FORBIDDEN", lambda: outsider.call("POST", f"/api/v1/processes/{pid}/step1", {"routine_id": self.routine()}), 403)
        self.assertEqual(linked.call("POST", f"/api/v1/step-changes/{q['id']}/approve")["decided_by_name"], "Sc-linked")  # the responsible of a review step

    def test_06_cancel_and_conditions(self):
        a = self.admin()
        pid, _ = self.process()
        new = self.routine()
        q = a.call("POST", f"/api/v1/processes/{pid}/step1", {"routine_id": new})
        c = a.call("POST", f"/api/v1/step-changes/{q['id']}/cancel")
        self.assertEqual(c["status"], "cancelled")
        self.expect("CHANGE-ALREADY-DECIDED", lambda: a.call("POST", f"/api/v1/step-changes/{q['id']}/approve"), 409)
        empty = a.call("POST", "/api/v1/processes", {"name": "vazio-sc", "items": []})
        self.expect("VALIDATION", lambda: a.call("POST", f"/api/v1/processes/{empty['id']}/step1", {"routine_id": new}), 400)
        other, in_use = self.process()
        self.expect("CONFLICT", lambda: a.call("POST", f"/api/v1/processes/{pid}/step1", {"routine_id": in_use}), 409)
        # The ready-made process accepts a replacement request like any other (PROCESS-ACTIONS-20261111); cancelled after.
        ready_made = next(x for x in a.call("GET", "/api/v1/processes") if x["system_key"])
        q = a.call("POST", f"/api/v1/processes/{ready_made['id']}/step1", {"routine_id": new})
        self.assertEqual(q["status"], "pending")
        a.call("POST", f"/api/v1/step-changes/{q['id']}/cancel")

    def test_07_routine_taken_after_the_request_blocks_the_approval(self):
        a = self.admin()
        _, other = self.login("sc-admin", "admin")
        pid, _ = self.process()
        new = self.routine()
        q = a.call("POST", f"/api/v1/processes/{pid}/step1", {"routine_id": new})
        target = a.call("POST", "/api/v1/processes", {"name": f"t-{uuid.uuid4().hex[:6]}", "items": []})
        a.call("POST", f"/api/v1/processes/{target['id']}/items", {"routine_id": new})
        self.expect("CONFLICT", lambda: other.call("POST", f"/api/v1/step-changes/{q['id']}/approve"), 409)
        self.assertNotEqual(self.first(pid), new)

    def test_08_concurrent_approvals_and_start_are_consistent(self):
        a = self.admin()
        _, one = self.login("sc-admin", "admin")
        _, two = self.login("sc-admin2", "admin")
        sid, r, hb = self.station("sc-race")
        for _ in range(4):
            pid, old = self.process()
            new = self.routine()
            q = a.call("POST", f"/api/v1/processes/{pid}/step1", {"routine_id": new})
            out, started = [], []

            def approve(u):
                try:
                    u.call("POST", f"/api/v1/step-changes/{q['id']}/approve")
                    out.append("ok")
                except test_core.CoreError as e:
                    out.append(e.diagnostic.error_code)

            def start():
                started.append(a.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": pid})["id"])
            ts = [threading.Thread(target=approve, args=(one,)), threading.Thread(target=approve, args=(two,)), threading.Thread(target=start)]
            [t.start() for t in ts]
            [t.join() for t in ts]
            ok = out.count("ok")
            self.assertLessEqual(ok, 1)
            e = a.call("GET", f"/api/v1/executions/{started[0]}")
            if ok:  # approved first: the start sees the new step. Never a run with a step that the process just lost.
                self.assertEqual(e["steps"][0]["routine_id"], new)
                self.assertEqual(self.first(pid), new)
            else:  # started first: the approval was refused, nothing changed
                self.assertEqual(self.first(pid), old)
                self.assertEqual(e["steps"][0]["routine_id"], old)
                self.assertIn("PROCESS-RUNNING", out)
            self.run_one(r, hb)

    def test_09_team_of_one_is_not_locked_out(self):
        """Eligibility falls back to the requester only when nobody else is eligible."""
        with self.h_core() as core:
            pid, _ = self.process()
            q = self.admin().call("POST", f"/api/v1/processes/{pid}/step1", {"routine_id": self.routine()})
            with core.db.tx() as c:
                me = self.admin().call("GET", "/api/v1/me")["id"]
                c.execute("UPDATE users SET role = 'operator' WHERE id <> %s", (me,))
                self.assertEqual(core._eligible(c, pid, me), [me])
                raise test_core.psycopg.Rollback()
            self.admin().call("POST", f"/api/v1/step-changes/{q['id']}/cancel")

    def h_core(self):
        import contextlib

        @contextlib.contextmanager
        def ctx():
            yield type(self).h.core
        return ctx()


if __name__ == "__main__":
    unittest.main()
