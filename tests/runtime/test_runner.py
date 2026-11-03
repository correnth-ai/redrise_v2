"""Runner contract tests (fake Engine). Run from the repo root:
    <python> -m unittest discover -s tests/runtime -t .
"""

import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runner"))
sys.path.insert(0, str(ROOT / "contracts" / "python"))

from redrise_runner.engine import EngineClient  # noqa: E402
from redrise_runner.jobs import JobSpec, run_job, session_lock  # noqa: E402
from redrise_runner.paths import Layout  # noqa: E402

FAKE = Path(__file__).with_name("fake_engine.py")


def procedure(tmp: Path, category="windows", platform="windows-x86_64") -> Path:
    p = tmp / f"proc-{category}-{platform}.json"
    p.write_text(json.dumps({"ir_version": 1, "category": category, "platform": platform, "steps": []}), encoding="utf-8")
    return p


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.layout = Layout(self.tmp / "install", self.tmp / "install/runtime/python", FAKE, self.tmp / "data")
        self.log = self.tmp / "engine-run.log"
        os.environ["FAKE_ENGINE_LOG"] = str(self.log)
        os.environ["FAKE_ENGINE_MODE"] = "ready"
        self.engine = EngineClient([sys.executable, str(FAKE)])

    def job(self, jid="j1", **kw) -> dict:
        return run_job(JobSpec(jid, kw.pop("proc", None) or procedure(self.tmp), kw.pop("bindings", {})), self.layout, self.engine, kw.pop("cancel", None))

    def test_completed_is_unverified_and_persisted(self):
        r = self.job()
        self.assertEqual(r["state"], "completed_unverified")
        self.assertFalse(r["verified"])
        rec = json.loads((self.layout.jobs_dir / "j1/job.json").read_text(encoding="utf-8"))
        self.assertEqual([h["state"] for h in rec["history"]], ["accepted", "running", "completed_unverified"])

    def test_incompatible_category_refused_before_engine(self):
        for cat, plat, code in (("macos", "macos-aarch64", "category_incompatible"), ("linux", "linux-x86_64", "category_incompatible"),
                                ("windows", "windows-aarch64", "platform_incompatible"), ("android", "windows-x86_64", "category_incompatible")):
            r = self.job(jid=f"x-{cat}-{plat}", proc=procedure(self.tmp, cat, plat))
            self.assertEqual((r["state"], r["code"]), ("refused", code))
        self.assertFalse(self.log.exists(), "engine run must not be invoked")

    def test_locked_session_refused_without_engine_run(self):
        os.environ["FAKE_ENGINE_MODE"] = "locked"
        r = self.job()
        self.assertEqual((r["state"], r["code"]), ("refused", "session_unavailable"))
        self.assertFalse(self.log.exists())

    def test_job_is_never_rerun(self):
        self.job()
        self.log.unlink()
        r = self.job()
        self.assertEqual((r["state"], r["code"]), ("refused", "job_already_exists"))
        self.assertFalse(self.log.exists())

    def test_uncertain_is_preserved(self):
        os.environ["FAKE_ENGINE_MODE"] = "uncertain"
        r = self.job()
        self.assertEqual((r["state"], r["failed_step"]), ("uncertain", 9))

    def test_session_busy_refused(self):
        with session_lock(self.layout.locks_dir):
            r = self.job()
        self.assertEqual((r["state"], r["code"]), ("refused", "session_busy"))
        self.assertFalse(self.log.exists())

    def test_cancel_is_forwarded_cooperatively(self):
        os.environ["FAKE_ENGINE_MODE"] = "slow"
        cancel = threading.Event()
        threading.Timer(0.3, cancel.set).start()
        t = time.monotonic()
        r = self.job(cancel=cancel)
        self.assertEqual(r["state"], "cancelled")
        self.assertLess(time.monotonic() - t, 4)

    def test_bindings_reach_engine(self):
        self.job(bindings={"output_path": "C:\\x\\y.xlsx"})
        argv = json.loads(self.log.read_text(encoding="utf-8"))
        self.assertIn("output_path=C:\\x\\y.xlsx", argv)

    def test_unknown_job_fields_rejected(self):
        p = self.tmp / "job.json"
        p.write_text(json.dumps({"job_id": "a", "procedure": "p", "script": "rm"}), encoding="utf-8")
        with self.assertRaises(ValueError):
            JobSpec.load(p)
        p.write_text(json.dumps({"job_id": "..\\evil", "procedure": "p"}), encoding="utf-8")
        with self.assertRaises(ValueError):
            JobSpec.load(p)

    def test_job_file_with_utf8_bom_is_accepted(self):
        p = self.tmp / "bom.json"
        p.write_bytes(b"\xef\xbb\xbf" + json.dumps({"job_id": "b", "procedure": "p"}).encode())
        self.assertEqual(JobSpec.load(p).job_id, "b")

    def test_integrity_detects_missing_modified_unexpected(self):
        from redrise_runner import integrity
        import hashlib
        root = self.tmp / "inst"
        (root / "engine").mkdir(parents=True)
        (root / "engine/a.bin").write_bytes(b"A")
        (root / "b.txt").write_bytes(b"B")
        files = [{"path": p, "sha256": hashlib.sha256(d).hexdigest()} for p, d in (("engine/a.bin", b"A"), ("b.txt", b"B"))]
        (root / "manifest.json").write_text(json.dumps({"files": files}), encoding="utf-8")
        self.assertTrue(integrity.verify(root)["ok"])
        (root / "engine/a.bin").write_bytes(b"tampered")
        (root / "b.txt").unlink()
        (root / "extra.dll").write_bytes(b"x")
        r = integrity.verify(root)
        self.assertEqual((r["ok"], r["modified"], r["missing"], r["unexpected"]), (False, ["engine/a.bin"], ["b.txt"], ["extra.dll"]))

    def test_missing_engine_is_reported(self):
        from redrise_runner.engine import EngineError
        with self.assertRaises(EngineError) as ctx:
            EngineClient.at(self.tmp / "nope.exe")
        self.assertEqual(ctx.exception.code, "engine_missing")


if __name__ == "__main__":
    unittest.main()
