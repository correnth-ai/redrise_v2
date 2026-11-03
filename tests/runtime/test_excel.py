"""Excel capabilities with fixtures (no Excel launched, nothing uninstalled).
    cd tests/runtime && <python> -B -m unittest test_excel
Simulated: registry, file checks, version reader, launcher, window probe and
the Engine start-screen dismissal are doubles declared per test."""

import sys
import unittest
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runner"))
sys.path.insert(0, str(ROOT / "contracts" / "python"))

from redrise_contracts import diagnostics as dg  # noqa: E402
from redrise_runner import diagnose, excel  # noqa: E402

EXE = r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE"
DESC = {"schema": excel.DESCRIPTOR_SCHEMA, "executable": EXE, "version": "16.0.19000.20000", "method": "app_paths"}


class FakeReg:
    def __init__(self, values=None, fail=False):
        self.values, self.fail = values or {}, fail

    def value(self, hive, key, name):
        if self.fail:
            raise PermissionError("access denied")
        return self.values.get((hive, key, name))


APP = (winreg.HKEY_LOCAL_MACHINE, excel._APP_PATHS, None)
C2R = (winreg.HKEY_LOCAL_MACHINE, excel._C2R, "InstallPath")


class Discover(unittest.TestCase):
    def test_found_via_app_paths(self):
        r = excel.discover(FakeReg({APP: EXE}), is_file=lambda p: True, version_of=lambda p: "16.0.1.2")
        self.assertEqual(r["status"], "found")
        self.assertEqual(excel.ExcelDescriptor.parse(r["descriptor"]).method, "app_paths")

    def test_found_via_click_to_run(self):
        r = excel.discover(FakeReg({C2R: r"C:\Program Files\Microsoft Office"}), is_file=lambda p: True,
                           version_of=lambda p: "16.0.1.2")
        self.assertEqual(r["descriptor"]["method"], "click_to_run")

    def test_registered_but_file_missing_is_not_found(self):
        r = excel.discover(FakeReg({APP: EXE}), is_file=lambda p: False, version_of=lambda p: "1.0")
        self.assertEqual(r["status"], "not_found")

    def test_not_found(self):
        self.assertEqual(excel.discover(FakeReg(), is_file=lambda p: False)["status"], "not_found")

    def test_query_failure_is_never_not_found(self):
        r = excel.discover(FakeReg(fail=True))
        self.assertEqual(r["status"], "failed")
        self.assertIn("PermissionError", r["reason"])

    def test_version_failure_is_failed(self):
        def boom(p):
            raise OSError("no version resource")
        r = excel.discover(FakeReg({APP: EXE}), is_file=lambda p: True, version_of=boom)
        self.assertEqual(r["status"], "failed")


class Descriptor(unittest.TestCase):
    def test_rejects(self):
        for bad in ({**DESC, "schema": "x"}, {**DESC, "executable": "excel.exe"},
                    {**DESC, "executable": r"C:\x\cmd.exe"}, {**DESC, "executable": EXE + '" /c calc'},
                    {**DESC, "version": "latest"}, {**DESC, "method": "guess"}, {**DESC, "args": ["/x"]}, "x"):
            with self.assertRaises(excel.DescriptorError):
                excel.ExcelDescriptor.parse(bad)


class Probe:
    def __init__(self, seq):
        self.seq, self.i = seq, 0

    def state(self, pid):
        s = self.seq[min(self.i, len(self.seq) - 1)]
        self.i += 1
        return s


def fast(**kw):
    return dict(is_file=lambda p: True, launcher=lambda p: 4242, timeout_s=2, poll_s=0.01, stable_s=0.03, **kw)


class Start(unittest.TestCase):
    def test_workbook_ready_from_descriptor_without_discovery(self):
        r = excel.start(DESC, windows=Probe(["none", "workbook_ready"]), **fast())
        self.assertEqual((r["status"], r["pid"], r["start_screen_dismissed"]), ("ready", 4242, False))

    def test_start_screen_dismissed_through_engine(self):
        probe = Probe(["start_screen"] * 6 + ["workbook_ready"])
        calls = []
        r = excel.start(DESC, windows=probe, dismiss_start_screen=lambda: calls.append(1) or {"outcome": "completed_unverified"}, **fast())
        self.assertEqual(r["status"], "ready")
        self.assertEqual(calls, [1])  # dismissed exactly once, never repeated

    def test_engine_failure_on_start_screen(self):
        r = excel.start(DESC, windows=Probe(["start_screen"]), dismiss_start_screen=lambda: {"outcome": "uncertain", "code": "x"}, **fast())
        d = r["diagnostic"]
        self.assertEqual((d["error_code"], d["effect_state"]), ("EXCEL-START-SCREEN-UNRESOLVED", "partial"))
        self.assertEqual(r["pid"], 4242)

    def test_timeout_reports_partial_effect(self):
        r = excel.start(DESC, windows=Probe(["none"]), **fast())
        self.assertEqual(r["diagnostic"]["error_code"], "EXCEL-START-TIMEOUT")
        self.assertEqual(r["diagnostic"]["effect_state"], "partial")
        self.assertTrue(r["message"].splitlines()[-1].startswith("Code: EXCEL-START-TIMEOUT |"))

    def test_invalid_descriptor_is_a_contract_error_before_launch(self):
        launched = []
        r = excel.start({**DESC, "schema": "v0"}, windows=Probe(["none"]),
                        **{**fast(), "launcher": lambda p: launched.append(p) or 1})
        self.assertEqual(r["diagnostic"]["error_code"], "CONTRACT-EXCEL-DESCRIPTOR")
        self.assertEqual(r["diagnostic"]["boundary"]["consumer"], "RR-EXCEL-START")
        self.assertEqual(launched, [])

    def test_missing_executable_and_launch_failure(self):
        r = excel.start(DESC, **{**fast(), "is_file": lambda p: False})
        self.assertEqual(r["diagnostic"]["error_code"], "EXCEL-EXECUTABLE-MISSING")

        def deny(p):
            raise PermissionError("blocked")
        r = excel.start(DESC, windows=Probe(["none"]), **{**fast(), "launcher": deny})
        self.assertEqual(r["diagnostic"]["error_code"], "EXCEL-START-FAILED")


class Flow(unittest.TestCase):
    def test_routing(self):
        started = []

        def start_fn(desc, correlation_id=None):
            started.append((desc, correlation_id))
            return {"status": "ready"}

        r = excel.new_workbook(lambda: {"status": "found", "descriptor": DESC}, start_fn, correlation_id="k")
        self.assertEqual((r["status"], started), ("ready", [(DESC, "k")]))

        for disc, code in (({"status": "not_found"}, "EXCEL-NOT-FOUND"),
                           ({"status": "failed", "reason": "x"}, "EXCEL-DISCOVERY-FAILED"),
                           ({"status": "maybe"}, "CONTRACT-EXCEL-DESCRIPTOR"),
                           ("garbage", "CONTRACT-EXCEL-DESCRIPTOR")):
            started.clear()
            r = excel.new_workbook(lambda: disc, start_fn, correlation_id="k")
            self.assertEqual(r["diagnostic"]["error_code"], code)
            self.assertEqual(r["diagnostic"]["correlation_id"], "k")
            self.assertEqual(started, [])
            self.assertEqual(dg.validate(r["diagnostic"]), [])

    def test_found_with_invalid_descriptor_is_caught_at_start_boundary(self):
        r = excel.new_workbook(lambda: {"status": "found", "descriptor": {"schema": "?"}},
                               lambda d, correlation_id=None: excel.start(d, correlation_id=correlation_id, **fast()))
        self.assertEqual(r["diagnostic"]["error_code"], "CONTRACT-EXCEL-DESCRIPTOR")


class RunnerResultMapping(unittest.TestCase):
    def test_existing_runner_codes_map_to_catalog(self):
        cases = {("refused", "session_busy"): "SESSION-BUSY", ("refused", "output_exists"): "OUTPUT-EXISTS",
                 ("precondition_missing", "excel_not_installed"): "EXCEL-NOT-FOUND",
                 ("uncertain", "step_failed_after_effect"): "STEP-UNCERTAIN", ("failed", "target_not_found"): "STEP-FAILED",
                 ("refused", "platform_incompatible"): "PROCEDURE-INCOMPATIBLE", ("refuted", "cells_mismatch"): "RESULT-NOT-VERIFIED",
                 ("login_required", "login_required"): "LOGIN-REQUIRED", ("error", "brand_new_code"): "UNMAPPED"}
        for (state, code), expect in cases.items():
            d = diagnose.for_result({"state": state, "code": code})
            self.assertEqual(d.error_code, expect, (state, code))
            self.assertEqual(dg.validate(d.to_dict()), [])
        self.assertIsNone(diagnose.for_result({"state": "verified"}))
        res = diagnose.attach({"state": "uncertain", "code": "x", "job": {"failed_step": 7}})
        self.assertIn("step 7", res["message"])
        self.assertTrue(res["message"].splitlines()[-1].startswith("Code: STEP-UNCERTAIN |"))

    def test_foreign_input_during_replay_has_its_own_code(self):
        for state in ("failed", "uncertain"):
            res = diagnose.attach({"state": state, "code": "user_input_detected", "failed_step": 0,
                                   "detail": "keyboard input from hardware during the run after 3 chars"})
            self.assertEqual(res["diagnostic"]["error_code"], "RUN-INTERRUPTED-BY-INPUT")
            self.assertEqual(dg.validate(res["diagnostic"]), [])
            self.assertIn("keyboard or mouse", res["message"])
            self.assertEqual(res["diagnostic"]["params"]["reason"], "keyboard input from hardware during the run after 3 chars")
            self.assertIn("after 3 chars", res["message"])
            self.assertTrue(res["message"].splitlines()[-1].startswith("Code: RUN-INTERRUPTED-BY-INPUT | Modules: RR-ENGINE-EXEC"))
        d = diagnose.for_result({"state": "refused", "code": "input_monitor_unavailable"})
        self.assertEqual((d.error_code, d.reported_by), ("SESSION-UNAVAILABLE", "RR-ENGINE-EXEC"))


if __name__ == "__main__":
    unittest.main()
