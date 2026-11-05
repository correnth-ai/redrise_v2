"""Follow-up "notify" (runner/redrise_runner/notify_draft.py) with fake launchers and browser
probe: what goes in the draft, how each channel receives it, and that nothing can send. No
application is opened and no account is touched (simulated component check).

    cd tests/runtime && <lab python> -B -m unittest test_notify_draft
"""

import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runner"))
sys.path.insert(0, str(ROOT / "contracts" / "python"))

from redrise_runner import agent, browser_open, notify_draft as nd  # noqa: E402

TO = "pessoa@exemplo.test"
PT = {"subject": "{process}: {step}", "steps": "Etapas", "state_verified": "Verificada", "this_step": "Esta mensagem", "not_run": "N\xe3o executada"}


def execution(**over):
    return {"process_name": "Pedidos", "station_name": "estacao", "context": {"steps": {}},
            "steps": [{"position": 1, "name": "Abrir", "state": "verified"}, {"position": 2, "name": "Avisar", "state": "running"}, {"position": 3, "name": "Depois", "state": None}], **over}


class DraftTest(unittest.TestCase):
    def test_subject_and_body_come_from_the_execution(self):
        subject, body = nd.draft(execution(), PT, 2, ["a.pdf"])
        self.assertEqual(subject, "Pedidos: Avisar")
        for piece in ("1. Abrir: Verificada", "2. Avisar: Esta mensagem", "3. Depois: N\xe3o executada", "a.pdf", "estacao"):
            self.assertIn(piece, body)

    def test_a_long_body_is_shortened_and_says_so(self):
        ex = execution(steps=[{"position": i, "name": f"Etapa {i}", "state": "verified"} for i in range(1, 300)])
        _, body = nd.draft(ex, {"truncated": "(encurtado)"}, 1, [])
        self.assertLessEqual(len(body), nd.MAX_BODY)
        self.assertTrue(body.endswith("(encurtado)"))

    def test_encoded_length_stays_within_what_a_command_or_address_takes(self):
        ex = execution(steps=[{"position": i, "name": "Conferi\xe7\xe3o com acentua\xe7\xe3o " * 3, "state": "verified"} for i in range(1, 80)])
        subject, body = nd.draft(ex, {"truncated": "(encurtado)", "subject": "x" * 400}, 1, [])
        self.assertLessEqual(len(subject), nd.MAX_SUBJECT)
        self.assertLessEqual(len(nd.quote(subject)) + len(nd.quote(body)), nd.MAX_ENCODED)
        self.assertTrue(body.endswith("(encurtado)"))

    def test_names_that_grow_a_lot_when_encoded_never_hang(self):
        name = "\u6f22\u5b57" * 100
        ex = execution(process_name=name, steps=[{"position": 1, "name": name, "state": "verified"}, {"position": 2, "name": name, "state": None}])
        subject, body = nd.draft(ex, {"subject": "{process}", "truncated": name}, 1, [])
        self.assertLessEqual(len(nd.quote(subject)) + len(nd.quote(body)), nd.MAX_ENCODED)

    def test_attachments_only_what_is_here(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Relatorio.pdf").write_bytes(b"%PDF")
            found, named = nd.attachments_of({"context": {"steps": {"1": {"report": {"file": r"..\..\Relatorio.pdf"}}, "2": {"report": {"file": "fora.pdf"}, "output_path": r"C:\nao\existe.txt"}}}}, Path(d))
            self.assertEqual([p.name for p in found], ["Relatorio.pdf"])  # never outside the folder of reports
            self.assertEqual(named, ["fora.pdf", r"C:\nao\existe.txt"])


class AppTest(unittest.TestCase):
    def opener(self, resolved, launch):
        self.opened = resolved
        launch(resolved["launch"])
        return {"state": "verified", "verified": True, "context": {"opened": {"name": resolved["name"], "hwnd": 5, "pid": 6}}}

    def launch(self, exe, args):
        self.started = (exe, args)

    def test_outlook_opens_a_new_message_with_the_file(self):
        out = nd.run_app({"mail_id": "outlook"}, TO, "Assunto com acento \xe7", "Linha 1\nLinha 2", Path(r"C:\x\a.pdf"), launch=self.launch,
                         resolve=lambda a: (Path(r"C:\Office\OUTLOOK.EXE"), "classic outlook"), opener=self.opener)
        self.assertEqual(out["state"], "verified")
        args = self.started[1]
        self.assertEqual(args[:2], ["/c", "ipm.note"])
        self.assertEqual(args[-2:], ["/a", r"C:\x\a.pdf"])
        self.assertTrue(args[3].startswith(TO + "?"))
        self.assertEqual(parse_qs(args[3].split("?", 1)[1])["body"], ["Linha 1\nLinha 2"])
        self.assertEqual(self.opened["image"], "outlook.exe")
        self.assertEqual(self.opened["title"], "Assunto com acento \xe7")  # the window showing this subject, not the main one
        for word in args:
            self.assertNotIn("send", word.lower())

    def test_new_outlook_is_not_treated_as_classic(self):
        out = nd.run_app({"mail_id": "outlook"}, TO, "s", "b", None, launch=self.launch, resolve=lambda a: (Path("olk.exe"), "new outlook"), opener=self.opener)
        self.assertEqual((out["state"], out["code"]), ("refused", "outlook_not_installed"))

    def test_thunderbird_compose(self):
        nd.run_app({"mail_id": "thunderbird"}, TO, "It's", "b", Path(r"C:\x\a.pdf"), launch=self.launch, app_path=lambda n: Path(r"C:\T\thunderbird.exe"), opener=self.opener)
        args = self.started[1]
        self.assertEqual(args[0], "-compose")
        self.assertIn(f"to='{TO}'", args[1])
        self.assertIn("attachment='file:///C:/x/a.pdf'", args[1])
        self.assertNotIn("It's", args[1])  # its list uses single quotes

    def test_default_app_gets_a_mailto(self):
        seen = []
        nd.run_app({"mail_id": "default"}, TO, "S", "B", None, shell=seen.append, mailto=lambda: r"C:\Mail\mail.exe", opener=self.opener)
        self.assertTrue(seen[0].startswith(f"mailto:{TO}?subject=S&body=B"))
        self.assertEqual(self.opened["image"], "mail.exe")
        out = nd.run_app({"mail_id": "default"}, TO, "S", "B", None, mailto=lambda: None, opener=self.opener)
        self.assertEqual(out["code"], "app_no_association")

    def test_clients_listed(self):
        got = nd.mail_clients(lambda a: (Path("o.exe"), "classic outlook"), lambda n: None, lambda: "m.exe")
        self.assertEqual([c["mail_id"] for c in got], ["outlook", "default"])
        self.assertTrue(all(c["name"].isascii() for c in got))
        self.assertEqual(nd.mail_clients(lambda a: (Path("olk.exe"), "new outlook"), lambda n: None, lambda: None), [])


@dataclass
class Doc:
    url: str | None


@dataclass
class Strip:
    count: int
    selected: str | None = None


class Probe:
    def __init__(self, addresses):
        self.addresses, self.opened = list(addresses), False

    def windows(self, images):
        return [{"hwnd": 1, "pid": 2, "image": next(iter(images)), "exe": "x"}]

    def strip(self, hwnd):
        return Strip(2 if self.opened else 1)

    def address(self, hwnd):
        return self.addresses.pop(0) if len(self.addresses) > 1 else self.addresses[0]

    def document(self, hwnd):
        url = self.address(hwnd)
        return Doc(url) if url else None

    def close(self):
        self.closed = True


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


class WebmailTest(unittest.TestCase):
    def go(self, addresses, provider="gmail"):
        probe, clock, urls = Probe(addresses), Clock(), []

        def open_site(browser, url):
            urls.append(url)
            probe.opened = True
        out = nd.run_webmail({"provider": provider, "browser": "msedge"}, TO, "Assunto", "Corpo", lambda: probe, lambda b: {"id": b, "name": "Microsoft Edge"},
                             open_site, 10.0, clock.now, clock.sleep)
        return out, urls

    def test_compose_page_counts_as_prepared(self):
        out, urls = self.go(["https://mail.google.com/mail/u/0/?view=cm"])
        self.assertEqual(out["state"], "verified")
        q = parse_qs(urlsplit(urls[0]).query)
        self.assertEqual((q["to"], q["su"], q["body"], q["view"]), ([TO], ["Assunto"], ["Corpo"], ["cm"]))

    def test_outlook_provider(self):
        out, urls = self.go(["https://outlook.office.com/mail/deeplink/compose"], "outlook")
        self.assertEqual(out["state"], "verified")
        self.assertEqual(parse_qs(urlsplit(urls[0]).query)["subject"], ["Assunto"])

    def test_sign_in_page_is_reported_as_such(self):
        out, _ = self.go(["https://accounts.google.com/signin"])
        self.assertEqual((out["state"], out["code"]), ("login_required", "notify_login_required"))
        r = agent.to_result(out, "c")
        self.assertEqual((r["state"], r["diagnostic"]["error_code"]), ("completed_unverified", "NOTIFY-LOGIN-REQUIRED"))
        self.assertEqual(r["diagnostic"]["params"]["target"], "Gmail")

    def test_a_redirect_to_sign_in_after_the_page_appears_is_not_prepared(self):
        out, _ = self.go(["https://mail.google.com/mail/", "https://mail.google.com/mail/", "https://accounts.google.com/signin"])
        self.assertEqual(out["state"], "login_required")

    def test_error_page_or_closed_tab_is_not_prepared(self):
        self.assertEqual(self.go(["https://mail.google.com/", "chrome-error://chromewebdata/"])[0]["state"], "uncertain")
        self.assertEqual(self.go(["https://mail.google.com/", None])[0]["state"], "uncertain")
        self.assertEqual(self.go(["https://mail.google.com/", "https://sso.exemplo.test/"])[0]["state"], "uncertain")

    def test_sign_in_that_finishes_counts(self):
        out, _ = self.go(["https://accounts.google.com/signin", "https://mail.google.com/mail/u/0/"])
        self.assertEqual(out["state"], "verified")

    def test_another_site_confirms_nothing(self):
        out, _ = self.go(["https://exemplo.test/"])
        self.assertEqual((out["state"], out["code"]), ("uncertain", "notify_unconfirmed"))
        self.assertEqual(agent.to_result(out, "c")["diagnostic"]["error_code"], "NOTIFY-UNCONFIRMED")

    def test_unknown_provider_or_browser(self):
        self.assertEqual(nd.run_webmail({"provider": "x", "browser": "msedge"}, TO, "s", "b", resolve=lambda b: {"id": b})["code"], "invalid_job")
        self.assertEqual(nd.run_webmail({"provider": "gmail", "browser": "msedge"}, TO, "s", "b", resolve=lambda b: None)["code"], "browser_not_found")


class RunTest(unittest.TestCase):
    def job(self, channel, execution_=None):
        return {"position": 2, "execution": execution_ or execution(), "config": {"action": "notify", "to": TO, "channel": channel, "labels": PT}}

    def test_prepared_records_what_was_prepared(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "R.pdf").write_bytes(b"%PDF")
            ex = execution(context={"steps": {"1": {"report": {"file": "R.pdf"}}}})
            seen = {}

            def app(channel, to, subject, body, attachment):
                seen.update(attachment=attachment, body=body)
                return {"state": "verified", "verified": True, "context": {"opened": {"name": "Microsoft Outlook", "hwnd": 7, "pid": 8}}}
            out = nd.run(self.job({"kind": "app", "mail_id": "outlook", "name": "Microsoft Outlook"}, ex), Path(d), app_runner=app)
            m = out["context"]["message"]
            self.assertEqual((m["status"], m["to"], m["channel"], m["attached"], m["hwnd"]), ("prepared", TO, "Microsoft Outlook", "R.pdf", 7))
            self.assertEqual(seen["attachment"].name, "R.pdf")

    def test_channels_without_files_mention_them(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "R.pdf").write_bytes(b"%PDF")
            ex = execution(context={"steps": {"1": {"report": {"file": "R.pdf"}}}})
            seen = {}

            def web(channel, to, subject, body):
                seen["body"] = body
                return {"state": "verified", "verified": True, "opened": {"name": "Gmail", "hwnd": 1, "pid": 2}}
            m = nd.run(self.job({"kind": "webmail", "provider": "gmail", "browser": "msedge"}, ex), Path(d), webmail_runner=web)["context"]["message"]
            self.assertEqual((m["attached"], m["mentioned"]), (None, ["R.pdf"]))
            self.assertIn("R.pdf", seen["body"])

    def test_not_prepared_passes_on_and_records_nothing(self):
        out = nd.run(self.job({"kind": "webmail", "provider": "gmail", "browser": "msedge"}), Path("."), webmail_runner=lambda *a: {"state": "uncertain", "code": "notify_unconfirmed", "detail": "Gmail"})
        self.assertEqual(out["state"], "uncertain")
        self.assertNotIn("context", out)

    def test_invalid(self):
        self.assertEqual(nd.run({"config": {}})["code"], "invalid_job")
        self.assertEqual(nd.run(self.job({"kind": "pombo"}), Path("."))["code"], "invalid_job")

    def test_no_send_exists_in_this_module(self):
        source = Path(nd.__file__).read_text(encoding="utf-8")
        code = [line for line in source.splitlines() if not line.lstrip().startswith(('"', "#"))]
        self.assertFalse([line for line in code if "smtp" in line.lower() or "sendmail" in line.lower() or "%{enter}" in line.lower()])
        self.assertTrue(browser_open.launch_site)


if __name__ == "__main__":
    unittest.main()
