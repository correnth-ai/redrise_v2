"""Browser opening routine (runner/redrise_runner/browser_open.py) with a fake
window/UI Automation probe and fake launchers: confirmation rules, fail-closed
cases and diagnostics. No real browser is started (simulated component check).

    cd tests/runtime && <lab python> -B -m unittest test_browser_open
"""

import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runner"))
sys.path.insert(0, str(ROOT / "contracts" / "python"))

from redrise_runner import agent, browser_open, browsers  # noqa: E402

EDGE = {"id": "msedge", "name": "Microsoft Edge", "path": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "version": "1.0", "source": "test", "homologated": False}


@dataclass
class Doc:
    url: str | None
    title: str | None


@dataclass
class Strip:
    count: int
    selected: str | None
    names: list


class FakeProbe:
    """Windows before the request; `after` applies once the launcher was called."""

    def __init__(self, before: dict, after: dict | None = None, appear_after_polls: int = 0, prompt: bool = False):
        self.state, self.after, self.wait = before, after, appear_after_polls
        self.launches = 0
        self.closed = False
        self.prompt = prompt  # the first request raises "Open with"; the browser appears on the next one
        self.open_prompts: list[int] = [50]  # an unrelated dialog already on screen
        self.closed_prompts: list[int] = []

    def trigger(self):
        self.launches += 1
        if self.prompt and self.launches == 1:
            self.open_prompts.append(77)

    @property
    def launched(self):
        return self.launches >= (2 if self.prompt else 1)

    def _current(self):
        if self.launched and self.after is not None:
            if self.wait <= 0:
                return self.after
            self.wait -= 1
        return self.state

    def windows(self, images):
        return [{"hwnd": h, "pid": 10 + h, "image": w["image"], "exe": w["exe"]} for h, w in self._current().items() if w["image"] in images]

    def strip(self, hwnd):
        w = self._current().get(hwnd)
        return Strip(w["tabs"], w["sel"], []) if w and w["tabs"] is not None else None

    def address(self, hwnd):
        w = self._current().get(hwnd)
        return w["addr"] if w else None

    def document(self, hwnd):
        w = self._current().get(hwnd)
        if not w:
            return None
        docs = w["doc"]
        if isinstance(docs, list):  # successive reads: e.g. previous page, then the target
            return Doc(docs.pop(0) if len(docs) > 1 else docs[0], w["sel"])
        return Doc(w["addr"] if docs is None else docs, w["sel"])

    def prompts(self):
        return list(self.open_prompts)

    def close_prompt(self, hwnd):
        self.closed_prompts.append(hwnd)
        self.open_prompts.remove(hwnd)

    def close(self):
        self.closed = True


def win(tabs, addr, image="msedge.exe", sel="Pagina", doc=None):
    return {"tabs": tabs, "addr": addr, "image": image, "sel": sel, "exe": rf"C:\X\{image}", "doc": doc}


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def run(config, probe, resolve=lambda b: EDGE if b == "msedge" else None, timeout=30.0, fail_launch=False):
    clock = Clock()
    calls = []

    def opener(*a):
        calls.append(a)
        if fail_launch:
            raise OSError("access denied")
        probe.trigger()

    out = browser_open.run(config, probe_factory=lambda: probe, resolve=resolve, open_site=opener, open_html=opener,
                           open_file_in=opener, timeout_s=timeout, clock=clock, sleep=clock.sleep)
    return out, calls, clock


SITE = {"origin": "site", "browser": "msedge", "url": "https://pedidos.exemplo.test/", "path": None, "isolated": True}


class Site(unittest.TestCase):
    def test_new_tab_in_running_browser_is_verified_with_context(self):
        p = FakeProbe({1: win(3, "pessoal.exemplo.test")}, {1: win(4, "pedidos.exemplo.test")})
        out, calls, _ = run(SITE, p)
        self.assertEqual(out["state"], "verified")
        self.assertEqual(calls, [(EDGE, SITE["url"])])
        c = out["context"]
        self.assertEqual((c["browser_id"], c["hwnd"], c["new_window"], c["address"]), ("msedge", 1, False, "pedidos.exemplo.test"))
        self.assertEqual((c["confirmation"], c["opened_by"]), ("page_ready", "chosen_browser"))
        self.assertTrue(p.closed)

    def test_error_page_is_tab_open_not_verified(self):
        # Edge 156 probe: a load error commits chrome-error://chromewebdata/ while the address field shows the target.
        p = FakeProbe({1: win(3, "pessoal.exemplo.test")},
                      {1: win(4, "pedidos.exemplo.test", doc="chrome-error://chromewebdata/")})
        out, _, clock = run(SITE, p)
        self.assertEqual((out["state"], out["code"]), ("failed", "browser_page_not_ready"))
        c = out["context"]
        self.assertEqual((c["confirmation"], c["page_url"], c["hwnd"]), ("tab_open", "chrome-error://chromewebdata/", 1))
        self.assertIn("browser error page", out["detail"])
        self.assertGreaterEqual(clock.t, 30)  # waited for the page within the same 30 s budget, no retry

    def test_previous_page_document_is_not_taken_as_ready(self):
        p = FakeProbe({1: win(1, "pessoal.exemplo.test")},
                      {1: win(2, "pedidos.exemplo.test", doc=["https://pessoal.exemplo.test/", "https://pessoal.exemplo.test/",
                                                              "https://pedidos.exemplo.test/"])})
        out, _, clock = run(SITE, p)
        self.assertEqual((out["state"], out["context"]["page_url"]), ("verified", "https://pedidos.exemplo.test/"))
        self.assertLess(clock.t, 2)

    def test_context_title_is_read_after_the_page_loaded(self):
        p = FakeProbe({1: win(1, "pessoal.exemplo.test")}, {1: win(2, "pedidos.exemplo.test", sel="Pagina final")})
        real_strip, reads = p.strip, []
        def strip(h):
            s = real_strip(h)
            reads.append(s)
            return Strip(s.count, "Sem nome" if len(reads) <= 2 else s.selected, [])
        p.strip = strip
        out, _, _ = run(SITE, p)
        self.assertEqual((out["state"], out["context"]["tab_title"]), ("verified", "Pagina final"))

    def test_page_never_committed_is_not_ready(self):
        p = FakeProbe({}, {1: win(1, "pedidos.exemplo.test", doc="")})
        out, _, _ = run(SITE, p, timeout=3)
        self.assertEqual((out["code"], out["context"]["confirmation"]), ("browser_page_not_ready", "tab_open"))
        self.assertIn("document not at the target", out["detail"])

    def test_new_window_when_browser_was_closed(self):
        p = FakeProbe({}, {7: win(1, "https://pedidos.exemplo.test/inicio")}, appear_after_polls=8)
        out, _, clock = run(SITE, p)
        self.assertEqual(out["state"], "verified")
        self.assertTrue(out["context"]["new_window"])
        self.assertLess(clock.t, 30)

    def test_personal_tab_already_at_target_is_not_taken(self):
        # The personal window already shows the address but gained no tab: never confirmed by coincidence.
        p = FakeProbe({1: win(2, "pedidos.exemplo.test")}, {1: win(2, "pedidos.exemplo.test")})
        out, _, clock = run(SITE, p)
        self.assertEqual((out["state"], out["code"]), ("failed", "browser_open_unconfirmed"))
        self.assertGreaterEqual(clock.t, 30)
        self.assertNotIn("context", out)

    def test_other_site_or_other_browser_is_not_confirmation(self):
        p = FakeProbe({}, {1: win(1, "outro.exemplo.test"), 2: win(1, "pedidos.exemplo.test", image="chrome.exe")})
        out, _, _ = run(SITE, p, timeout=2)
        self.assertEqual((out["state"], out["code"]), ("failed", "browser_open_unconfirmed"))

    def test_unreadable_tab_strip_fails_closed(self):
        p = FakeProbe({1: win(None, "x")}, {1: win(None, "pedidos.exemplo.test")})
        out, _, _ = run(SITE, p, timeout=1)
        self.assertEqual(out["code"], "browser_open_unconfirmed")

    def test_missing_browser_refused_before_opening_no_substitution(self):
        p = FakeProbe({})
        out, calls, _ = run({**SITE, "browser": "chrome"}, p)
        self.assertEqual((out["state"], out["code"], calls), ("refused", "browser_not_found", []))

    def test_launch_refused_by_windows(self):
        out, _, _ = run(SITE, FakeProbe({}), fail_launch=True)
        self.assertEqual((out["state"], out["code"]), ("failed", "browser_open_failed"))

    def test_without_ui_automation_nothing_is_opened(self):
        calls = []
        out = browser_open.run(SITE, probe_factory=lambda: (_ for _ in ()).throw(OSError("no uia")),
                               resolve=lambda b: EDGE, open_site=lambda *a: calls.append(a))
        self.assertEqual((out["state"], out["code"], calls), ("refused", "browser_uia_unavailable", []))


class Html(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = Path(self.tmp.name) / "Manual de Teste.html"
        self.file.write_text("<title>t</title>", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_identifies_the_browser_where_the_file_opened(self):
        url = "file:///" + str(self.file).replace("\\", "/").replace(" ", "%20")
        p = FakeProbe({1: win(2, "pessoal.exemplo.test", image="chrome.exe")},
                      {1: win(2, "pessoal.exemplo.test", image="chrome.exe"), 9: win(5, "x"), 4: win(3, url, image="msedge.exe")})
        p.after[4]["exe"] = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        p.state[4] = win(2, "y")  # Edge already open with 2 tabs
        out, calls, _ = run({"origin": "html", "browser": None, "url": None, "path": str(self.file), "isolated": True}, p)
        self.assertEqual(out["state"], "verified")
        self.assertEqual(calls, [(str(self.file),)])
        self.assertEqual((out["context"]["browser_id"], out["context"]["hwnd"]), ("msedge", 4))
        self.assertEqual((out["context"]["opened_by"], out["context"]["confirmation"]), ("association", "page_ready"))

    def _url(self):
        return "file:///" + str(self.file).replace("\\", "/").replace(" ", "%20")

    def test_open_with_prompt_is_cancelled_and_file_opens_in_edge(self):
        p = FakeProbe({}, {4: win(1, self._url(), image="msedge.exe")}, prompt=True)
        out, calls, _ = run({"origin": "html", "path": str(self.file), "isolated": True}, p)
        self.assertEqual(out["state"], "verified")
        self.assertEqual(calls, [(str(self.file),), (EDGE, str(self.file))])
        self.assertEqual(p.closed_prompts, [77])  # only the dialog raised by this request; 50 untouched
        self.assertEqual((out["context"]["opened_by"], out["context"]["browser_id"]), ("default_browser_after_prompt", "msedge"))

    def test_identifies_brave_where_the_association_opened_the_file(self):
        p = FakeProbe({}, {6: win(1, self._url(), image="brave.exe")})
        p.after[6]["exe"] = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
        out, _, _ = run({"origin": "html", "path": str(self.file), "isolated": True}, p)
        self.assertEqual(out["state"], "verified")
        c = out["context"]
        self.assertEqual((c["browser_id"], c["browser_name"], c["opened_by"]), ("brave", "Brave", "association"))

    def test_brave_is_never_a_site_choice(self):
        out, calls, _ = run({**SITE, "browser": "brave"}, FakeProbe({}), resolve=browsers.resolve)
        self.assertEqual((out["state"], out["code"], calls), ("refused", "browser_not_found", []))
        self.assertNotIn("brave", {b["id"] for b in browsers.discover()["browsers"]})

    def test_open_with_prompt_without_edge_is_refused(self):
        p = FakeProbe({}, {4: win(1, self._url())}, prompt=True)
        out, calls, _ = run({"origin": "html", "path": str(self.file), "isolated": True}, p, resolve=lambda b: None)
        self.assertEqual((out["state"], out["code"], len(calls)), ("refused", "browser_not_found", 1))
        self.assertEqual(p.closed_prompts, [77])

    def test_missing_file_refused_before_opening(self):
        out, calls, _ = run({"origin": "html", "path": str(self.file) + ".nao", "isolated": True}, FakeProbe({}))
        self.assertEqual((out["state"], out["code"], calls), ("refused", "input_missing", []))


class Matching(unittest.TestCase):
    def test_site_host_rules(self):
        m = browser_open.site_matches
        self.assertTrue(m("pedidos.exemplo.test", "https://pedidos.exemplo.test/"))
        self.assertTrue(m("https://www.pedidos.exemplo.test/login?x=1", "https://pedidos.exemplo.test/"))
        self.assertFalse(m("pedidos.exemplo.test.mal.test", "https://pedidos.exemplo.test/"))
        self.assertFalse(m(None, "https://pedidos.exemplo.test/"))
        self.assertFalse(m("", "https://pedidos.exemplo.test/"))

    def test_html_path_rules(self):
        m = browser_open.html_matches
        self.assertTrue(m("file:///C:/Exemplos/Manual%20A.html", r"C:\Exemplos\Manual A.html"))
        self.assertTrue(m("C:/exemplos/manual a.html", r"C:\Exemplos\Manual A.html"))
        self.assertFalse(m("file:///C:/Exemplos/outro.html", r"C:\Exemplos\Manual A.html"))

    def test_classify_known_browsers(self):
        c = browsers.classify
        self.assertEqual(c(r"C:\Program Files\Google\Chrome\Application\chrome.exe"), "chrome")
        self.assertEqual(c(r"C:\Users\u\AppData\Local\Chromium\Application\chrome.exe"), "chromium")
        self.assertIsNone(c(r"C:\Users\u\AppData\Local\Programs\@redrise\browsers\chromium-1\chrome-win\chrome.exe".replace("chromium-1", "pw")))


class Diagnostics(unittest.TestCase):
    def test_result_codes_map_to_browser_diagnostics(self):
        cases = {("failed", "browser_open_unconfirmed"): ("BROWSER-OPEN-UNCONFIRMED", "unknown"),
                 ("failed", "browser_page_not_ready"): ("BROWSER-PAGE-NOT-READY", "partial"),
                 ("failed", "browser_open_failed"): ("BROWSER-OPEN-FAILED", "none"),
                 ("refused", "browser_not_found"): ("BROWSER-NOT-FOUND", "none"),
                 ("refused", "browser_uia_unavailable"): ("BROWSER-IDENTIFY-UNAVAILABLE", "none"),
                 ("refused", "input_missing"): ("INPUT-FILE-MISSING", "none")}
        for (state, code), (ecode, effect) in cases.items():
            r = agent.to_result({"state": state, "code": code, "detail": "d"}, "cid")
            self.assertEqual((r["state"], r["diagnostic"]["error_code"], r["diagnostic"]["effect_state"]), (state, ecode, effect))
            self.assertFalse(r["verified"])

    def test_verified_result_carries_context_for_the_next_routine(self):
        r = agent.to_result({"state": "verified", "verified": True, "context": {"hwnd": 5, "browser_id": "msedge"}}, "cid")
        self.assertEqual((r["state"], r["verified"], r["details"]["context"]["hwnd"], r["diagnostic"]), ("verified", True, 5, None))


if __name__ == "__main__":
    unittest.main()
