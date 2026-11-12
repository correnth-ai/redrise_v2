"""Update Browser: browser routines, processes and executions on the real Core
(isolated PostgreSQL on C:, HTTPS API with pinning). Runner calls are made by
the test as a declared simulated Runner; no browser is opened here.

    cd tests/core && <lab python> -B -m unittest test_browser_processes
Env: RR_PG_BIN, RR_CORE_SITE (as test_core)."""

import unittest
import uuid

import test_core
from test_core import Harness

SITE = {"origin": "site", "browser": "msedge", "url": "https://pedidos.exemplo.test/", "path": None, "isolated": True}
HTML = {"origin": "html", "browser": None, "url": None, "path": "C:\\Exemplos\\manual.html", "isolated": True}


class BrowserProcessTest(unittest.TestCase):
    setUpClass = classmethod(Harness.setUpClass.__func__)
    tearDownClass = classmethod(Harness.tearDownClass.__func__)
    client, expect, admin, station = Harness.client, Harness.expect, classmethod(Harness.admin.__func__), Harness.station

    # ---------------------------------------------------------------- helpers
    def other_admin(self):
        """Second administrator: whoever asks for a replacement of step 1 does not approve it alone."""
        cls = type(self)
        if "_other" not in vars(cls):
            self.admin().call("POST", "/api/v1/users", {"username": "admin2", "display": "Admin 2", "password": test_core.PW, "role": "admin"})
            cls._other = self.client().call("POST", "/api/v1/login", {"username": "admin2", "password": test_core.PW})["token"]
        return cls._other

    def browser_routine(self, config=SITE, name=None):
        out = self.admin().call("POST", "/api/v1/routines", {"name": name or f"b-{uuid.uuid4().hex[:6]}", "category": "browser",
                                                             "version": {"kind": "browser_open", "config": config}})
        return out["routine"]["id"], out["version"]["id"]

    def process(self, links, name=None):
        return self.admin().call("POST", "/api/v1/processes", {"name": name or f"p-{uuid.uuid4().hex[:6]}",
                                                               "items": [{"routine_id": r, "continue_next": c} for r, c in links]})

    def execute(self, sid, request_id=None, **target):
        return self.admin().call("POST", "/api/v1/executions", {"request_id": request_id or uuid.uuid4().hex, "station_id": sid, **target})

    def run_claimed(self, r, hb, state="verified", context=None):
        """Simulated Runner: claim -> start -> report. Returns the claim."""
        job = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        self.assertIsNotNone(job)
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/start", {"lease_id": job["lease_id"]})
        result = {"schema": "redrise.job-result/1", "state": state, "verified": state == "verified",
                  "details": {"context": context} if context else {}}
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/result", {"lease_id": job["lease_id"], "result": result})
        return job, result

    def get(self, eid):
        return self.admin().call("GET", f"/api/v1/executions/{eid}")

    # ---------------------------------------------------------------- tests
    def test_01_registration_validation_and_versioning(self):
        a = self.admin()
        rid, _ = self.browser_routine(SITE, "Abrir portal")
        # HTML keeps only its own fields: a residual browser is never stored for HTML (B03).
        _, hv = self.browser_routine({**HTML, "browser": "chrome", "url": "https://x.test/"})
        stored = next(r for r in a.call("GET", "/api/v1/routines") if r["version_id"] == hv)["config"]
        self.assertEqual((stored["browser"], stored["url"], stored["path"]), (None, None, HTML["path"]))
        for bad in ({**SITE, "url": "pedidos.exemplo.test"}, {**SITE, "browser": "opera"}, {**HTML, "path": "manual.html"},
                    {**SITE, "isolated": None}, {"origin": "app"}):
            self.expect("VALIDATION", lambda b=bad: self.browser_routine(b), 400)
        self.expect("VALIDATION", lambda: a.call("POST", "/api/v1/routines", {"name": "x", "category": "windows",
                                                                               "version": {"kind": "browser_open", "config": SITE}}), 400)
        v2 = a.call("POST", f"/api/v1/routines/{rid}/versions", {"kind": "browser_open", "name": "Abrir portal novo",
                                                                  "config": {**SITE, "url": "https://novo.exemplo.test/"}})
        self.assertEqual(v2["version"], 2)
        row = next(r for r in a.call("GET", "/api/v1/routines") if r["id"] == rid)
        self.assertEqual((row["name"], row["config"]["url"], row["version"]), ("Abrir portal novo", "https://novo.exemplo.test/", 2))

    def test_01b_deleting_a_routine(self):
        a = self.admin()
        rid, _ = self.browser_routine(SITE, "Livre")
        linked, _ = self.browser_routine(SITE, "Em uso")
        proc = self.process([(linked, False)], "Processo em uso")
        # TEAM-ACCOUNTS-20261108 item 6: a linked routine is deleted too, and leaves its process in the same transaction.
        self.assertEqual(a.call("DELETE", f"/api/v1/routines/{linked}")["processes"], ["Processo em uso"])
        self.assertEqual(a.call("GET", f"/api/v1/processes/{proc['id']}")["items"], [])
        self.assertNotIn(linked, [r["id"] for r in a.call("GET", "/api/v1/routines")])
        self.expect("NOT-FOUND", lambda: a.call("DELETE", f"/api/v1/routines/{linked}"), 404)  # never twice
        self.expect("NOT-FOUND", lambda: a.call("POST", "/api/v1/processes", {"name": "Com excluida", "items": [{"routine_id": linked, "continue_next": False}]}), 404)

    def test_02_isolated_flag_enforced_by_api(self):
        sid, _, _ = self.station("iso-st", categories=("browser",))
        rid, vid = self.browser_routine({**SITE, "isolated": False})
        self.expect("ROUTINE-NOT-ISOLATED", lambda: self.execute(sid, routine_id=rid), 409)
        # The legacy job endpoint is not a side door for browser routines.
        self.expect("VALIDATION", lambda: self.admin().call("POST", "/api/v1/jobs", {"request_id": uuid.uuid4().hex,
                    "version_id": vid, "station_id": sid, "inputs": {}}), 400)
        # G29: the same routine is accepted in any position of a process, including the first.
        p = self.process([(rid, False)])
        self.assertEqual(self.execute(sid, process_id=p["id"])["steps"][0]["state"], "queued")

    def test_03_chain_advances_only_on_verified_and_carries_context(self):
        sid, r, hb = self.station("chain-st", categories=("browser",))
        r1, _ = self.browser_routine()
        r2, _ = self.browser_routine(HTML)
        r3, _ = self.browser_routine()
        p = self.process([(r1, True), (r2, True), (r3, True)])
        e = self.execute(sid, process_id=p["id"])
        self.assertEqual([s["state"] for s in e["steps"]], ["queued", None, None])  # G22: first routine only
        ctx1 = {"browser_id": "msedge", "hwnd": 101, "address": "pedidos.exemplo.test"}
        job1, res1 = self.run_claimed(r, hb, "verified", ctx1)
        self.assertEqual((job1["kind"], job1["config"]["url"], job1["context"], job1["position"]),
                         ("browser_open", SITE["url"], {}, 1))
        # A retransmitted report (lost ack) is idempotent and never queues the next routine twice.
        dup = r.call("POST", f"/api/v1/runner/jobs/{job1['job_id']}/result", {"lease_id": job1["lease_id"], "result": res1})
        self.assertTrue(dup["duplicate"])
        job2, _ = self.run_claimed(r, hb, "verified", {"browser_id": "msedge", "hwnd": 102})
        self.assertEqual((job2["position"], job2["context"]["last"], job2["config"]["origin"]), (2, ctx1, "html"))
        self.run_claimed(r, hb, "verified", {"browser_id": "msedge", "hwnd": 103})
        done = self.get(e["id"])
        self.assertEqual((done["state"], done["outcome"], done["end_reason"]), ("finished", "verified", "sequence_end"))
        self.assertEqual([s["state"] for s in done["steps"]], ["verified"] * 3)
        self.assertEqual(sorted(done["context"]["steps"]), ["1", "2", "3"])
        jobs = [j for j in self.admin().call("GET", "/api/v1/jobs") if j["routine_id"] in (r1, r2, r3)]
        self.assertEqual(len(jobs), 3)

    def test_04_continuation_off_ends_after_the_routine(self):
        sid, r, hb = self.station("stop-st", categories=("browser",))
        r1, _ = self.browser_routine()
        r2, _ = self.browser_routine()
        e = self.execute(sid, process_id=self.process([(r1, False), (r2, True)])["id"])
        self.run_claimed(r, hb, "verified", {"hwnd": 1})
        done = self.get(e["id"])
        self.assertEqual((done["state"], done["outcome"], done["end_reason"]), ("finished", "verified", "continuation_off"))
        self.assertIsNone(done["steps"][1]["state"])  # not executed, and reported as such
        self.assertIsNone(r.call("POST", "/api/v1/runner/claim", hb)["job"])

    def test_05_failed_or_unverified_stop_without_retry(self):
        sid, r, hb = self.station("fail-st", categories=("browser",))
        r1, _ = self.browser_routine()
        r2, _ = self.browser_routine()
        for state in ("failed", "completed_unverified", "uncertain"):
            e = self.execute(sid, process_id=self.process([(r1, True), (r2, True)])["id"])
            self.run_claimed(r, hb, state)
            done = self.get(e["id"])
            self.assertEqual((done["state"], done["outcome"], done["end_reason"]), ("finished", state, "not_verified"), state)
            self.assertEqual([s["state"] for s in done["steps"]], [state, None])
            self.assertEqual(done["context"], {})  # nothing invented for the next routine
            self.assertIsNone(r.call("POST", "/api/v1/runner/claim", hb)["job"])  # no retry, no next

    def test_06_snapshot_fixed_at_start(self):
        sid, r, hb = self.station("snap-st", categories=("browser",))
        r1, _ = self.browser_routine()
        r2, v2 = self.browser_routine(SITE)
        p = self.process([(r1, True), (r2, True)])
        e = self.execute(sid, process_id=p["id"])
        # Edits after the start only affect new executions (G27).
        self.admin().call("POST", f"/api/v1/routines/{r2}/versions", {"kind": "browser_open", "config": {**SITE, "url": "https://outro.exemplo.test/"}})
        self.admin().call("PUT", f"/api/v1/processes/{p['id']}", {"name": p["name"], "items": [{"routine_id": r1, "continue_next": False}]})
        self.run_claimed(r, hb, "verified", {"hwnd": 7})
        job2 = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        self.assertEqual((job2["position"], job2["config"]["url"]), (2, SITE["url"]))
        self.assertEqual(self.get(e["id"])["steps"][1]["routine_version_id"], v2)
        procs = {x["id"]: x for x in self.admin().call("GET", "/api/v1/processes")}
        self.assertEqual(len(procs[p["id"]]["items"]), 1)

    def test_07_execution_request_is_idempotent(self):
        sid, r, hb = self.station("idem-st", categories=("browser",))
        rid, _ = self.browser_routine()
        req = uuid.uuid4().hex
        e1 = self.execute(sid, request_id=req, routine_id=rid)
        e2 = self.execute(sid, request_id=req, routine_id=rid)
        self.assertEqual(e1["id"], e2["id"])
        self.assertTrue(e2["duplicate"])
        self.assertIsNotNone(r.call("POST", "/api/v1/runner/claim", hb)["job"])
        self.assertIsNone(r.call("POST", "/api/v1/runner/claim", hb)["job"])  # one tab, not two

    def test_08_lease_lost_while_running_ends_uncertain(self):
        sid, r, hb = self.station("lease-st", categories=("browser",))
        r1, _ = self.browser_routine()
        r2, _ = self.browser_routine()
        e = self.execute(sid, process_id=self.process([(r1, True), (r2, True)])["id"])
        job = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/start", {"lease_id": job["lease_id"]})
        with self.su() as c:
            c.execute("UPDATE jobs SET lease_expires_at = now() - interval '1 second' WHERE id = %s", (job["job_id"],))
        done = self.get(e["id"])
        self.assertEqual((done["state"], done["outcome"], done["end_reason"]), ("finished", "uncertain", "not_verified"))
        self.assertIsNone(r.call("POST", "/api/v1/runner/claim", hb)["job"])

    def test_09_browsers_reported_by_station_and_storage(self):
        sid, r, hb = self.station("disc-st", categories=("browser",))
        found = [{"id": "msedge", "name": "Microsoft Edge", "path": "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
                  "version": "1.2.3.4", "source": "HKLM:StartMenuInternet", "homologated": False},
                 {"id": "unknown-browser", "name": "x"}]
        r.call("POST", "/api/v1/runner/heartbeat", {**hb, "browsers": found})
        st = next(s for s in self.admin().call("GET", "/api/v1/stations") if s["id"] == sid)
        self.assertEqual([b["id"] for b in st["browsers"]], ["msedge"])
        r.call("POST", "/api/v1/runner/heartbeat", hb)  # an older Runner without the field keeps the list
        st = next(s for s in self.admin().call("GET", "/api/v1/stations") if s["id"] == sid)
        self.assertEqual(len(st["browsers"]), 1)
        s = self.admin().call("GET", "/api/v1/storage")
        self.assertGreater(s["db_bytes"], 0)
        self.assertEqual(set(s["counts"]), {"routines", "processes", "executions", "jobs"})

    def test_10_process_validation_and_roles(self):
        a = self.admin()
        rid, _ = self.browser_routine()
        tpl = a.call("POST", "/api/v1/routines", {"name": "m", "category": "windows", "version": {"kind": "template", "template_id": "boas-vindas"}})
        self.assertEqual(self.process([])["items"], [])  # a process may start empty; its step 1 comes from Nova Rotina
        self.expect("VALIDATION", lambda: self.process([(tpl["routine"]["id"], True)]), 400)
        self.expect("NOT-FOUND", lambda: self.process([(999999, True)]), 404)
        a.call("POST", "/api/v1/users", {"username": "oper-bp", "display": "Op", "password": test_core.PW, "role": "operator"})
        op = self.client(self.client().call("POST", "/api/v1/login", {"username": "oper-bp", "password": test_core.PW})["token"])
        self.expect("AUTH-FORBIDDEN", lambda: op.call("POST", "/api/v1/processes", {"name": "x", "items": [{"routine_id": rid, "continue_next": True}]}), 403)
        op.call("GET", "/api/v1/processes")
        op.call("GET", "/api/v1/executions")

    def welcome(self):
        return next(p for p in self.admin().call("GET", "/api/v1/processes") if p["system_key"] == "boas-vindas")

    def test_11_welcome_process_is_ready_and_created_once(self):
        a = self.admin()
        p = self.welcome()
        self.assertEqual(p["name"], "Boas-vindas")
        self.assertEqual([(i["routine_name"], i["kind"], i["config"]["step"], i["continue_next"]) for i in p["items"]],
                         [("Abrir e identificar", "notepad_step", "open", True), ("Digitar e salvar", "notepad_step", "save", True),
                          ("Fechar e verificar", "notepad_step", "close", True)])
        self.su_core().ensure_welcome_process()  # a later start of the same team creates nothing
        self.assertEqual(sum(1 for x in a.call("GET", "/api/v1/processes") if x["system_key"] == "boas-vindas"), 1)
        # Administrators edit it like any process (PROCESS-ACTIONS-20261111 item 1.1); put back as it was after.
        a.call("PUT", f"/api/v1/processes/{p['id']}", {"name": "x", "items": [{"routine_id": p["items"][0]["routine_id"], "continue_next": True}]})
        self.assertEqual(len(self.welcome()["items"]), 1)
        a.call("PUT", f"/api/v1/processes/{p['id']}", {"name": p["name"], "items": [{"routine_id": i["routine_id"], "continue_next": i["continue_next"]} for i in p["items"]]})
        self.assertEqual(self.welcome()["items"], p["items"])

    def test_12_welcome_steps_run_in_order_with_context_of_the_same_execution(self):
        sid, r, hb = self.station("bv-st", categories=("windows",))
        p = self.welcome()
        e = self.execute(sid, process_id=p["id"])
        first, _ = self.run_claimed(r, hb, context={"notepad": {"window": 1, "tab_id": "42.1"}})
        self.assertEqual((first["kind"], first["config"]["step"], first["context"]), ("notepad_step", "open", {}))
        second, _ = self.run_claimed(r, hb, context={"notepad": {"window": 1, "tab_id": "42.1"}, "output_path": "x"})
        self.assertEqual(second["config"]["step"], "save")
        self.assertEqual(second["context"]["last"]["notepad"]["tab_id"], "42.1")
        third = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        self.assertEqual(third["config"]["step"], "close")
        self.assertEqual(third["context"]["last"]["output_path"], "x")
        self.assertEqual(self.get(e["id"])["state"], "running")

    def test_13_failed_step_stops_the_welcome_process(self):
        sid, r, hb = self.station("bv-st2", categories=("windows",))
        e = self.execute(sid, process_id=self.welcome()["id"])
        self.run_claimed(r, hb)
        self.run_claimed(r, hb, state="uncertain")
        got = self.get(e["id"])
        self.assertEqual((got["state"], got["outcome"], got["end_reason"], got["steps"][2]["state"]), ("finished", "uncertain", "not_verified", None))
        self.assertIsNone(r.call("POST", "/api/v1/runner/claim", hb)["job"])

    def test_14_welcome_process_needs_a_windows_station(self):
        sid, _, _ = self.station("bv-browser", categories=("browser",))
        self.expect("STATION-INCOMPATIBLE", lambda: self.execute(sid, process_id=self.welcome()["id"]), 409)

    def test_15_linked_routine_runs_only_through_its_process(self):
        sid, r, hb = self.station("link-st", categories=("browser",))
        rid, _ = self.browser_routine()
        self.assertEqual(self.execute(sid, routine_id=rid)["steps"][0]["state"], "queued")  # still standalone
        self.run_claimed(r, hb)
        p = self.process([(rid, False)], "Processo do vinculo")
        e = self.expect("ROUTINE-LINKED", lambda: self.execute(sid, routine_id=rid), 409)
        self.assertIn("Processo do vinculo", e.diagnostic.next_action)
        self.assertEqual(self.execute(sid, process_id=p["id"])["steps"][0]["state"], "queued")
        self.expect("ROUTINE-LINKED", lambda: self.execute(sid, routine_id=self.welcome()["items"][0]["routine_id"]), 409)

    def test_16_ready_made_routines_have_no_side_doors(self):
        a = self.admin()
        sid, _, _ = self.station("bv-door", categories=("windows",))
        item = self.welcome()["items"][0]
        vid = next(r for r in a.call("GET", "/api/v1/routines") if r["id"] == item["routine_id"])["version_id"]
        self.expect("VALIDATION", lambda: a.call("POST", "/api/v1/jobs", {"request_id": uuid.uuid4().hex, "version_id": vid,
                                                                          "station_id": sid, "inputs": {}}), 400)
        self.expect("VALIDATION", lambda: a.call("POST", f"/api/v1/routines/{item['routine_id']}/versions",
                                                 {"kind": "template", "template_id": "boas-vindas"}), 400)
        self.expect("VALIDATION", lambda: a.call("DELETE", f"/api/v1/routines/{item['routine_id']}"), 400)
        self.assertEqual(self.welcome()["items"][0]["kind"], "notepad_step")

    def su_core(self):
        from redrise_core.service import Core
        return Core(self.h.database, {})

    def su(self):
        return Harness.su(self)


if __name__ == "__main__":
    unittest.main()
