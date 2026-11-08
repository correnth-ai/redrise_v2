"""Cancel of a process step on the real Core (isolated PostgreSQL on C:, HTTPS API
with pinning). Runner calls are made by the test as a declared simulated Runner.
A cancel accepted before the next step is queued never lets that step start; the
step in course keeps its real result; no automatic retry.

    cd tests/core && <lab python> -B -m unittest test_cancel
Env: RR_PG_BIN, RR_CORE_SITE (as test_core)."""

import threading
import unittest
import uuid

import test_core

CALC = {"target": {"kind": "app", "app_id": "Calc!App", "name": "Calculadora"}, "isolated": True}
VERIFIED = {"schema": "redrise.job-result/1", "state": "verified", "verified": True, "details": {"context": {"done": True}}}


class CancelTest(unittest.TestCase):
    _base = test_core.Harness
    setUpClass = classmethod(_base.setUpClass.__func__)
    tearDownClass = classmethod(_base.tearDownClass.__func__)
    client, expect, admin, station = _base.client, _base.expect, classmethod(_base.admin.__func__), _base.station

    # ---------------------------------------------------------------- helpers
    def routine(self, link=None):
        body = {"name": f"a-{uuid.uuid4().hex[:6]}", "category": "windows", "version": {"kind": "app_open", "config": CALC}}
        if link:
            body["link"] = {"process_id": link}
        return self.admin().call("POST", "/api/v1/routines", body)["routine"]["id"]

    def two_steps(self):
        """Process of two linked routines, continuation on, started on a fresh station."""
        a = self.admin()
        pid = a.call("POST", "/api/v1/processes", {"name": f"p-{uuid.uuid4().hex[:6]}", "items": []})["id"]
        self.routine(link=pid)
        a.call("POST", f"/api/v1/processes/{pid}/items", {"routine_id": self.routine()})
        sid, r, hb = self.station(f"st-{uuid.uuid4().hex[:6]}")
        eid = a.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": pid})["id"]
        return eid, r, hb

    def execution(self, eid):
        return self.admin().call("GET", f"/api/v1/executions/{eid}")

    def first_job(self, eid):
        return self.execution(eid)["steps"][0]["job_id"]

    def cancel(self, job_id):
        return self.admin().call("POST", f"/api/v1/jobs/{job_id}/cancel")

    def claim_and_start(self, r, hb):
        job = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        self.assertIsNotNone(job)
        go = r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/start", {"lease_id": job["lease_id"]})
        self.assertTrue(go["proceed"])
        return job

    def report(self, r, job, result=VERIFIED):
        return r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/result", {"lease_id": job["lease_id"], "result": result})

    def assert_stopped_after_first(self, eid, r, hb, first_state):
        e = self.execution(eid)
        self.assertEqual((e["state"], e["outcome"], e["end_reason"]), ("finished", "cancelled", "cancelled"))
        self.assertEqual([s["state"] for s in e["steps"]], [first_state, None])  # step 2 never queued
        self.assertIsNone(r.call("POST", "/api/v1/runner/claim", hb)["job"])

    # ---------------------------------------------------------------- tests
    def test_01_cancel_while_queued(self):
        eid, r, hb = self.two_steps()
        self.assertEqual(self.cancel(self.first_job(eid)), {"state": "cancelled"})
        self.assert_stopped_after_first(eid, r, hb, "cancelled")

    def test_02_cancel_after_claim_before_start(self):
        eid, r, hb = self.two_steps()
        job = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        self.assertEqual(self.cancel(job["job_id"]), {"state": "claimed", "cancel_requested": True})
        go = r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/start", {"lease_id": job["lease_id"]})
        self.assertEqual(go, {"proceed": False, "reason": "cancelled"})
        self.assert_stopped_after_first(eid, r, hb, "cancelled")

    def test_03_cancel_while_running_then_runner_stops(self):
        eid, r, hb = self.two_steps()
        job = self.claim_and_start(r, hb)
        self.assertEqual(self.cancel(job["job_id"]), {"state": "running", "cancel_requested": True})
        self.assertIn(job["job_id"], r.call("POST", "/api/v1/runner/heartbeat", hb)["cancel"])  # propagated to the Runner
        self.report(r, job, {"schema": "redrise.job-result/1", "state": "cancelled", "verified": False, "details": {}})
        self.assert_stopped_after_first(eid, r, hb, "cancelled")

    def test_04_cancel_while_running_but_step_completes(self):
        """The Runner could not stop in time: the step's real result is kept, the next step is not started."""
        eid, r, hb = self.two_steps()
        job = self.claim_and_start(r, hb)
        self.cancel(job["job_id"])
        self.assertEqual(self.report(r, job), {"duplicate": False, "state": "verified"})
        self.assertEqual(self.report(r, job), {"duplicate": True, "state": "verified"})  # retransmitted report
        self.assert_stopped_after_first(eid, r, hb, "verified")
        e = self.execution(eid)
        self.assertTrue(e["steps"][0]["verified"])
        self.assertEqual(e["context"]["last"], {"done": True})  # effect of the step preserved, not undone
        jobs = self.admin().call("GET", f"/api/v1/jobs/{job['job_id']}")
        self.assertEqual((jobs["state"], jobs["cancel_requested"]), ("verified", True))

    def test_05_result_first_then_cancel_is_refused(self):
        """Cancel after the next step was queued is not accepted for the finished step; the queued step can still be cancelled."""
        eid, r, hb = self.two_steps()
        job = self.claim_and_start(r, hb)
        self.report(r, job)
        self.expect("CONFLICT", lambda: self.cancel(job["job_id"]), 409)
        e = self.execution(eid)
        self.assertEqual((e["state"], [s["state"] for s in e["steps"]]), ("running", ["verified", "queued"]))
        self.assertEqual(self.cancel(e["steps"][1]["job_id"]), {"state": "cancelled"})
        e = self.execution(eid)
        self.assertEqual((e["state"], e["outcome"], e["end_reason"]), ("finished", "cancelled", "cancelled"))

    def test_06_cancel_on_last_step_does_not_hide_completion(self):
        """Nothing left to block: a completed last step ends the sequence normally."""
        eid, r, hb = self.two_steps()
        self.report(r, self.claim_and_start(r, hb))
        last = self.claim_and_start(r, hb)
        self.cancel(last["job_id"])
        self.report(r, last)
        e = self.execution(eid)
        self.assertEqual((e["state"], e["outcome"], e["end_reason"]), ("finished", "verified", "sequence_end"))

    def test_07_race_between_cancel_and_result(self):
        """Either the cancel is accepted and step 2 never exists, or the result won and the cancel is refused."""
        for _ in range(8):
            eid, r, hb = self.two_steps()
            job = self.claim_and_start(r, hb)
            out = {}
            barrier = threading.Barrier(2)

            def do_cancel():
                barrier.wait()
                try:
                    out["cancel"] = self.cancel(job["job_id"])
                except test_core.CoreError as e:
                    out["cancel"] = e.diagnostic.error_code

            def do_report():
                barrier.wait()
                out["report"] = self.report(r, job)

            ts = [threading.Thread(target=do_cancel), threading.Thread(target=do_report)]
            for t in ts:
                t.start()
            for t in ts:
                t.join(30)
            e = self.execution(eid)
            self.assertEqual(out["report"]["state"], "verified")
            if out["cancel"] == "CONFLICT":
                self.assertEqual([s["state"] for s in e["steps"]], ["verified", "queued"])
            else:
                self.assertEqual(out["cancel"], {"state": "running", "cancel_requested": True})
                self.assertEqual([s["state"] for s in e["steps"]], ["verified", None])
                self.assertEqual(e["end_reason"], "cancelled")


if __name__ == "__main__":
    unittest.main()
