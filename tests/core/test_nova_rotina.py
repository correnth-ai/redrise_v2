"""Nova Rotina on the real Core (isolated PostgreSQL on C:, HTTPS API with pinning):
app_open registration, one starting routine per process, preparation and test
jobs, integrating a standalone routine. Runner calls are made by the test as a
declared simulated Runner; nothing is opened here.

    cd tests/core && <lab python> -B -m unittest test_nova_rotina
Env: RR_PG_BIN, RR_CORE_SITE (as test_core)."""

import threading
import unittest
import uuid

import test_core
from test_core import Harness

CALC = {"target": {"kind": "app", "app_id": "Calc!App", "name": "Calculadora"}, "isolated": True}
SITE = {"origin": "site", "browser": "msedge", "url": "https://pedidos.exemplo.test/", "path": None, "isolated": True}


class NovaRotinaTest(unittest.TestCase):
    setUpClass = classmethod(Harness.setUpClass.__func__)
    tearDownClass = classmethod(Harness.tearDownClass.__func__)
    client, expect, admin = Harness.client, Harness.expect, classmethod(Harness.admin.__func__)

    def station(self, name, categories=("windows", "browser")):
        """A station on the first Runner that honours a job's mode."""
        sid, r, hb = Harness.station(self, name, categories=categories)
        hb = {**hb, "runner_version": "0.3.10"}
        r.call("POST", "/api/v1/runner/heartbeat", hb)
        return sid, r, hb

    # ---------------------------------------------------------------- helpers
    def empty_process(self, name=None):
        return self.admin().call("POST", "/api/v1/processes", {"name": name or f"p-{uuid.uuid4().hex[:6]}", "items": []})

    def app_routine(self, link=None, config=CALC, name=None):
        body = {"name": name or f"a-{uuid.uuid4().hex[:6]}", "category": "windows", "version": {"kind": "app_open", "config": config}}
        if link is not None:
            body["link"] = {"process_id": link}
        return self.admin().call("POST", "/api/v1/routines", body)

    def prepare(self, rid, sid, request_id=None):
        return self.admin().call("POST", f"/api/v1/routines/{rid}/prepare", {"request_id": request_id or uuid.uuid4().hex, "station_id": sid})

    def finish(self, r, hb, state="verified", context=None):
        job = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        self.assertIsNotNone(job)
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/start", {"lease_id": job["lease_id"]})
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/progress", {"lease_id": job["lease_id"], "check": {"id": "target", "state": "ok", "detail": "Calculadora"}})
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/result", {"lease_id": job["lease_id"], "result": {
            "schema": "redrise.job-result/1", "state": state, "verified": state == "verified", "details": {"context": context} if context else {}}})
        return job

    # ---------------------------------------------------------------- tests
    def test_01_registration_validation(self):
        out = self.app_routine()
        self.assertEqual(out["version"]["config"], CALC)
        self.assertEqual(out["version"]["kind"], "app_open")
        for bad in ({"isolated": True}, {"target": {"kind": "app", "name": "x"}, "isolated": True},
                    {"target": {"kind": "file", "path": "relativo.txt", "name": "x"}, "isolated": True},
                    {"target": {"kind": "app", "app_id": "a", "name": ""}, "isolated": True},
                    {"target": {"kind": "url", "name": "x"}, "isolated": True}, {"target": CALC["target"]}):
            self.expect("VALIDATION", lambda b=bad: self.app_routine(config=b), 400)
        self.expect("VALIDATION", lambda: self.admin().call("POST", "/api/v1/routines", {
            "name": "x", "category": "browser", "version": {"kind": "app_open", "config": CALC}}), 400)
        rid = out["routine"]["id"]
        v2 = self.admin().call("POST", f"/api/v1/routines/{rid}/versions", {"kind": "app_open", "name": "Nova", "config": {
            "target": {"kind": "file", "path": r"C:\Exemplos\a.xlsx", "name": "a.xlsx"}, "isolated": True}})
        self.assertEqual((v2["version"], v2["config"]["target"]["kind"]), (2, "file"))

    def test_02_process_without_steps_cannot_run(self):
        sid, _, _ = self.station("nr-empty")
        p = self.empty_process()
        self.assertEqual(p["items"], [])
        self.expect("PROCESS-START-INVALID", lambda: self.admin().call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": p["id"]}), 409)

    def test_03_one_starting_routine_per_process(self):
        p = self.empty_process("Com inicio")
        first = self.app_routine(link=p["id"], name="Primeira")
        got = self.admin().call("GET", f"/api/v1/processes/{p['id']}")["items"]
        self.assertEqual([(i["position"], i["routine_id"]) for i in got], [(1, first["routine"]["id"])])
        before = {r["id"] for r in self.admin().call("GET", "/api/v1/routines")}
        e = self.expect("PROCESS-HAS-START", lambda: self.app_routine(link=p["id"], name="Segunda"), 409)
        self.assertEqual(e.diagnostic.params["process"], "Com inicio")
        # The refusal undoes the routine too: the same transaction.
        self.assertEqual({r["id"] for r in self.admin().call("GET", "/api/v1/routines")}, before)
        self.expect("NOT-FOUND", lambda: self.app_routine(link=999999), 404)
        ready_made = next(x for x in self.admin().call("GET", "/api/v1/processes") if x["system_key"])
        self.expect("VALIDATION", lambda: self.app_routine(link=ready_made["id"]), 400)

    def test_04_concurrent_starts_give_one_winner(self):
        p = self.empty_process()
        results = []

        def attempt(i):
            c = self.admin()
            try:
                c.call("POST", "/api/v1/routines", {"name": f"conc-{i}", "category": "windows", "version": {"kind": "app_open", "config": CALC}, "link": {"process_id": p["id"]}})
                results.append("ok")
            except test_core.CoreError as e:
                results.append(e.diagnostic.error_code)
        ts = [threading.Thread(target=attempt, args=(i,)) for i in range(4)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(sorted(results), ["PROCESS-HAS-START"] * 3 + ["ok"])
        self.assertEqual(len(self.admin().call("GET", f"/api/v1/processes/{p['id']}")["items"]), 1)

    def test_05_station_apps(self):
        sid, r, hb = self.station("nr-apps")
        a = self.admin()
        self.assertIsNone(a.call("GET", f"/api/v1/stations/{sid}/apps")["apps"])
        r.call("POST", "/api/v1/runner/heartbeat", {**hb, "apps": [{"id": "Calc!App", "name": "Calculadora"},
                                                                   {"id": "browser:msedge", "name": "Edge", "browser_id": "msedge"},
                                                                   {"id": "x", "name": "Y", "browser_id": "opera"}, {"name": "sem id"}]})
        apps = a.call("GET", f"/api/v1/stations/{sid}/apps")["apps"]
        self.assertEqual(apps, [{"id": "Calc!App", "name": "Calculadora"}, {"id": "browser:msedge", "name": "Edge", "browser_id": "msedge"}, {"id": "x", "name": "Y"}])
        r.call("POST", "/api/v1/runner/heartbeat", hb)  # sent only when it changes: what is stored stays
        self.assertEqual(len(a.call("GET", f"/api/v1/stations/{sid}/apps")["apps"]), 3)
        self.assertNotIn("apps", next(s for s in a.call("GET", "/api/v1/stations") if s["id"] == sid))
        self.expect("NOT-FOUND", lambda: a.call("GET", "/api/v1/stations/999999/apps"), 404)

    def test_06_prepare_then_test_opens_what_was_resolved(self):
        sid, r, hb = self.station("nr-prep")
        p = self.empty_process()
        rid = self.app_routine(link=p["id"])["routine"]["id"]
        req = uuid.uuid4().hex
        job = self.prepare(rid, sid, req)
        self.assertEqual((job["mode"], job["state"]), ("prepare", "queued"))
        self.assertTrue(self.prepare(rid, sid, req)["duplicate"])  # the same request never makes a second job
        self.expect("PREPARE-REQUIRED", lambda: self.admin().call("POST", f"/api/v1/routines/{rid}/test", {"request_id": uuid.uuid4().hex, "prepare_job_id": job["id"]}), 409)
        resolved = {"how": "start_menu", "launch": "shell:AppsFolder\\Calc!App", "name": "Calculadora"}
        claimed = self.finish(r, hb, context={"resolved": resolved})
        self.assertEqual((claimed["mode"], claimed["kind"]), ("prepare", "app_open"))
        got = self.admin().call("GET", f"/api/v1/jobs/{job['id']}")
        self.assertEqual(got["state"], "verified")
        self.assertIn({"id": "target", "state": "ok", "detail": "Calculadora"}, [e["detail"] for e in got["events"] if e["state"] == "check"])
        t = self.admin().call("POST", f"/api/v1/routines/{rid}/test", {"request_id": uuid.uuid4().hex, "prepare_job_id": job["id"]})
        self.assertEqual(t["mode"], "test")
        claim = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        self.assertEqual((claim["mode"], claim["config"], claim["inputs"]), ("test", CALC, {}))  # the raw config of the prepared version, never a stored copy
        # A test is not an execution of the process.
        self.assertIsNone(self.admin().call("GET", f"/api/v1/processes/{p['id']}")["last_execution"])
        r.call("POST", f"/api/v1/runner/jobs/{claim['job_id']}/result", {"lease_id": claim["lease_id"], "result": {"schema": "redrise.job-result/1", "state": "refused", "verified": False}})

    def test_07_a_new_version_needs_a_new_preparation(self):
        sid, r, hb = self.station("nr-ver")
        p = self.empty_process()
        rid = self.app_routine(link=p["id"])["routine"]["id"]
        job = self.prepare(rid, sid)
        self.finish(r, hb, context={"resolved": {"how": "start_menu", "launch": "x", "name": "x"}})
        self.admin().call("POST", f"/api/v1/routines/{rid}/versions", {"kind": "app_open", "config": CALC})
        self.expect("PREPARE-REQUIRED", lambda: self.admin().call("POST", f"/api/v1/routines/{rid}/test", {"request_id": uuid.uuid4().hex, "prepare_job_id": job["id"]}), 409)

    def test_08_failed_preparation_gives_no_test_and_standalone_gives_none(self):
        sid, r, hb = self.station("nr-fail")
        p = self.empty_process()
        rid = self.app_routine(link=p["id"])["routine"]["id"]
        job = self.prepare(rid, sid)
        self.finish(r, hb, state="failed")
        self.expect("PREPARE-REQUIRED", lambda: self.admin().call("POST", f"/api/v1/routines/{rid}/test", {"request_id": uuid.uuid4().hex, "prepare_job_id": job["id"]}), 409)
        free = self.app_routine()["routine"]["id"]
        job = self.prepare(free, sid)
        self.finish(r, hb, context={"resolved": {"how": "start_menu", "launch": "x", "name": "x"}})
        self.expect("VALIDATION", lambda: self.admin().call("POST", f"/api/v1/routines/{free}/test", {"request_id": uuid.uuid4().hex, "prepare_job_id": job["id"]}), 400)

    def test_09_app_routine_runs_by_execution_and_linked_only_by_process(self):
        sid, r, hb = self.station("nr-run")
        free = self.app_routine()["routine"]["id"]
        a = self.admin()
        e = a.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "routine_id": free})
        job = self.finish(r, hb)
        self.assertEqual((job["mode"], job["kind"]), ("run", "app_open"))
        self.assertEqual(a.call("GET", f"/api/v1/executions/{e['id']}")["outcome"], "verified")
        p = self.empty_process()
        linked = self.app_routine(link=p["id"])["routine"]["id"]
        self.expect("ROUTINE-LINKED", lambda: a.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "routine_id": linked}), 409)
        browser_only, _, _ = self.station("nr-browser-only", categories=("browser",))
        self.expect("STATION-INCOMPATIBLE", lambda: a.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": browser_only, "process_id": p["id"]}), 409)

    def test_10_integrating_a_standalone_routine(self):
        a = self.admin()
        p = self.empty_process("Integracao")
        one, two = self.app_routine()["routine"]["id"], self.app_routine()["routine"]["id"]
        out = a.call("POST", f"/api/v1/processes/{p['id']}/items", {"routine_id": one})
        self.assertEqual([i["routine_id"] for i in out["items"]], [one])
        a.call("PUT", f"/api/v1/processes/{p['id']}", {"name": "Integracao", "items": [{"routine_id": one, "continue_next": False}]})  # same step 1, continuation off
        out = a.call("POST", f"/api/v1/processes/{p['id']}/items", {"routine_id": two})
        # The step before now continues to it, or it would never run.
        self.assertEqual([(i["position"], i["routine_id"], i["continue_next"]) for i in out["items"]], [(1, one, True), (2, two, True)])
        self.expect("CONFLICT", lambda: a.call("POST", f"/api/v1/processes/{p['id']}/items", {"routine_id": two}), 409)
        other = self.empty_process()
        self.expect("CONFLICT", lambda: a.call("POST", f"/api/v1/processes/{other['id']}/items", {"routine_id": one}), 409)
        ready_made = next(x for x in a.call("GET", "/api/v1/processes") if x["system_key"])
        three = self.app_routine()["routine"]["id"]
        self.expect("VALIDATION", lambda: a.call("POST", f"/api/v1/processes/{ready_made['id']}/items", {"routine_id": three}), 400)
        template = self.admin().call("POST", "/api/v1/routines", {"name": "m", "category": "windows", "version": {"kind": "template", "template_id": "boas-vindas"}})["routine"]["id"]
        self.expect("VALIDATION", lambda: a.call("POST", f"/api/v1/processes/{other['id']}/items", {"routine_id": template}), 400)

    def test_11_operators_cannot_prepare_test_or_integrate(self):
        a = self.admin()
        a.call("POST", "/api/v1/users", {"username": "operador-nr", "display": "Op", "password": test_core.PW, "role": "operator"})
        tok = self.client().call("POST", "/api/v1/login", {"username": "operador-nr", "password": test_core.PW})["token"]
        op = self.client(tok)
        sid, _, _ = self.station("nr-op")
        p = self.empty_process()
        rid = self.app_routine()["routine"]["id"]
        self.expect("AUTH-FORBIDDEN", lambda: op.call("POST", f"/api/v1/routines/{rid}/prepare", {"request_id": uuid.uuid4().hex, "station_id": sid}), 403)
        self.expect("AUTH-FORBIDDEN", lambda: op.call("POST", f"/api/v1/routines/{rid}/test", {"request_id": uuid.uuid4().hex, "prepare_job_id": str(uuid.uuid4())}), 403)
        self.expect("AUTH-FORBIDDEN", lambda: op.call("POST", f"/api/v1/processes/{p['id']}/items", {"routine_id": rid}), 403)

    def test_13_a_new_version_keeps_the_kind_of_the_routine(self):
        a = self.admin()
        uid = a.call("GET", "/api/v1/me")["id"]
        p = self.empty_process()
        first = self.app_routine(link=p["id"])["routine"]["id"]
        follow = {"kind": "followup", "config": {"action": "review", "assignee_id": uid}}
        self.expect("VALIDATION", lambda: a.call("POST", f"/api/v1/routines/{first}/versions", follow), 400)  # step 1 never becomes a follow-up
        rv = a.call("POST", "/api/v1/routines", {"name": "rv", "category": "windows", "version": follow, "link": {"process_id": p["id"], "after_position": 1}})["routine"]["id"]
        self.expect("VALIDATION", lambda: a.call("POST", f"/api/v1/routines/{rv}/versions", {"kind": "app_open", "config": CALC}), 400)
        t = a.call("POST", "/api/v1/routines", {"name": "m", "category": "windows", "version": {"kind": "template", "template_id": "boas-vindas"}})
        self.expect("VALIDATION", lambda: a.call("POST", f"/api/v1/routines/{t['routine']['id']}/versions", {"kind": "app_open", "config": CALC}), 400)  # no back door to run a linked routine as a job
        self.expect("VALIDATION", lambda: a.call("POST", f"/api/v1/routines/{first}/versions", {"kind": "template", "template_id": "boas-vindas"}), 400)

    def test_14_older_runner_gets_no_assistant_job(self):
        sid, r, hb = Harness.station(self, "nr-old")  # would open on "prepare": it ignores the mode
        rid = self.app_routine()["routine"]["id"]
        self.expect("STATION-INCOMPATIBLE", lambda: self.prepare(rid, sid), 409)

    def test_12_progress_needs_the_lease(self):
        sid, r, hb = self.station("nr-lease")
        rid = self.app_routine()["routine"]["id"]
        self.prepare(rid, sid)
        job = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        self.expect("CONFLICT", lambda: r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/progress", {"lease_id": str(uuid.uuid4()), "check": {"id": "x", "state": "ok"}}), 409)
        self.expect("CONTRACT-PAYLOAD", lambda: r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/progress", {"lease_id": job["lease_id"], "check": {"id": "x", "state": "maybe"}}), 400)
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/result", {"lease_id": job["lease_id"], "result": {"schema": "redrise.job-result/1", "state": "refused", "verified": False}})


if __name__ == "__main__":
    unittest.main()
