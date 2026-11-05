"""Opening a registered destination (runner/redrise_runner/app_open.py) with fake
Start menu, windows and launcher: list filtering, preparation that opens nothing,
confirmation rules and diagnostics. Nothing is started (simulated component check).

    cd tests/runtime && <lab python> -B -m unittest test_app_open
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runner"))
sys.path.insert(0, str(ROOT / "contracts" / "python"))

from redrise_runner import agent, app_open  # noqa: E402

START = [{"Name": "Bloco de Notas", "AppID": "Microsoft.WindowsNotepad_8wekyb3d8bbwe!App"},
         {"Name": "Calculadora", "AppID": "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"},
         {"Name": "Microsoft Edge", "AppID": "MSEdge"},
         {"Name": "Site do fabricante", "AppID": "https://exemplo.test/"},
         {"Name": "Manual", "AppID": r"C:\Programas\Ferramenta\manual.pdf"},
         {"Name": "Remover Ferramenta", "AppID": r"C:\Programas\Ferramenta\unins000.exe"},
         {"Name": "Ferramenta", "AppID": r"C:\Programas\Ferramenta\ferramenta.exe"}]
EDGE = {"id": "msedge", "name": "Microsoft Edge"}


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


class DiscoverTest(unittest.TestCase):
    def test_lists_what_starts_a_program_and_merges_browsers(self):
        out = app_open.discover(lambda: START, lambda: [EDGE])
        self.assertEqual([a["name"] for a in out], ["Bloco de Notas", "Calculadora", "Ferramenta", "Microsoft Edge"])
        self.assertEqual(out[3], {"id": "browser:msedge", "name": "Microsoft Edge", "browser_id": "msedge"})

    def test_a_failed_query_is_not_an_empty_list(self):
        def boom():
            raise OSError("Get-StartApps exit 1")
        with self.assertRaises(OSError):
            app_open.discover(boom, lambda: [])


class PrepareTest(unittest.TestCase):
    def setUp(self):
        self.checks = []

    def report(self, check, state, detail=None):
        self.checks.append((check, state))

    def test_app_resolved_without_opening(self):
        listed = lambda: [{"id": "App!1", "name": "Calculadora"}]  # noqa: E731
        out = app_open.prepare_app({"target": {"kind": "app", "app_id": "App!1", "name": "Calculadora"}}, self.report, listed)
        self.assertEqual(out["state"], "verified")
        self.assertEqual(out["context"]["resolved"], {"how": "start_menu", "launch": "shell:AppsFolder\\App!1", "name": "Calculadora", "package": "App"})
        self.assertEqual(self.checks, [("target", "running"), ("target", "ok"), ("launch", "ok")])

    def test_app_gone_from_this_station(self):
        out = app_open.prepare_app({"target": {"kind": "app", "app_id": "App!1", "name": "Calculadora"}}, self.report, lambda: [])
        self.assertEqual((out["state"], out["code"], out["detail"]), ("failed", "app_target_not_found", "Calculadora"))
        self.assertEqual(self.checks[-1], ("target", "failed"))

    def test_file_exists_and_has_a_program(self):
        with tempfile.TemporaryDirectory() as d:
            doc = Path(d) / "planilha.xlsx"
            doc.write_text("x")
            ok = app_open.prepare_app({"target": {"kind": "file", "path": str(doc), "name": doc.name}}, self.report, associated=lambda p: r"C:\Office\EXCEL.EXE")
            self.assertEqual(ok["context"]["resolved"]["how"], "association")
            no = app_open.prepare_app({"target": {"kind": "file", "path": str(doc), "name": doc.name}}, self.report, associated=lambda p: None)
            self.assertEqual(no["code"], "app_no_association")
            exe = Path(d) / "ferramenta.exe"
            exe.write_text("x")
            prog = app_open.prepare_app({"target": {"kind": "file", "path": str(exe), "name": exe.name}}, self.report, associated=lambda p: None)
            self.assertEqual(prog["context"]["resolved"]["how"], "program")
        missing = app_open.prepare_app({"target": {"kind": "file", "path": r"C:\nao\existe.xlsx", "name": "x"}}, self.report)
        self.assertEqual(missing["code"], "app_target_not_found")

    def test_browser_checks_only(self):
        site = {"origin": "site", "browser": "msedge", "url": "https://x.test/", "path": None, "isolated": True}
        ok = app_open.prepare_browser(site, self.report, lambda b: {"id": b, "name": "Microsoft Edge"})
        self.assertEqual(ok["state"], "verified")
        self.assertEqual(app_open.prepare_browser(site, self.report, lambda b: None)["code"], "browser_not_found")
        self.assertEqual(app_open.prepare_browser({"origin": "html", "path": r"C:\nao\existe.html"}, self.report)["code"], "input_missing")


def window(hwnd, image="calc.exe", pid=None):
    return {"hwnd": hwnd, "pid": pid if pid is not None else hwnd * 10, "process_image": image, "class": "C"}


class OpenTest(unittest.TestCase):
    def run_open(self, resolved, before, after, fg_before=1, fg_after=1, launch=None, timeout_s=2.0, pids=None, paths=None):
        launched, clock = [], Clock()
        state = {"opened": False}
        pids = pids or (set(), set())

        def do_launch(t):
            if launch:
                launch(t)
            launched.append(t)
            state["opened"] = True
        out = app_open.open_target(resolved, do_launch, lambda: after if state["opened"] else before,
                                   lambda: fg_after if state["opened"] else fg_before, lambda: pids[1] if state["opened"] else pids[0],
                                   lambda pid: (paths or {}).get(pid, ""), timeout_s, clock.now, clock.sleep)
        return out, launched

    def test_new_window_of_the_program_confirms_and_exact_target_is_launched(self):
        r = {"how": "program", "launch": r"C:\Programas\calc.exe", "name": "Calculadora", "image": "calc.exe"}
        out, launched = self.run_open(r, [window(1, "outro.exe")], [window(1, "outro.exe"), window(2)], fg_after=2)
        self.assertEqual(out["state"], "verified")
        self.assertEqual((out["context"]["opened"]["hwnd"], out["context"]["opened"]["new_window"]), (2, True))
        self.assertEqual(launched, [r["launch"]])

    def test_program_already_open_coming_to_the_front_confirms(self):
        r = {"how": "program", "launch": r"C:\Programas\calc.exe", "name": "Calculadora", "image": "calc.exe"}
        out, _ = self.run_open(r, [window(1, "outro.exe"), window(5)], [window(1, "outro.exe"), window(5)], fg_after=5)
        self.assertEqual((out["state"], out["context"]["opened"]["new_window"]), ("verified", False))

    def test_a_window_of_another_program_confirms_nothing(self):
        r = {"how": "program", "launch": r"C:\Programas\ferramenta.exe", "name": "Ferramenta", "image": "ferramenta.exe"}
        out, _ = self.run_open(r, [window(1)], [window(1), window(2, "outro.exe")], fg_after=2)
        self.assertEqual((out["state"], out["code"]), ("uncertain", "app_open_unconfirmed"))

    def test_store_app_through_the_frame_host_needs_its_package_running(self):
        r = {"how": "start_menu", "launch": "shell:AppsFolder\\Microsoft.Calc_x!App", "name": "Calculadora", "package": "microsoft.calc"}
        frame = window(2, app_open.FRAME_HOST, pid=20)
        ok, _ = self.run_open(r, [window(1, "outro.exe")], [window(1, "outro.exe"), frame], fg_after=2, pids=({20}, {20, 99}),
                              paths={99: r"C:\Program Files\WindowsApps\Microsoft.Calc_11_x64__x\CalculatorApp.exe"})
        self.assertEqual(ok["state"], "verified")
        no, _ = self.run_open(r, [window(1, "outro.exe")], [window(1, "outro.exe"), frame], fg_after=2, pids=({20}, {20}), paths={20: r"C:\Windows\ApplicationFrameHost.exe"})
        self.assertEqual(no["state"], "uncertain")

    def test_unknown_program_needs_a_process_that_did_not_exist(self):
        r = {"how": "start_menu", "launch": "shell:AppsFolder\\Chrome", "name": "Programa"}
        toast = window(2, "shellexperiencehost.exe", pid=7)
        no, _ = self.run_open(r, [window(1)], [window(1), toast], fg_after=2, pids=({7, 10}, {7, 10}))
        self.assertEqual(no["state"], "uncertain")  # a toast or a shell dialog is not the app
        switched, _ = self.run_open(r, [window(1), window(5)], [window(1), window(5)], fg_after=5, pids=({10, 50}, {10, 50}))
        self.assertEqual(switched["state"], "uncertain")  # someone switching windows is not the app
        behind, _ = self.run_open(r, [window(1)], [window(1), window(3, "outro.exe", pid=30)], fg_after=1, pids=({10}, {10, 30}))
        self.assertEqual(behind["state"], "uncertain")  # another program that happened to start, not in front
        yes, _ = self.run_open(r, [window(1)], [window(1), window(3, "programa.exe", pid=30)], fg_after=3, pids=({10}, {10, 30}))
        self.assertEqual(yes["state"], "verified")

    def test_with_a_title_only_the_window_showing_it_counts(self):
        r = {"how": "mail", "launch": "outlook", "name": "Outlook", "image": "outlook.exe", "title": "Pedidos: Avisar"}
        main, compose = window(2, "outlook.exe"), window(3, "outlook.exe")
        titles = {2: "Caixa de Entrada - Outlook", 3: "Pedidos: Avisar - Mensagem (HTML)"}
        clock = Clock()

        def go(after):
            state = {"on": False}
            return app_open.open_target(r, lambda t: state.update(on=True), lambda: after if state["on"] else [window(1, "x.exe")], lambda: after[-1]["hwnd"] if state["on"] else 1,
                                        lambda: set(), lambda pid: "", 2.0, clock.now, clock.sleep, lambda h: titles.get(h, ""))
        self.assertEqual(go([window(1, "x.exe"), main])["state"], "uncertain")
        self.assertEqual(go([window(1, "x.exe"), main, compose])["context"]["opened"]["hwnd"], 3)

    def test_nothing_seen_is_uncertain_never_a_second_launch(self):
        r = {"how": "association", "launch": r"C:\x\a.xlsx", "name": "a.xlsx", "image": "excel.exe"}
        out, launched = self.run_open(r, [window(1)], [window(1)])
        self.assertEqual((out["state"], out["code"]), ("uncertain", "app_open_unconfirmed"))
        self.assertEqual(len(launched), 1)

    def test_refused_by_windows_names_the_destination(self):
        def refuse(t):
            raise OSError("no")
        out, launched = self.run_open({"how": "association", "launch": "x", "name": "a.xlsx"}, [window(1)], [window(1)], launch=refuse)
        self.assertEqual((out["state"], out["code"], out["detail"], launched), ("failed", "app_open_failed", "a.xlsx", []))


class ResolveTest(unittest.TestCase):
    def test_what_identifies_the_window(self):
        listed = lambda: [{"id": "Microsoft.Calc_8we!App", "name": "C"}, {"id": r"{GUID}\Tool\tool.EXE", "name": "T"}, {"id": "Chrome", "name": "G"}]  # noqa: E731
        calc = app_open.resolve_target({"kind": "app", "app_id": "Microsoft.Calc_8we!App", "name": "C"}, listed)
        self.assertEqual((calc["package"], calc.get("image")), ("Microsoft.Calc", None))
        self.assertEqual(app_open.resolve_target({"kind": "app", "app_id": r"{GUID}\Tool\tool.EXE", "name": "T"}, listed)["image"], "tool.exe")
        word = app_open.resolve_target({"kind": "app", "app_id": "Microsoft.Office.WINWORD.EXE.15", "name": "W"}, lambda: [{"id": "Microsoft.Office.WINWORD.EXE.15", "name": "W"}])
        self.assertEqual(word["image"], "winword.exe")
        bare = app_open.resolve_target({"kind": "app", "app_id": "Chrome", "name": "G"}, listed)
        self.assertNotIn("image", bare)
        self.assertNotIn("package", bare)
        with tempfile.TemporaryDirectory() as d:
            doc = Path(d) / "a.xlsx"
            doc.write_text("x")
            got = app_open.resolve_target({"kind": "file", "path": str(doc), "name": "a.xlsx"}, associated=lambda p: r"C:\Office\EXCEL.EXE")
            self.assertEqual((got["how"], got["image"]), ("association", "excel.exe"))


class ResultTest(unittest.TestCase):
    def test_results_map_to_diagnostics_with_the_target(self):
        for code, ecode in (("app_target_not_found", "APP-TARGET-NOT-FOUND"), ("app_no_association", "APP-NO-ASSOCIATION"),
                            ("app_open_failed", "APP-OPEN-FAILED"), ("app_open_unconfirmed", "APP-OPEN-UNCONFIRMED")):
            r = agent.to_result({"state": "failed", "code": code, "detail": "Calculadora"}, "cid-1")
            self.assertEqual(r["diagnostic"]["error_code"], ecode)
            self.assertEqual(r["diagnostic"]["params"]["target"], "Calculadora")
            self.assertEqual(r["diagnostic"]["module_hints"], ["RR-APP-OPEN"])

    def test_context_reaches_the_core(self):
        r = agent.to_result({"state": "verified", "verified": True, "context": {"resolved": {"how": "program"}}}, "cid-1")
        self.assertEqual(r["details"]["context"]["resolved"]["how"], "program")


if __name__ == "__main__":
    unittest.main()
