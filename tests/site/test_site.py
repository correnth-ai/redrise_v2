"""Local isolated site (P12): routes, 404 literal, sign-up validation, release files.
    cd tests/site && <python> -B -m unittest test_site
"""

import json
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "site"))
import serve_local  # noqa: E402


class SiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        (cls.tmp / "rel").mkdir()
        (cls.tmp / "rel" / "latest.json").write_text(json.dumps({"schema": "redrise.release/1", "version": "0.1.0-test",
            "installer": {"file": "RedRise-Setup-0.1.0-test.exe", "size": 3, "sha256": "a" * 64}}), encoding="utf-8")
        (cls.tmp / "rel" / "RedRise-Setup-0.1.0-test.exe").write_bytes(b"abc")
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), serve_local.make(cls.tmp / "rel", cls.tmp / "data"))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path) as r:
                return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)

    def post(self, body):
        req = urllib.request.Request(self.base + "/api/notify", json.dumps(body).encode(), {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def test_pages_and_preserved_destinations(self):
        s, home, h = self.get("/")
        self.assertEqual(s, 200)
        self.assertIn("Construa, automatize e opere processos B2B com agentes de IA.", home)
        self.assertIn("https://redrise.app/contact-sales", home)  # Agendar Demonstração preserved
        self.assertIn("https://redrise.app/signin", home)          # Acessar preserved
        self.assertIn("Baixar RedRise", home)
        self.assertEqual(h.get("X-Robots-Tag"), "noindex, nofollow")
        self.assertEqual(self.get("/download")[0], 200)
        self.assertEqual(self.get("/assets/redrise-lockup-light.svg")[0], 200)

    def test_releases_served_and_traversal_refused(self):
        s, body, _ = self.get("/releases/latest.json")
        self.assertEqual((s, json.loads(body)["version"]), (200, "0.1.0-test"))
        self.assertEqual(self.get("/releases/RedRise-Setup-0.1.0-test.exe")[0], 200)
        self.assertEqual(self.get("/releases/..%2F..%2Fsecret")[0], 404)
        self.assertEqual(self.get("/assets/..%2Fprovenance.json")[0], 404)

    def test_404_literal(self):
        s, body, _ = self.get("/cases/sales")
        self.assertEqual(s, 404)
        self.assertIn("404 — Ainda não concluímos esta sessão.", body)
        self.assertIn("Cadastre-se abaixo para ser notificado quando lançarmos algo.", body)
        self.assertIn("Digite seu e-mail", body)

    def test_notify_validates_and_persists(self):
        self.assertEqual(self.post({"email": "nao-e-email"}), 400)
        self.assertEqual(self.post(["not", "an", "object"]), 400)  # answered, not a dropped connection
        self.assertEqual(self.post({"email": "pessoa@exemplo.com", "page": "/cases/sales"}), 200)
        rows = (self.tmp / "data" / "notify.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(json.loads(rows[-1])["email"], "pessoa@exemplo.com")


if __name__ == "__main__":
    unittest.main()
