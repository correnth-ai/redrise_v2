"""Template orchestration and verifier tests (fake Engine; no UI).
    cd tests/runtime && <python> -m unittest test_templates
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runner"))
sys.path.insert(0, str(ROOT / "contracts" / "python"))

from redrise_runner import templates, verifiers  # noqa: E402
from redrise_runner.engine import EngineClient  # noqa: E402
from redrise_runner.paths import Layout  # noqa: E402

FAKE = Path(__file__).with_name("fake_engine.py")
LITERAL = "Boas vindas à RedRise! Estamos felizes em tê-los conosco! Esperamos que as automações lhes seja útil!"


def minimal_xlsx(path: Path, cells: dict[str, object]) -> None:
    """Hand-built SpreadsheetML for reader tests (not Engine output)."""
    def c(ref, v):
        if v is None:
            return ""
        if isinstance(v, (int, float)):
            return f'<c r="{ref}"><v>{v}</v></c>'
        return f'<c r="{ref}" t="inlineStr"><is><t>{v}</t></is></c>'
    rows = {}
    for ref, v in cells.items():
        rows.setdefault(ref[1:], []).append(c(ref, v))
    sheet = "".join(f'<row r="{r}">{"".join(cs)}</row>' for r, cs in sorted(rows.items()))
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="P" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="x"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{sheet}</sheetData></worksheet>')


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_text_equals_utf8_and_refutes_mismatch(self):
        p = self.tmp / "Boas_Vindas.txt"
        p.write_bytes(LITERAL.encode("utf-8") + b"\r\n")
        self.assertTrue(verifiers.text_file_equals(p, LITERAL)["verified"])
        p.write_bytes(LITERAL.encode("cp1252"))
        self.assertEqual(verifiers.text_file_equals(p, LITERAL)["code"], "not_utf8")
        p.write_bytes(LITERAL[:-1].encode("utf-8"))
        self.assertFalse(verifiers.text_file_equals(p, LITERAL)["verified"])
        self.assertEqual(verifiers.text_file_equals(self.tmp / "nope.txt", LITERAL)["code"], "file_missing")

    def test_xlsx_number_vs_text(self):
        p = self.tmp / "a.xlsx"
        minimal_xlsx(p, {"A1": "Campo", "B2": "Cliente Teste 01", "B3": 1500})
        ok = verifiers.xlsx_cells(p, {"A1": "Campo", "B2": "Cliente Teste 01", "B3": "number:1500", "C9": None})
        self.assertTrue(ok["verified"], ok)
        minimal_xlsx(p, {"A1": "Campo", "B2": "Cliente Teste 01", "B3": "1500"})
        self.assertFalse(verifiers.xlsx_cells(p, {"B3": "number:1500"})["verified"])
        p.write_bytes(b"not a zip")
        self.assertEqual(verifiers.xlsx_cells(p, {"A1": "x"})["code"], "not_xlsx")

    def test_xlsx_reader_on_real_excel_file_when_available(self):
        lab = Path(os.environ.get("USERPROFILE", "")) / "RedRise-v2-dev" / "proofs" / "p01-engine"
        files = sorted(lab.glob("run-*/saida/resultado_replay.xlsx"))
        if not files:
            self.skipTest("no Excel-written workbook in the lab")
        got = verifiers.read_cells(files[-1], ["A1", "B1", "A2", "A3", "B2", "B3"])
        self.assertEqual(got, {"A1": "Campo", "B1": "Valor", "A2": "Cliente", "A3": "Valor do pedido", "B2": "Cliente Teste 01", "B3": 1500})

    def test_browser_final_url_classification(self):
        rules = [{"prefix": "https://mail.google.com/mail/", "state": "inbox_authenticated", "verified": True},
                 {"prefix": "https://accounts.google.com/", "state": "login_required", "verified": False}]
        other = {"state": "unexpected_page", "verified": False}
        self.assertEqual(verifiers.browser_final_url("https://accounts.google.com/v3/signin?x", rules, other)["state"], "login_required")
        self.assertTrue(verifiers.browser_final_url("https://mail.google.com/mail/u/0/#inbox", rules, other)["verified"])
        self.assertEqual(verifiers.browser_final_url("https://evil.test/", rules, other)["state"], "unexpected_page")
        self.assertEqual(verifiers.browser_final_url(None, rules, other)["code"], "no_final_url")


class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        inst = self.tmp / "install"
        shutil.copytree(ROOT / "templates", inst / "templates")
        self.layout = Layout(inst, inst / "runtime/python", FAKE, self.tmp / "data")
        os.environ["FAKE_ENGINE_MODE"] = "ready"
        self.log = self.tmp / "engine-run.log"
        os.environ["FAKE_ENGINE_LOG"] = str(self.log)
        self.engine = EngineClient([sys.executable, str(FAKE)])
        self.desk = self.tmp / "Desktop"
        self.desk.mkdir()

    def run_t(self, tid, **given):
        return templates.run_template(tid, self.layout, self.engine, given, self.desk)

    def test_installed_templates_are_listed_and_valid_json(self):
        ids = [t["id"] for t in templates.list_templates(self.layout.install_root / "templates")]
        self.assertEqual(ids, ["boas-vindas", "browser-formulario", "excel-pedido", "gmail-acessar", "outlook-abrir"])

    def test_boas_vindas_refuses_existing_file_without_launch_or_engine(self):
        (self.desk / "Boas_Vindas.txt").write_text("old", encoding="utf-8")
        r = self.run_t("boas-vindas")
        self.assertEqual((r["state"], r["code"]), ("refused", "output_exists"))
        self.assertNotIn("launched", r)
        self.assertFalse(self.log.exists())
        self.assertEqual((self.desk / "Boas_Vindas.txt").read_text(encoding="utf-8"), "old")

    def test_boas_vindas_default_output_on_desktop(self):
        os.environ["FAKE_ENGINE_MODE"] = "locked"  # stop before launch, after input resolution
        r = self.run_t("boas-vindas")
        self.assertEqual(r["inputs"]["output_path"], str(self.desk / "Boas_Vindas.txt"))
        self.assertEqual((r["state"], r["code"]), ("refused", "session_unavailable"))
        self.assertNotIn("launched", r)

    def test_excel_missing_inputs_and_absent_workbook(self):
        self.assertEqual(self.run_t("excel-pedido")["code"], "missing_input")
        r = self.run_t("excel-pedido", input_path=str(self.tmp / "nope.xlsx"), output_path=str(self.tmp / "o.xlsx"))
        self.assertIn(r["code"], ("input_missing", "excel_not_installed"))

    def test_unknown_input_and_candidate_template_refused(self):
        self.assertEqual(self.run_t("boas-vindas", evil="x")["code"], "unknown_input")
        self.assertEqual(self.run_t("browser-formulario")["code"], "template_candidate_not_shipped")
        self.assertEqual(self.run_t("does-not-exist")["code"], "template_not_installed")

    def test_check_template_dry_run_launches_nothing(self):
        r = templates.run_template("boas-vindas", self.layout, self.engine, {}, self.desk, dry_run=True)
        self.assertEqual(r["state"], "ready")
        self.assertNotIn("launched", r)
        self.assertFalse(self.log.exists())

    def test_busy_session_refuses_before_launching_the_app(self):
        """P04 review defect: the session lock is taken before the target app
        is launched (a running automation must not lose focus)."""
        from redrise_runner import apps
        from redrise_runner.jobs import session_lock
        launched = []
        orig = apps.launch
        apps.launch = lambda exe, args: launched.append(exe) or 1
        try:
            with session_lock(self.layout.locks_dir):
                r = self.run_t("boas-vindas")
        finally:
            apps.launch = orig
        self.assertEqual((r["state"], r["code"]), ("refused", "session_busy"))
        self.assertEqual(launched, [])
        self.assertFalse(self.log.exists())

    def test_incompatible_procedure_refused_before_launch(self):
        from redrise_runner import apps
        proc = self.layout.install_root / "templates" / "boas-vindas" / "procedure.json"
        j = json.loads(proc.read_text(encoding="utf-8"))
        j["platform"] = "macos-aarch64"
        proc.write_text(json.dumps(j), encoding="utf-8")
        launched = []
        orig = apps.launch
        apps.launch = lambda exe, args: launched.append(exe) or 1
        try:
            r = self.run_t("boas-vindas")
        finally:
            apps.launch = orig
        self.assertEqual((r["state"], r["code"]), ("refused", "platform_incompatible"))
        self.assertEqual(launched, [])

    def test_gmail_without_packaged_browser_is_precondition_missing(self):
        r = self.run_t("gmail-acessar")
        self.assertEqual((r["state"], r["code"]), ("precondition_missing", "browser_not_packaged"))


class EndOfRunApp(unittest.TestCase):
    """An app opened only for the run is closed after a verified result; an
    app already open, or any non-verified result, leaves it open."""

    def setUp(self):
        self.closed: list[list[int]] = []
        self.windows = [{"hwnd": 1, "process_image": "notepad.exe"}, {"hwnd": 2, "process_image": "notepad.exe"},
                        {"hwnd": 3, "process_image": "excel.exe"}]
        self._orig = (verifiers.top_windows, templates.apps.close_windows)
        verifiers.top_windows = lambda: self.windows
        templates.apps.close_windows = lambda h: self.closed.append(h) or []

    def tearDown(self):
        verifiers.top_windows, templates.apps.close_windows = self._orig

    def finish(self, state, was_running=False, template=None):
        res = {}
        opened = {"image": "notepad.exe", "was_running": was_running, "before": {1}}
        f = templates._finisher(template or {}, opened, res, lambda s, **kw: {**res, "state": s, **kw})
        return f(state)

    def test_verified_closes_only_windows_opened_by_the_run(self):
        r = self.finish("verified")
        self.assertEqual(self.closed, [[2]])
        self.assertEqual(r["opened_app"]["action"], "closed")

    def test_app_already_open_stays_open(self):
        self.assertEqual(self.finish("verified", was_running=True)["opened_app"]["action"], "kept_open_was_running")
        self.assertEqual(self.closed, [])

    def test_non_verified_result_stays_open_for_checking(self):
        for state in ("uncertain", "failed", "refuted"):
            self.assertEqual(self.finish(state)["opened_app"]["action"], "kept_open_for_checking")
        self.assertEqual(self.closed, [])

    def test_template_whose_result_is_the_open_app_keeps_it(self):
        r = self.finish("verified", template={"close_opened_app": False})
        self.assertEqual(r["opened_app"]["action"], "kept_open_by_template")
        self.assertEqual(self.closed, [])

    def test_is_running_reads_localized_tasklist_output(self):
        # As the agent runs it: UTF-8 mode, no console (tasklist then writes the
        # localized "no match" message in the OEM code page, e.g. "INFORMAÇÕES").
        import subprocess
        code = ("import sys; sys.path[:0] = [sys.argv[1]]; from redrise_runner import apps; "
                "print(apps.is_running('rr-not-a-running-image.exe'), apps.is_running(sys.argv[2]))")
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", code, str(ROOT / "runner"), Path(sys.executable).name],
                           capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "False True"), r.stderr)

    def test_close_refused_by_the_app_is_reported(self):
        templates.apps.close_windows = lambda h: h
        self.assertEqual(self.finish("verified")["opened_app"]["action"], "close_requested_still_open")


class LaunchedWindow(unittest.TestCase):
    """The run acts only in the window its launch opened (observed: Notepad
    restoring 19 windows from its last session spread the typing across them)."""

    def pick(self, frames, fg, before=(), timeout_s=1.0):
        frames = list(frames)

        def windows():
            return frames.pop(0) if len(frames) > 1 else frames[0]
        return templates.apps.launched_window("notepad.exe", "Notepad", set(before), lambda: fg, windows,
                                              timeout_s=timeout_s, quiet_s=0.05, poll_s=0.01)

    @staticmethod
    def np(*hwnds, cls="Notepad", image="notepad.exe"):
        return [{"hwnd": h, "process_image": image, "class": cls} for h in hwnds]

    def test_waits_for_restored_windows_and_takes_the_foreground_one(self):
        frames = [[], self.np(11), self.np(11, 12), self.np(11, 12, 13)]
        self.assertEqual(self.pick(frames, fg=12), 12)

    def test_without_a_new_foreground_window_takes_the_topmost_new_one(self):
        frames = [self.np(1, 5, 6)]
        self.assertEqual(self.pick(frames, fg=1, before={1}), 5)

    def test_other_apps_classes_and_existing_windows_are_not_candidates(self):
        frames = [self.np(1) + self.np(2, cls="#32770") + self.np(3, image="excel.exe")]
        self.assertIsNone(self.pick(frames, fg=2, before={1}, timeout_s=0.2))


class BoundRun(unittest.TestCase):
    run_t = TemplateTests.run_t

    def setUp(self):
        TemplateTests.setUp(self)
        from redrise_runner import apps
        self.apps, self.after = apps, []
        self._orig = (apps.launch, apps.is_running, apps.launched_window, apps.foreground_window,
                      verifiers.top_windows)
        real = apps.launched_window
        apps.launch = lambda exe, args: 4242
        apps.is_running = lambda image: False
        apps.launched_window = lambda *a, **k: real(*a, timeout_s=0.3, quiet_s=0.05, poll_s=0.01)
        apps.foreground_window = lambda: 0
        state = {"launched": False}
        orig_launch = apps.launch

        def launch(exe, args):
            state["launched"] = True
            return orig_launch(exe, args)
        apps.launch = launch
        verifiers.top_windows = lambda: self.after if state["launched"] else []

    def tearDown(self):
        (self.apps.launch, self.apps.is_running, self.apps.launched_window, self.apps.foreground_window,
         verifiers.top_windows) = self._orig

    def test_engine_is_bound_to_the_window_the_launch_opened(self):
        self.after = [{"hwnd": 7, "pid": 1, "process_image": "notepad.exe", "class": "Notepad"}]
        r = self.run_t("boas-vindas")
        argv = json.loads(self.log.read_text(encoding="utf-8"))
        self.assertEqual(argv[argv.index("--bound-window") + 1], "7")
        self.assertEqual(r["launched"]["window"], 7)

    def test_no_window_from_the_launch_stops_before_the_engine(self):
        from redrise_runner import diagnose
        r = self.run_t("boas-vindas")
        self.assertEqual((r["state"], r["code"]), ("error", "launched_window_not_found"))
        self.assertFalse(self.log.exists())
        self.assertEqual(r["opened_app"]["action"], "kept_open_for_checking")
        self.assertEqual(diagnose.for_result(r).error_code, "APP-WINDOW-NOT-FOUND")


if __name__ == "__main__":
    unittest.main()
