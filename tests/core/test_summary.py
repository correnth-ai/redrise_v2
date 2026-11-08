"""Execution summary for Empresa on the real Core (isolated PostgreSQL on C:, HTTPS API
with pinning): counts come from the database for the period, not from the capped
list; the period list used by the detail has the same rows. Runner calls are made by
the test as a declared simulated Runner.

    cd tests/core && <lab python> -B -m unittest test_summary
Env: RR_PG_BIN, RR_CORE_SITE (as test_core)."""

import unittest
import uuid

import test_core

CALC = {"target": {"kind": "app", "app_id": "Calc!App", "name": "Calculadora"}, "isolated": True}
GROUPS = ("running", "waiting", "attention", "verified")


def group_of(e):
    """Same rule as desktop/src/data/status.ts (tabs of Processo > Histórico)."""
    if e["state"] == "running":
        return "running"
    if e["state"] == "waiting_review":
        return "waiting"
    return "verified" if e["outcome"] == "verified" else "attention"


class SummaryTest(unittest.TestCase):
    _base = test_core.Harness
    setUpClass = classmethod(_base.setUpClass.__func__)
    tearDownClass = classmethod(_base.tearDownClass.__func__)
    client, expect, admin, station, su = _base.client, _base.expect, classmethod(_base.admin.__func__), _base.station, _base.su

    def routine(self, link=None, after=None, version=None):
        body = {"name": f"a-{uuid.uuid4().hex[:6]}", "category": "windows", "version": version or {"kind": "app_open", "config": CALC}}
        if link:
            body["link"] = {"process_id": link, **({"after_position": after} if after else {})}
        return self.admin().call("POST", "/api/v1/routines", body)["routine"]["id"]

    def process(self):
        pid = self.admin().call("POST", "/api/v1/processes", {"name": f"p-{uuid.uuid4().hex[:6]}", "items": []})["id"]
        self.routine(link=pid)
        return pid

    def start(self, sid, pid):
        return self.admin().call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": pid})["id"]

    def finish_next(self, r, hb, state):
        job = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/start", {"lease_id": job["lease_id"]})
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/result", {"lease_id": job["lease_id"], "result": {
            "schema": "redrise.job-result/1", "state": state, "verified": state == "verified", "details": {"context": {"done": True}}}})

    def test_01_counts_beyond_the_list_cap_and_period(self):
        a = self.admin()
        sid, r, hb = self.station("st-summary")
        empty = a.call("GET", "/api/v1/executions/summary")
        self.assertEqual({k: empty[k] for k in ("days", "total", *GROUPS)}, {"days": 30, "total": 0, "running": 0, "waiting": 0, "attention": 0, "verified": 0})
        self.assertLess(empty["since"], empty["until"])

        pid = self.process()
        old = self.start(sid, pid)  # moved 40 days back below: outside the period
        self.finish_next(r, hb, "verified")
        with self.su() as conn:
            conn.execute("UPDATE executions SET created_at = now() - interval '40 days' WHERE id = %s", (old,))
        ids = [self.start(sid, pid) for _ in range(103)]
        self.finish_next(r, hb, "verified")
        self.finish_next(r, hb, "verified")
        self.finish_next(r, hb, "failed")
        uid = a.call("POST", "/api/v1/users", {"username": "rev1", "display": "Rev", "password": test_core.PW, "role": "operator"})["id"]
        rpid = self.process()
        self.routine(link=rpid, after=1, version={"kind": "followup", "config": {"action": "review", "assignee_id": uid}})
        self.start(sid, rpid)
        s = a.call("GET", "/api/v1/executions/summary")
        self.assertEqual((s["total"], s["verified"], s["attention"], s["waiting"], s["running"]), (104, 2, 1, 0, 101))

        listed = a.call("GET", "/api/v1/executions")
        self.assertEqual(len(listed), 100)  # the usual list stays capped and is not a total
        period = a.call("GET", "/api/v1/executions?days=30")
        self.assertEqual(len(period), s["total"])
        self.assertNotIn(old, [e["id"] for e in period])
        self.assertTrue(set(ids) <= {e["id"] for e in period})
        self.assertEqual({g: sum(group_of(e) == g for e in period) for g in GROUPS}, {g: s[g] for g in GROUPS})
        self.assertEqual(a.call("GET", "/api/v1/executions/summary?days=60")["total"], 105)

    def test_02_waiting_review_and_live_change(self):
        a = self.admin()
        sid, r, hb = self.station("st-review")
        before = a.call("GET", "/api/v1/executions/summary")
        uid = next(u["id"] for u in a.call("GET", "/api/v1/users") if u["username"] == "admin")
        rpid = self.process()
        self.routine(link=rpid, after=1, version={"kind": "followup", "config": {"action": "review", "assignee_id": uid}})
        self.start(sid, rpid)
        mid = a.call("GET", "/api/v1/executions/summary")
        self.assertEqual((mid["total"] - before["total"], mid["running"] - before["running"]), (1, 1))
        self.finish_next(r, hb, "verified")  # step 1 done: the review pauses the execution
        after = a.call("GET", "/api/v1/executions/summary")
        self.assertEqual((after["waiting"] - before["waiting"], after["running"] - before["running"]), (1, 0))

    def test_03_validation_and_access(self):
        a = self.admin()
        for bad in ("0", "abc", "400", "-1"):
            self.expect("VALIDATION", lambda: a.call("GET", f"/api/v1/executions/summary?days={bad}"), 400)
            self.expect("VALIDATION", lambda: a.call("GET", f"/api/v1/executions?days={bad}"), 400)
        self.expect("AUTH-REQUIRED", lambda: self.client().call("GET", "/api/v1/executions/summary"), 401)
        _, r, _ = self.station("st-access")
        self.expect("AUTH-REQUIRED", lambda: r.call("GET", "/api/v1/executions/summary"), 401)
        a.call("POST", "/api/v1/users", {"username": "oper9", "display": "Op", "password": test_core.PW, "role": "operator"})
        op = self.client(self.client().call("POST", "/api/v1/login", {"username": "oper9", "password": test_core.PW})["token"])
        self.assertEqual(op.call("GET", "/api/v1/executions/summary")["total"], a.call("GET", "/api/v1/executions/summary")["total"])


if __name__ == "__main__":
    unittest.main()
