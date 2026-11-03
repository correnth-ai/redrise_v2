"""Local isolated site for the closed beta (P12): loopback only, never public.

    python serve_local.py --releases DIR --data DIR [--port 47880]

/, /download, static files, /assets/* (authorized logos), /releases/* (signed
channel: latest.json, latest.json.sig, installer), POST /api/notify (404
sign-up, validated, stored locally as JSON lines); anything else -> 404 page
with status 404. Pages carry noindex."""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SITE = Path(__file__).resolve().parent
BRAND = SITE.parent / "assets" / "brand" / "redrise"
PAGES = {"/": "index.html", "/download": "download.html"}
STATIC = {"/styles.css", "/download.js"}
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")


def make(releases: Path, data: Path):
    class H(BaseHTTPRequestHandler):
        server_version = "redrise-site-local"

        def log_message(self, *a):
            pass

        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Robots-Tag", "noindex, nofollow")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _file(self, p: Path):
            ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            if p.suffix == ".sig":
                ctype = "text/plain"
            self._send(200, p.read_bytes(), ctype + ("; charset=utf-8" if ctype.startswith("text/") or ctype.endswith("json") else ""))

        def _404(self):
            self._send(404, (SITE / "404.html").read_bytes(), "text/html; charset=utf-8")

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in PAGES:
                return self._file(SITE / PAGES[path])
            if path in STATIC:
                return self._file(SITE / path.lstrip("/"))
            m = re.fullmatch(r"/assets/([A-Za-z0-9._-]+)", path)
            if m and (BRAND / m.group(1)).is_file() and m.group(1).endswith((".png", ".svg")):
                return self._file(BRAND / m.group(1))
            m = re.fullmatch(r"/releases/([A-Za-z0-9._-]+)", path)
            if m and (releases / m.group(1)).is_file():
                return self._file(releases / m.group(1))
            self._404()

        def do_POST(self):
            if self.path != "/api/notify":
                return self._404()
            try:
                n = min(int(self.headers.get("Content-Length") or 0), 4096)
                body = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(body, dict):
                    body = {}
                email = str(body.get("email", "")).strip()
            except (ValueError, TypeError):
                body, email = {}, ""
            if not EMAIL.match(email):
                return self._send(400, json.dumps({"error": "Informe um e-mail válido."}).encode(), "application/json")
            data.mkdir(parents=True, exist_ok=True)
            with open(data / "notify.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"email": email, "page": str(body.get("page", ""))[:200], "at": int(time.time())}) + "\n")
            self._send(200, b'{"ok": true}', "application/json")

    return H


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--releases", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--port", type=int, default=47880)
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make(a.releases, a.data))  # loopback only
    print(json.dumps({"site": f"http://127.0.0.1:{a.port}/"}), flush=True)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
