"""Follow-up with review on the real Core (isolated PostgreSQL on C:, HTTPS API with
pinning): position of the step, pause, approval by the current responsible only,
single resumption, reassignment with concurrency, notifications. Runner calls are
made by the test as a declared simulated Runner.

    cd tests/core && <lab python> -B -m unittest test_review
Env: RR_PG_BIN, RR_CORE_SITE (as test_core)."""

import threading
import unittest
import uuid

import test_core
from test_core import Harness

CALC = {"target": {"kind": "app", "app_id": "Calc!App", "name": "Calculadora"}, "isolated": True}


class ReviewTest(unittest.TestCase):
    setUpClass = classmethod(Harness.setUpClass.__func__)
    tearDownClass = classmethod(Harness.tearDownClass.__func__)
    client, expect, admin, station = Harness.client, Harness.expect, classmethod(Harness.admin.__func__), Harness.station

    # ---------------------------------------------------------------- helpers
    def member(self, name):
        a = self.admin()
        u = a.call("POST", "/api/v1/users", {"username": name, "display": name.capitalize(), "password": test_core.PW, "role": "operator"})
        return u["id"], self.client(self.client().call("POST", "/api/v1/login", {"username": name, "password": test_core.PW})["token"])

    def app_routine(self, link=None, name=None):
        body = {"name": name or f"a-{uuid.uuid4().hex[:6]}", "category": "windows", "version": {"kind": "app_open", "config": CALC}}
        if link:
            body["link"] = {"process_id": link}
        return self.admin().call("POST", "/api/v1/routines", body)["routine"]["id"]

    def review_step(self, process_id, after, assignee, name=None):
        return self.admin().call("POST", "/api/v1/routines", {
            "name": name or f"r-{uuid.uuid4().hex[:6]}", "category": "windows",
            "version": {"kind": "followup", "config": {"action": "review", "assignee_id": assignee}},
            "link": {"process_id": process_id, "after_position": after}})["routine"]["id"]

    def process(self, name=None):
        p = self.admin().call("POST", "/api/v1/processes", {"name": name or f"p-{uuid.uuid4().hex[:6]}", "items": []})
        return p["id"], self.app_routine(link=p["id"])

    def start(self, sid, process_id):
        return self.admin().call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": process_id})["id"]

    def run_step(self, r, hb, context=None):
        job = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        self.assertIsNotNone(job, "a step should be queued")
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/start", {"lease_id": job["lease_id"]})
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/result", {"lease_id": job["lease_id"], "result": {
            "schema": "redrise.job-result/1", "state": "verified", "verified": True, "details": {"context": context or {"done": True}}}})
        return job

    def execution(self, eid):
        return self.admin().call("GET", f"/api/v1/executions/{eid}")

    def pending_of(self, user, eid):
        return next(q for q in user.call("GET", "/api/v1/reviews") if q["execution_id"] == eid)

    # ---------------------------------------------------------------- tests
    def test_01_follow_up_goes_after_the_chosen_step(self):
        uid, _ = self.member("ana")
        pid, first = self.process()
        last = self.app_routine()
        self.admin().call("POST", f"/api/v1/processes/{pid}/items", {"routine_id": last})
        rv = self.review_step(pid, 1, uid)
        items = self.admin().call("GET", f"/api/v1/processes/{pid}")["items"]
        self.assertEqual([(i["position"], i["routine_id"], i["continue_next"]) for i in items], [(1, first, True), (2, rv, True), (3, last, True)])
        self.expect("VALIDATION", lambda: self.review_step(pid, 9, uid), 400)
        self.expect("VALIDATION", lambda: self.review_step(pid, 1, 999999), 400)  # only an active member
        self.expect("VALIDATION", lambda: self.admin().call("POST", "/api/v1/routines", {"name": "x", "category": "windows", "version": {"kind": "followup", "config": {"action": "review", "assignee_id": uid}}}), 400)
        self.expect("VALIDATION", lambda: self.admin().call("PUT", f"/api/v1/processes/{pid}", {"name": "x", "items": [{"routine_id": rv, "continue_next": True}]}), 400)
        ready_made = next(x for x in self.admin().call("GET", "/api/v1/processes") if x["system_key"])
        self.expect("VALIDATION", lambda: self.review_step(ready_made["id"], 1, uid), 400)
        row = next(r for r in self.admin().call("GET", "/api/v1/routines") if r["id"] == rv)
        self.assertEqual((row["kind"], row["assignee_name"]), ("followup", "Ana"))

    def test_02_pause_approval_and_single_resumption(self):
        sid, r, hb = self.station("rv-flow")
        uid, ana = self.member("bia")
        _, other = self.member("caio")
        pid, _ = self.process("Com revisao")
        self.review_step(pid, 1, uid)
        tail = self.app_routine()
        self.admin().call("POST", f"/api/v1/processes/{pid}/items", {"routine_id": tail})
        eid = self.start(sid, pid)
        self.run_step(r, hb, {"file": "a.txt"})
        e = self.execution(eid)
        self.assertEqual((e["state"], e["steps"][1]["state"], e["steps"][1]["review"]["assignee_name"]), ("waiting_review", "awaiting_review", "Bia"))
        self.assertIsNone(r.call("POST", "/api/v1/runner/claim", hb)["job"])  # nothing runs while paused
        n = ana.call("GET", "/api/v1/notifications")
        self.assertEqual(n["unseen"], 1)
        self.assertEqual((n["items"][0]["process_name"], n["items"][0]["position"]), ("Com revisao", 2))
        q = self.pending_of(ana, eid)
        self.assertEqual((q["status"], q["context"]["last"]), ("pending", {"file": "a.txt"}))
        # Opening is a separate thing: seen, not approved.
        ana.call("POST", f"/api/v1/notifications/{n['items'][0]['id']}/seen")
        self.assertEqual(ana.call("GET", "/api/v1/notifications")["unseen"], 0)
        self.assertEqual(self.execution(eid)["state"], "waiting_review")
        self.expect("NOT-FOUND", lambda: other.call("POST", f"/api/v1/notifications/{n['items'][0]['id']}/seen"), 404)
        # Only the responsible; an administrator is not one by being an administrator.
        self.expect("REVIEW-NOT-ASSIGNEE", lambda: other.call("POST", f"/api/v1/reviews/{q['id']}/approve"), 403)
        self.expect("REVIEW-NOT-ASSIGNEE", lambda: self.admin().call("POST", f"/api/v1/reviews/{q['id']}/approve"), 403)
        done = ana.call("POST", f"/api/v1/reviews/{q['id']}/approve")
        self.assertEqual((done["status"], done["decided_by_name"]), ("approved", "Bia"))
        self.assertTrue(done["decided_at"])
        self.expect("REVIEW-ALREADY-DECIDED", lambda: ana.call("POST", f"/api/v1/reviews/{q['id']}/approve"), 409)
        e = self.execution(eid)
        self.assertEqual((e["state"], e["steps"][1]["state"], e["steps"][1]["verified"]), ("running", "verified", True))
        job = self.run_step(r, hb)
        self.assertEqual((job["position"], job["context"]["last"]), (3, {"file": "a.txt"}))  # the same execution, its context
        e = self.execution(eid)
        self.assertEqual((e["state"], e["outcome"], e["end_reason"]), ("finished", "verified", "sequence_end"))
        self.assertIsNone(r.call("POST", "/api/v1/runner/claim", hb)["job"])

    def test_03_review_as_last_step_finishes_verified(self):
        sid, r, hb = self.station("rv-last")
        uid, u = self.member("dora")
        pid, _ = self.process()
        self.review_step(pid, 1, uid)
        eid = self.start(sid, pid)
        self.run_step(r, hb)
        u.call("POST", f"/api/v1/reviews/{self.pending_of(u, eid)['id']}/approve")
        e = self.execution(eid)
        self.assertEqual((e["state"], e["outcome"], e["end_reason"]), ("finished", "verified", "sequence_end"))

    def test_04_failed_step_opens_no_review(self):
        sid, r, hb = self.station("rv-fail")
        uid, u = self.member("edu")
        pid, _ = self.process()
        self.review_step(pid, 1, uid)
        eid = self.start(sid, pid)
        job = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/start", {"lease_id": job["lease_id"]})
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/result", {"lease_id": job["lease_id"], "result": {"schema": "redrise.job-result/1", "state": "failed", "verified": False}})
        self.assertEqual(self.execution(eid)["state"], "finished")
        self.assertFalse([q for q in u.call("GET", "/api/v1/reviews") if q["execution_id"] == eid])

    def test_05_reassignment_moves_pending_and_keeps_decided(self):
        sid, r, hb = self.station("rv-move")
        a_id, a = self.member("fabi")
        b_id, b = self.member("gil")
        pid, _ = self.process()
        rv = self.review_step(pid, 1, a_id)
        done = self.start(sid, pid)
        self.run_step(r, hb)
        a.call("POST", f"/api/v1/reviews/{self.pending_of(a, done)['id']}/approve")
        open_ = self.start(sid, pid)
        self.run_step(r, hb)
        self.assertEqual(a.call("GET", "/api/v1/notifications")["unseen"], 1)
        self.admin().call("POST", f"/api/v1/routines/{rv}/versions", {"kind": "followup", "config": {"action": "review", "assignee_id": b_id}})
        moved = self.pending_of(b, open_)
        self.assertEqual((moved["status"], moved["assignee_name"]), ("pending", "Gil"))
        self.assertEqual(b.call("GET", "/api/v1/notifications")["unseen"], 1)
        self.assertEqual(a.call("GET", "/api/v1/notifications")["unseen"], 0)
        self.assertFalse([q for q in a.call("GET", "/api/v1/reviews") if q["execution_id"] == open_])
        self.expect("REVIEW-NOT-ASSIGNEE", lambda: a.call("POST", f"/api/v1/reviews/{moved['id']}/approve"), 403)
        # Concluded keeps author and time, and stays with who decided.
        kept = self.pending_of(a, done)
        self.assertEqual((kept["status"], kept["decided_by_name"]), ("approved", "Fabi"))
        b.call("POST", f"/api/v1/reviews/{moved['id']}/approve")
        self.assertEqual(self.execution(open_)["state"], "finished")

    def test_06_step_reached_after_a_change_goes_to_the_current_responsible(self):
        sid, r, hb = self.station("rv-late")
        a_id, a = self.member("hugo")
        b_id, b = self.member("iris")
        pid, _ = self.process()
        rv = self.review_step(pid, 1, a_id)
        eid = self.start(sid, pid)  # the snapshot still has the first responsible
        self.admin().call("POST", f"/api/v1/routines/{rv}/versions", {"kind": "followup", "config": {"action": "review", "assignee_id": b_id}})
        self.run_step(r, hb)
        self.assertEqual(self.pending_of(b, eid)["assignee_name"], "Iris")
        self.assertFalse([q for q in a.call("GET", "/api/v1/reviews") if q["execution_id"] == eid])

    def test_06b_step_reached_while_the_responsible_changes_stays_with_the_new_one(self):
        sid, r, hb = self.station("rv-race2")
        a_id, a = self.member("otto")
        b_id, b = self.member("paz")
        pid, _ = self.process()
        rv = self.review_step(pid, 1, a_id)
        for _ in range(6):
            eid = self.start(sid, pid)
            ts = [threading.Thread(target=lambda: self.run_step(r, hb)),
                  threading.Thread(target=lambda: self.admin().call("POST", f"/api/v1/routines/{rv}/versions", {"kind": "followup", "config": {"action": "review", "assignee_id": b_id}}))]
            [t.start() for t in ts]
            [t.join() for t in ts]
            self.assertEqual(self.execution(eid)["state"], "waiting_review")
            q = self.pending_of(b, eid)  # never left with the previous one
            b.call("POST", f"/api/v1/reviews/{q['id']}/approve")
            self.admin().call("POST", f"/api/v1/routines/{rv}/versions", {"kind": "followup", "config": {"action": "review", "assignee_id": a_id}})

    def test_07_concurrent_approvals_give_one_decision_and_one_resumption(self):
        sid, r, hb = self.station("rv-conc")
        uid, u = self.member("joao")
        pid, _ = self.process()
        self.review_step(pid, 1, uid)
        self.admin().call("POST", f"/api/v1/processes/{pid}/items", {"routine_id": self.app_routine()})
        eid = self.start(sid, pid)
        self.run_step(r, hb)
        qid = self.pending_of(u, eid)["id"]
        out = []

        def click():
            try:
                u.call("POST", f"/api/v1/reviews/{qid}/approve")
                out.append("ok")
            except test_core.CoreError as e:
                out.append(e.diagnostic.error_code)
        ts = [threading.Thread(target=click) for _ in range(5)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(sorted(out), ["REVIEW-ALREADY-DECIDED"] * 4 + ["ok"])
        self.run_step(r, hb)
        self.assertIsNone(r.call("POST", "/api/v1/runner/claim", hb)["job"])
        self.assertEqual(self.execution(eid)["state"], "finished")

    def test_08_concurrent_reassignment_and_approval_never_give_two_decisions(self):
        sid, r, hb = self.station("rv-race")
        a_id, a = self.member("kim")
        b_id, b = self.member("lia")
        pid, _ = self.process()
        rv = self.review_step(pid, 1, a_id)
        for round_ in range(6):
            owner, other, other_id = (a, b, b_id) if round_ % 2 == 0 else (b, a, a_id)
            eid = self.start(sid, pid)
            self.run_step(r, hb)
            qid = self.pending_of(owner, eid)["id"]
            result = {}

            def approve():
                try:
                    owner.call("POST", f"/api/v1/reviews/{qid}/approve")
                    result["approve"] = "ok"
                except test_core.CoreError as e:
                    result["approve"] = e.diagnostic.error_code

            def move():
                self.admin().call("POST", f"/api/v1/routines/{rv}/versions", {"kind": "followup", "config": {"action": "review", "assignee_id": other_id}})
            ts = [threading.Thread(target=approve), threading.Thread(target=move)]
            [t.start() for t in ts]
            [t.join() for t in ts]
            if result["approve"] == "ok":  # approved first: the decision stays with who decided
                self.assertEqual(self.pending_of(owner, eid)["status"], "approved")
            else:  # moved first: the old responsible lost it; the new one decides, once
                self.assertEqual(result["approve"], "REVIEW-NOT-ASSIGNEE")
                other.call("POST", f"/api/v1/reviews/{qid}/approve")
            self.expect("REVIEW-ALREADY-DECIDED", lambda: other.call("POST", f"/api/v1/reviews/{qid}/approve"), 409)
            self.assertEqual(self.execution(eid)["state"], "finished")
            self.assertIsNone(r.call("POST", "/api/v1/runner/claim", hb)["job"])
            rows = self.su_rows(eid)
            self.assertEqual(len(rows), 1)

    def su_rows(self, eid):
        with Harness.su(self) as c:
            with c.cursor() as cur:
                cur.execute("SELECT status, decided_by FROM review_requests WHERE execution_id = %s", (eid,))
                return cur.fetchall()

    def test_09_station_revoked_during_the_pause_ends_the_execution(self):
        sid, r, hb = self.station("rv-revoke")
        uid, u = self.member("mel")
        pid, _ = self.process()
        self.review_step(pid, 1, uid)
        self.admin().call("POST", f"/api/v1/processes/{pid}/items", {"routine_id": self.app_routine()})
        eid = self.start(sid, pid)
        self.run_step(r, hb)
        self.admin().call("DELETE", f"/api/v1/stations/{sid}")
        u.call("POST", f"/api/v1/reviews/{self.pending_of(u, eid)['id']}/approve")
        e = self.execution(eid)
        self.assertEqual((e["state"], e["outcome"]), ("finished", "refused"))

    def test_10_browser_only_station_can_run_a_process_with_review_of_browser_steps(self):
        sid, r, hb = self.station("rv-browser", categories=("browser",))
        uid, _ = self.member("nina")
        p = self.admin().call("POST", "/api/v1/processes", {"name": "So navegador", "items": []})
        self.admin().call("POST", "/api/v1/routines", {"name": "Abrir site", "category": "browser", "link": {"process_id": p["id"]}, "version": {"kind": "browser_open", "config": {
            "origin": "site", "browser": "msedge", "url": "https://x.exemplo.test/", "path": None, "isolated": True}}})
        self.review_step(p["id"], 1, uid)
        self.assertTrue(self.start(sid, p["id"]))


if __name__ == "__main__":
    unittest.main()
