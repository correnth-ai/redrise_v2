"""Runner agent <-> Core link checks (P07): real Core + isolated PostgreSQL,
simulated Engine (tests/runtime/fake_engine.py), no UI actions.

    cd tests/core && <lab python> -B -m unittest test_agent
"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from test_core import LAB, PG_BIN, PW  # noqa: E402,F401  (sets sys.path)

from redrise_contracts.client import CoreClient, CoreError  # noqa: E402
from redrise_contracts import diagnostics as dg  # noqa: E402
from redrise_contracts.vault import MemoryVault  # noqa: E402
from redrise_core import host  # noqa: E402
from redrise_runner import station  # noqa: E402
from redrise_runner.agent import Agent  # noqa: E402
from redrise_runner.engine import EngineClient  # noqa: E402
from redrise_runner.paths import Layout  # noqa: E402

FAKE = ROOT / "tests" / "runtime" / "fake_engine.py"
PROC = {"ir_version": 1, "category": "windows", "platform": "windows-x86_64",
        "source": {"recording_id": "test", "events_sha256": "test", "input_origin": "authored-template"},
        "target_process": "notepad.exe", "params": [],
        "steps": [{"id": 0, "from_seq": [0, 0], "expect": {"process_image": "notepad.exe"}, "action": {"type": "key", "vk": 65}}]}


class FlakyClient(CoreClient):
    """Drops the first result report after the Core processed it (lost ack)."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.drop_next_result_ack = False

    def call(self, method, path, body=None, **kw):
        out = super().call(method, path, body, **kw)
        if path.endswith("/result") and self.drop_next_result_ack:
            self.drop_next_result_ack = False
            raise CoreError(0, dg.make("CORE-UNREACHABLE", reported_by="RR-RUNNER", params={"reason": "ack lost (simulated)"}))
        return out


class AgentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="rr-agent-"))
        inst = cls.tmp / "install"
        shutil.copytree(ROOT / "templates", inst / "templates")
        cls.vault = MemoryVault()
        cls.h = host.Host(host.HostPaths(inst, cls.tmp / "host-data", pg_bin=PG_BIN), cls.vault, log=lambda m: None)
        info = cls.h.start(lan_port=0, bind="127.0.0.1")
        cls.port, cls.fp = info["lan_port"], info["fingerprint"]
        c = CoreClient("127.0.0.1", cls.port, cls.fp)
        c.call("POST", "/api/v1/setup", {"team": "T", "username": "admin", "display": "A", "password": PW})
        cls.admin = CoreClient("127.0.0.1", cls.port, cls.fp, c.call("POST", "/api/v1/login", {"username": "admin", "password": PW})["token"])
        cls.version = cls.admin.call("POST", "/api/v1/routines", {"name": "proc", "category": "windows",
                                                                  "version": {"kind": "procedure", "procedure": PROC}})["version"]["id"]
        cls.inst = inst

    @classmethod
    def tearDownClass(cls):
        cls.h.stop()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        os.environ["FAKE_ENGINE_MODE"] = "ready"
        data = self.tmp / f"st-{uuid.uuid4().hex[:6]}"
        sv = MemoryVault("station")
        code = f"rr1:127.0.0.1:{self.port}:{self.fp}"
        conn = station.join(data, code, "admin", PW, f"est-{data.name}", vault=sv)
        self.sid = conn.station_id
        self.client = FlakyClient("127.0.0.1", self.port, self.fp, sv.get(station.TOKEN), reported_by="RR-RUNNER")
        layout = Layout(self.inst, self.inst / "runtime/python", FAKE, data)
        self.agent = Agent(layout, EngineClient([sys.executable, str(FAKE)]), self.client, poll_s=0.1, log=lambda m: None)
        self.agent.recover()
        self.agent.tick()  # first heartbeat reports platform/categories (no job yet)

    def job(self):
        return self.admin.call("POST", "/api/v1/jobs", {"request_id": uuid.uuid4().hex, "version_id": self.version,
                                                        "station_id": self.sid})["id"]

    def wait_idle(self, timeout=20):
        t0 = time.monotonic()
        while self.agent.state.job_id and time.monotonic() - t0 < timeout:
            time.sleep(0.05)
        if self.agent._worker:
            self.agent._worker.join(timeout)

    def state(self, jid):
        return self.admin.call("GET", f"/api/v1/jobs/{jid}")

    def test_join_rejects_bad_code_and_wrong_fingerprint(self):
        with self.assertRaises(ValueError):
            station.join(self.tmp / "x", "rr1:host:abc:zz", "admin", PW, vault=MemoryVault())
        with self.assertRaises(CoreError) as cm:
            station.join(self.tmp / "y", f"rr1:127.0.0.1:{self.port}:{'1' * 64}", "admin", PW, vault=MemoryVault())
        self.assertEqual(cm.exception.diagnostic.error_code, "CORE-CERT-MISMATCH")

    def test_claim_execute_report_once(self):
        jid = self.job()
        self.agent.tick()
        self.wait_idle()
        st = self.state(jid)
        self.assertEqual(st["state"], "completed_unverified")
        self.assertFalse(st["verified"])
        self.agent.tick()  # nothing new: never re-run
        self.assertEqual([e["state"] for e in self.state(jid)["events"]].count("running"), 1)

    def test_lost_ack_resends_same_result_without_rerun(self):
        log = self.tmp / f"engine-{uuid.uuid4().hex[:6]}.log"
        os.environ["FAKE_ENGINE_LOG"] = str(log)
        self.client.drop_next_result_ack = True
        jid = self.job()
        self.agent.tick()
        self.wait_idle()
        self.assertTrue(any(self.agent.outbox.glob("*.json")))  # kept for resend
        log.unlink()
        self.agent.tick()  # resend; Core treats it as duplicate
        self.assertFalse(any(self.agent.outbox.glob("*.json")))
        self.assertFalse(log.exists())  # Engine not invoked again
        self.assertEqual(self.state(jid)["state"], "completed_unverified")
        os.environ.pop("FAKE_ENGINE_LOG")

    def test_restart_during_job_reports_uncertain(self):
        jid = self.job()
        hb = self.agent.info() | {"session_state": "ready"}
        claim = self.client.call("POST", "/api/v1/runner/claim", hb)["job"]
        self.client.call("POST", f"/api/v1/runner/jobs/{jid}/start", {"lease_id": claim["lease_id"]})
        (self.agent.records / f"{jid}.json").write_text(json.dumps({"job_id": jid, "lease_id": claim["lease_id"],
                                                                    "phase": "running"}), encoding="utf-8")
        self.agent.recover()  # process restarted
        self.agent.tick()
        st = self.state(jid)
        self.assertEqual(st["state"], "uncertain")
        self.assertEqual(st["diagnostic"]["error_code"], "STEP-UNCERTAIN")
        self.assertIn("Check", st["diagnostic"]["next_action"])

    def test_locked_session_does_not_claim(self):
        os.environ["FAKE_ENGINE_MODE"] = "locked"
        jid = self.job()
        self.agent.tick()
        st = self.state(jid)
        self.assertEqual(st["state"], "queued")
        self.assertIn("locked", st["waiting_reason"])

    def test_cancel_running_job(self):
        os.environ["FAKE_ENGINE_MODE"] = "slow"
        jid = self.job()
        self.agent.tick()
        self.admin.call("POST", f"/api/v1/jobs/{jid}/cancel")
        self.agent.tick()  # heartbeat delivers the cancel
        self.wait_idle()
        self.assertEqual(self.state(jid)["state"], "cancelled")


if __name__ == "__main__":
    unittest.main()
