"""Follow-up "notify" on the real Core: what a routine may store and that the step goes to the
Runner with its execution. Declared simulated Runner; no message exists anywhere here.

    cd tests/core && <lab python> -B -m unittest test_notify_followup
Env: RR_PG_BIN, RR_CORE_SITE (as test_core)."""

import unittest
import uuid

from test_core import CoreTest

CALC = {"target": {"kind": "app", "app_id": "Calc!App", "name": "Calculadora"}, "isolated": True}
APP = {"kind": "app", "mail_id": "outlook", "name": "Microsoft Outlook"}
WEB = {"kind": "webmail", "provider": "gmail", "browser": "msedge", "name": "Gmail"}


def notify(to="pessoa@exemplo.test", channel=APP, **over):
    return {"kind": "followup", "config": {"action": "notify", "to": to, "channel": channel, "labels": {"subject": "{process}"}, **over}}


class NotifyFollowUpTest(unittest.TestCase):
    setUpClass = classmethod(CoreTest.setUpClass.__func__)
    tearDownClass = classmethod(CoreTest.tearDownClass.__func__)
    client, expect, admin, station = CoreTest.client, CoreTest.expect, classmethod(CoreTest.admin.__func__), CoreTest.station

    def process(self):
        a = self.admin()
        p = a.call("POST", "/api/v1/processes", {"name": f"Aviso {uuid.uuid4().hex[:4]}", "items": []})
        a.call("POST", "/api/v1/routines", {"name": "Abrir", "category": "windows", "version": {"kind": "app_open", "config": CALC}, "link": {"process_id": p["id"]}})
        return p["id"]

    def add(self, pid, version):
        return self.admin().call("POST", "/api/v1/routines", {"name": f"Avisar {uuid.uuid4().hex[:4]}", "category": "windows", "version": version, "link": {"process_id": pid, "after_position": 1}})

    def test_01_what_is_stored(self):
        pid = self.process()
        out = self.add(pid, notify(to=" pessoa@exemplo.test ", channel={**APP, "extra": "x"}))
        self.assertEqual(out["version"]["config"]["to"], "pessoa@exemplo.test")
        self.assertEqual(out["version"]["config"]["channel"], APP)  # only the fields of the channel
        self.assertEqual(self.add(self.process(), notify(channel=WEB))["version"]["config"]["channel"], WEB)
        for bad in (notify(to="sem-arroba"), notify(to="a@b.com?bcc=x%40y.z"), notify(to="a@b.com,c@d.com"), notify(channel={"kind": "app", "mail_id": "smtp"}), notify(channel={**WEB, "provider": "x"}), notify(channel={**WEB, "browser": "opera"}),
                    notify(channel="outlook"), notify(labels="x")):
            self.expect("VALIDATION", lambda b=bad: self.add(self.process(), b), 400)

    def test_02_step_goes_to_the_runner_and_the_result_is_recorded(self):
        sid, r, hb = self.station("nt-flow")
        a = self.admin()
        pid = self.process()
        self.add(pid, notify())
        e = a.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": sid, "process_id": pid})

        def finish(context):
            job = r.call("POST", "/api/v1/runner/claim", hb)["job"]
            r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/start", {"lease_id": job["lease_id"]})
            r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/result", {"lease_id": job["lease_id"], "result": {
                "schema": "redrise.job-result/1", "state": "verified", "verified": True, "details": {"context": context}}})
            return job
        finish({"opened": {"name": "Calculadora"}})
        job = finish({"message": {"status": "prepared", "to": "pessoa@exemplo.test", "channel": "Microsoft Outlook"}})
        self.assertEqual((job["config"]["action"], job["execution"]["id"]), ("notify", e["id"]))
        got = a.call("GET", f"/api/v1/executions/{e['id']}")
        self.assertEqual((got["state"], got["outcome"], got["context"]["steps"]["2"]["message"]["status"]), ("finished", "verified", "prepared"))

    def test_03_station_reports_mail_applications(self):
        sid, r, hb = self.station("nt-apps")
        r.call("POST", "/api/v1/runner/heartbeat", {**hb, "apps": [{"id": "mail:outlook", "name": "Microsoft Outlook", "mail_id": "outlook"}, {"id": "mail:x", "name": "X", "mail_id": "smtp"}]})
        self.assertEqual(self.admin().call("GET", f"/api/v1/stations/{sid}/apps")["apps"], [{"id": "mail:outlook", "name": "Microsoft Outlook", "mail_id": "outlook"}, {"id": "mail:x", "name": "X"}])

    def test_04_a_new_version_keeps_the_action(self):
        a = self.admin()
        rid = self.add(self.process(), notify())["routine"]["id"]
        self.expect("VALIDATION", lambda: a.call("POST", f"/api/v1/routines/{rid}/versions", {"kind": "followup", "config": {"action": "report", "labels": {}}}), 400)
        self.assertEqual(a.call("POST", f"/api/v1/routines/{rid}/versions", {**notify(to="outra@exemplo.test"), "name": "Avisar outra"})["version"], 2)


if __name__ == "__main__":
    unittest.main()
