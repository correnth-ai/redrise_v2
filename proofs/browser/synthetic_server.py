"""Synthetic order form (lab only), loopback-bound.

GET  /        form: Cliente (name=cliente), Valor do pedido (name=valor), button "Salvar"
POST /save    appends {"cliente", "valor", "at"} to --store (JSON lines), shows "Salvo com sucesso"
--fake-success: shows the same success page WITHOUT persisting (fault injection).
Prints {"port": N} on stdout once listening.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

FORM = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Pedido RedRise</title></head>
<body><h1>Novo pedido</h1>
<form method="post" action="/save">
<label for="cliente">Cliente</label> <input id="cliente" name="cliente" autocomplete="off"><br>
<label for="valor">Valor do pedido</label> <input id="valor" name="valor" inputmode="decimal" autocomplete="off"><br>
<button type="submit" data-testid="salvar">Salvar</button>
</form></body></html>"""
DONE = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Pedido salvo</title></head>
<body><p id="status">Salvo com sucesso</p></body></html>"""


def make_handler(store: Path, fake: bool):
    class H(BaseHTTPRequestHandler):
        def _send(self, body: str, code: int = 200):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self._send(FORM if self.path in ("/", "/index.html") else "not found", 200 if self.path in ("/", "/index.html") else 404)

        def do_POST(self):
            if self.path != "/save":
                return self._send("not found", 404)
            n = int(self.headers.get("Content-Length", "0"))
            form = parse_qs(self.rfile.read(n).decode("utf-8"))
            if not fake:
                rec = {"cliente": form.get("cliente", [""])[0], "valor": form.get("valor", [""])[0], "at": time.time()}
                with open(store, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self._send(DONE)

        def log_message(self, *args):
            pass

    return H


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", type=Path, required=True)
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--fake-success", action="store_true")
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(a.store, a.fake_success))
    print(json.dumps({"port": srv.server_address[1]}), flush=True)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
