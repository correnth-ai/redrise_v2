"""Change feed on the real Core and PostgreSQL: announced on commit, by domain, without noise
from heartbeats, with a bounded wait. Declared simulated Runner.

    cd tests/core && <lab python> -B -m unittest test_changes
Env: RR_PG_BIN, RR_CORE_SITE (as test_core)."""

import threading
import time
import unittest
import uuid

import test_core
from test_core import CoreTest

SITE = {"origin": "site", "browser": "msedge", "url": "https://x.exemplo.test/", "path": None, "isolated": True}


class ChangesTest(unittest.TestCase):
    setUpClass = classmethod(CoreTest.setUpClass.__func__)
    tearDownClass = classmethod(CoreTest.tearDownClass.__func__)
    client, expect, admin, station = CoreTest.client, CoreTest.expect, classmethod(CoreTest.admin.__func__), CoreTest.station

    def now(self):
        return self.admin().call("POST", "/api/v1/changes", {})

    def after(self, mark, wait=5.0):
        """Everything announced after `mark`, collecting until a quiet moment."""
        domains, seq, end = set(), mark["seq"], time.monotonic() + wait
        while time.monotonic() < end:
            out = self.admin().call("POST", "/api/v1/changes", {"epoch": mark["epoch"], "seq": seq, "wait_s": 0.6})
            if not out["domains"] and domains:
                break
            domains |= set(out["domains"])
            seq = out["seq"]
        return domains

    def routine(self, name=None):
        return self.admin().call("POST", "/api/v1/routines", {"name": name or f"r-{uuid.uuid4().hex[:6]}", "category": "browser", "version": {"kind": "browser_open", "config": SITE}})["routine"]["id"]

    def test_01_needs_a_session(self):
        self.expect("AUTH-REQUIRED", lambda: self.client().call("POST", "/api/v1/changes", {}), 401)

    def test_02_each_change_names_its_domain(self):
        a = self.admin()
        mark = self.now()
        rid = self.routine()
        self.assertIn("routines", self.after(mark))
        mark = self.now()
        p = a.call("POST", "/api/v1/processes", {"name": f"p-{uuid.uuid4().hex[:6]}", "items": [{"routine_id": rid, "continue_next": False}]})
        self.assertIn("processes", self.after(mark))
        sid, r, hb = self.station("ch-run", categories=("browser",))
        mark = self.now()
        a.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": p["id"]})
        got = self.after(mark)
        self.assertLessEqual({"executions", "jobs"}, got)
        mark = self.now()
        job = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        self.assertIn("jobs", self.after(mark))
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/start", {"lease_id": job["lease_id"]})
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/result", {"lease_id": job["lease_id"], "result": {"schema": "redrise.job-result/1", "state": "verified", "verified": True}})

    def test_03_a_heartbeat_without_news_is_silent(self):
        sid, r, hb = self.station("ch-beat")
        time.sleep(0.5)
        mark = self.now()
        for _ in range(3):
            r.call("POST", "/api/v1/runner/heartbeat", hb)
        self.assertEqual(self.admin().call("POST", "/api/v1/changes", {"epoch": mark["epoch"], "seq": mark["seq"], "wait_s": 1.0})["domains"], [])
        r.call("POST", "/api/v1/runner/heartbeat", {**hb, "session_state": "locked", "session_reason": "tela bloqueada"})
        self.assertIn("stations", self.after(mark))
        r.call("POST", "/api/v1/runner/heartbeat", hb)

    def test_04_a_refused_change_announces_nothing(self):
        a = self.admin()
        p = a.call("POST", "/api/v1/processes", {"name": f"p-{uuid.uuid4().hex[:6]}", "items": []})
        a.call("POST", f"/api/v1/processes/{p['id']}/items", {"routine_id": self.routine()})
        time.sleep(0.5)
        mark = self.now()
        # The routine is inserted inside the transaction, then the process refuses it: rollback.
        self.expect("PROCESS-HAS-START", lambda: a.call("POST", "/api/v1/routines", {"name": "x", "category": "browser", "version": {"kind": "browser_open", "config": SITE}, "link": {"process_id": p["id"]}}), 409)
        self.assertEqual(a.call("POST", "/api/v1/changes", {"epoch": mark["epoch"], "seq": mark["seq"], "wait_s": 1.0})["domains"], [])

    def test_05_waits_and_wakes_at_once(self):
        mark = self.now()
        got = {}

        def wait():
            start = time.monotonic()
            got["out"] = self.admin().call("POST", "/api/v1/changes", {"epoch": mark["epoch"], "seq": mark["seq"], "wait_s": 15}, timeout_s=25)
            got["s"] = time.monotonic() - start
        t = threading.Thread(target=wait)
        t.start()
        time.sleep(0.7)
        self.routine()
        t.join()
        self.assertIn("routines", got["out"]["domains"])
        self.assertLess(got["s"], 5)

    def test_06_bounded_wait_and_other_epoch(self):
        mark = self.now()
        out = self.admin().call("POST", "/api/v1/changes", {"epoch": "outro", "seq": 0, "wait_s": 15})
        self.assertEqual((out["domains"], out["epoch"]), (["*"], mark["epoch"]))  # another Core: read everything again
        start = time.monotonic()
        self.admin().call("POST", "/api/v1/changes", {"epoch": mark["epoch"], "seq": 10 ** 9, "wait_s": 0.4})
        self.assertLess(time.monotonic() - start, 3)
        self.assertEqual(self.admin().call("POST", "/api/v1/changes", {"epoch": mark["epoch"], "seq": "x"})["domains"], ["*"])

    def test_07_feed_cap(self):
        from redrise_core.changes import MAX_WAIT_S, ChangeFeed
        f = ChangeFeed(None)
        self.assertEqual(MAX_WAIT_S, 20.0)
        start = time.monotonic()
        threading.Timer(0.2, lambda: f.bump("x")).start()
        self.assertEqual(f.since(0, f.epoch, 10 ** 6)["domains"], ["x"])
        self.assertLess(time.monotonic() - start, 3)
        self.assertEqual(f.since(1, f.epoch, -5)["domains"], [])


if __name__ == "__main__":
    unittest.main()
