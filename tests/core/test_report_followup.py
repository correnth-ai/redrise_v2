"""Follow-up "report" on the real Core: the step goes to the Runner with its execution,
continues to the next step only when verified. Declared simulated Runner.

    cd tests/core && <lab python> -B -m unittest test_report_followup
Env: RR_PG_BIN, RR_CORE_SITE (as test_core)."""

import unittest
import uuid

from test_core import CoreTest

CALC = {"target": {"kind": "app", "app_id": "Calc!App", "name": "Calculadora"}, "isolated": True}
PT = {"title": "Relat\xf3rio"}


class ReportFollowUpTest(unittest.TestCase):
    setUpClass = classmethod(CoreTest.setUpClass.__func__)
    tearDownClass = classmethod(CoreTest.tearDownClass.__func__)
    client, expect, admin, station = CoreTest.client, CoreTest.expect, classmethod(CoreTest.admin.__func__), CoreTest.station

    def setup_process(self, labels=None, name="Com relatorio"):
        a = self.admin()
        p = a.call("POST", "/api/v1/processes", {"name": f"{name} {uuid.uuid4().hex[:4]}", "items": []})
        a.call("POST", "/api/v1/routines", {"name": "Abrir", "category": "windows", "version": {"kind": "app_open", "config": CALC}, "link": {"process_id": p["id"]}})
        rid = a.call("POST", "/api/v1/routines", {"name": "Gerar relatorio", "category": "windows", "link": {"process_id": p["id"], "after_position": 1},
                                                  "version": {"kind": "followup", "config": {"action": "report", "labels": labels if labels is not None else PT}}})["routine"]["id"]
        return p["id"], rid

    def finish(self, r, hb, job, state="verified", context=None):
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/start", {"lease_id": job["lease_id"]})
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/result", {"lease_id": job["lease_id"], "result": {
            "schema": "redrise.job-result/1", "state": state, "verified": state == "verified", "details": {"context": context or {}}}})

    def test_01_report_step_receives_the_real_execution(self):
        sid, r, hb = self.station("rp-flow")
        pid, _ = self.setup_process()
        a = self.admin()
        e = a.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": pid})
        first = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        self.assertNotIn("execution", first)  # only the report needs it
        self.finish(r, hb, first, context={"opened": {"name": "Calculadora"}})
        job = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        self.assertEqual((job["kind"], job["position"], job["config"]["action"], job["config"]["labels"]), ("followup", 2, "report", PT))
        ex = job["execution"]
        self.assertEqual([s["state"] for s in ex["steps"]], ["verified", "claimed"])
        self.assertEqual(ex["context"]["steps"]["1"], {"opened": {"name": "Calculadora"}})
        self.assertEqual(ex["id"], e["id"])
        self.finish(r, hb, job, context={"report": {"file": "Relatorio.pdf", "bytes": 10}})
        done = a.call("GET", f"/api/v1/executions/{e['id']}")
        self.assertEqual((done["state"], done["outcome"]), ("finished", "verified"))
        self.assertEqual(done["context"]["steps"]["2"]["report"]["file"], "Relatorio.pdf")

    def test_02_report_not_verified_stops_the_execution(self):
        sid, r, hb = self.station("rp-fail")
        pid, _ = self.setup_process()
        a = self.admin()
        a.call("POST", f"/api/v1/processes/{pid}/items", {"routine_id": a.call("POST", "/api/v1/routines", {"name": "Depois", "category": "windows", "version": {"kind": "app_open", "config": CALC}})["routine"]["id"]})
        e = a.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": pid})
        self.finish(r, hb, r.call("POST", "/api/v1/runner/claim", hb)["job"])
        self.finish(r, hb, r.call("POST", "/api/v1/runner/claim", hb)["job"], state="failed")
        got = a.call("GET", f"/api/v1/executions/{e['id']}")
        self.assertEqual((got["state"], got["outcome"], got["steps"][2]["state"]), ("finished", "failed", None))
        self.assertIsNone(r.call("POST", "/api/v1/runner/claim", hb)["job"])

    def test_03_validation_and_a_routine_keeps_its_action(self):
        a = self.admin()
        pid, rid = self.setup_process()
        link = {"process_id": pid, "after_position": 1}
        for bad in ({"action": "report", "labels": "x"}, {"action": "report", "labels": {"title": 1}}, {"action": "report", "labels": {"t" * 41: "x"}}, {"action": "enviar"}):
            self.expect("VALIDATION", lambda b=bad: a.call("POST", "/api/v1/routines", {"name": "x", "category": "windows", "version": {"kind": "followup", "config": b}, "link": link}), 400)
        me = a.call("GET", "/api/v1/me")["id"]
        self.expect("VALIDATION", lambda: a.call("POST", f"/api/v1/routines/{rid}/versions", {"kind": "followup", "config": {"action": "review", "assignee_id": me}}), 400)
        v = a.call("POST", f"/api/v1/routines/{rid}/versions", {"kind": "followup", "name": "Relatorio final", "config": {"action": "report", "labels": PT}})
        self.assertEqual(v["version"], 2)

    def test_04_browser_only_station_cannot_run_it(self):
        sid, _, _ = self.station("rp-browser", categories=("browser",))
        a = self.admin()
        p = a.call("POST", "/api/v1/processes", {"name": f"So site {uuid.uuid4().hex[:4]}", "items": []})
        a.call("POST", "/api/v1/routines", {"name": "Site", "category": "browser", "link": {"process_id": p["id"]}, "version": {"kind": "browser_open", "config": {
            "origin": "site", "browser": "msedge", "url": "https://x.exemplo.test/", "path": None, "isolated": True}}})
        a.call("POST", "/api/v1/routines", {"name": "Rel", "category": "windows", "link": {"process_id": p["id"], "after_position": 1},
                                            "version": {"kind": "followup", "config": {"action": "report", "labels": {}}}})
        self.expect("STATION-INCOMPATIBLE", lambda: a.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": p["id"]}), 409)


if __name__ == "__main__":
    unittest.main()
