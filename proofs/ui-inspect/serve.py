"""Lab tool, never shipped: serves the built UI in a plain browser against a real
Core and PostgreSQL with synthetic data, so screens can be inspected with
persisted records and without any input on the desktop. The desktop bridge is
replaced by a small shim (/__shim.js -> /__ipc -> CoreClient); nothing here
drives Windows, and the Runner is a declared simulation.

    <lab python> -B proofs/ui-inspect/serve.py [--port 5199] [--dist <ui dist>]
Env: RR_PG_BIN, RR_CORE_SITE (as tests/core). State lives in a temporary folder on C:."""

import argparse
import json
import mimetypes
import os
import shutil
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB = Path(os.environ.get("RR_LAB", Path.home() / "RedRise-v2-dev"))
PG_BIN = Path(os.environ.get("RR_PG_BIN", LAB / "downloads/p06-core/pgsql/bin"))
SITE = Path(os.environ.get("RR_CORE_SITE", LAB / "downloads/p06-core/site-packages"))
for p in (ROOT / "core", ROOT / "contracts" / "python", ROOT / "runner", SITE):
    sys.path.insert(0, str(p))

from redrise_contracts.client import CoreClient, CoreError  # noqa: E402
from redrise_contracts.vault import MemoryVault  # noqa: E402
from redrise_core import host  # noqa: E402

SHIM = """window.__TAURI__ = { core: { invoke: async (cmd, args) => {
  const r = await fetch('/__ipc', { method: 'POST', body: JSON.stringify({ cmd, args }) });
  const j = await r.json(); if (!r.ok) throw j; return j; } }, window: { getCurrentWindow() { return null; } } };"""
PASSWORD = "senha-forte-01"


def seed(info: dict) -> None:
    """Synthetic team: enough rows for pagination, every link state and every outcome."""
    c = CoreClient("127.0.0.1", info["lan_port"], info["fingerprint"])
    c.call("POST", "/api/v1/setup", {"team": "Equipe de Inspecao", "username": "admin", "display": "Pessoa Administradora", "password": PASSWORD})
    a = CoreClient("127.0.0.1", info["lan_port"], info["fingerprint"], c.call("POST", "/api/v1/login", {"username": "admin", "password": PASSWORD})["token"])
    a.call("POST", "/api/v1/users", {"username": "operador", "display": "Pessoa Operadora", "password": PASSWORD, "role": "operator"})
    s = a.call("POST", "/api/v1/stations", {"name": "estacao-inspecao", "is_host": True})
    r = CoreClient("127.0.0.1", info["lan_port"], info["fingerprint"], s["runner_token"], reported_by="RR-RUNNER")
    hb = {"platform": "windows-x86_64", "categories": ["windows", "browser"], "runner_version": "0.3.10", "session_state": "ready",
          "browsers": [{"id": "msedge", "name": "Microsoft Edge", "path": "C:\\simulated\\msedge.exe", "version": "1", "source": "simulated", "homologated": False}]}
    apps = [{"id": f"Sintetico.{n.replace(' ', '')}!App", "name": n} for n in ("Bloco de Notas", "Calculadora", "Paint", "Planilha Sintetica", "Sistema de Pedidos")]
    r.call("POST", "/api/v1/runner/heartbeat", {**hb, "apps": apps + [{"id": "browser:msedge", "name": "Microsoft Edge", "browser_id": "msedge"},
                                                              {"id": "mail:default", "name": "Windows mail app", "mail_id": "default"}]})

    def routine(name, cfg):
        return a.call("POST", "/api/v1/routines", {"name": name, "category": "browser", "version": {"kind": "browser_open", "config": cfg}})["routine"]["id"]
    site = lambda host_: {"origin": "site", "browser": "msedge", "url": f"https://{host_}.exemplo.test/", "path": None, "isolated": True}
    html = {"origin": "html", "browser": None, "url": None, "path": "C:\\Exemplos\\manual.html", "isolated": True}
    linked = [routine(n, site(h)) for n, h in (("Abrir pedidos", "pedidos"), ("Abrir notas fiscais", "notas"), ("Abrir estoque", "estoque"))]
    loose = [routine(f"Consultar portal {i:02d}", site(f"portal{i}")) for i in range(1, 11)]
    loose.append(routine("Abrir manual local", html))
    loose.append(routine("Etapa que requer contexto", {**site("contexto"), "isolated": False}))
    a.call("POST", "/api/v1/routines", {"name": "Modelo de boas-vindas", "category": "windows", "version": {"kind": "template", "template_id": "boas-vindas"}})
    proc = a.call("POST", "/api/v1/processes", {"name": "Pedidos do dia", "items": [{"routine_id": x, "continue_next": True} for x in linked]})
    other = a.call("POST", "/api/v1/processes", {"name": "Conferencia de notas", "items": [{"routine_id": linked[1], "continue_next": False}]})

    def step(state="verified", code=None, cancel=False):
        job = r.call("POST", "/api/v1/runner/claim", hb)["job"]
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/start", {"lease_id": job["lease_id"]})
        if cancel:  # cancel accepted while the step runs; the Runner still reports what happened
            a.call("POST", f"/api/v1/jobs/{job['job_id']}/cancel")
        result = {"schema": "redrise.job-result/1", "state": state, "verified": state == "verified", "details": {"context": {"tab": "sintetica"}}}
        if code:
            from redrise_contracts import diagnostics as dg
            result["diagnostic"] = dg.make(code, reported_by="RR-RUNNER", params={"url": "https://pedidos.exemplo.test/", "reason": "synthetic"}).to_dict()
        r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/result", {"lease_id": job["lease_id"], "result": result})

    def execute(**target):
        return a.call("POST", "/api/v1/executions", {"request_id": uuid.uuid4().hex, "station_id": s["station"]["id"], **target})
    for _ in range(6):  # complete runs
        execute(process_id=proc["id"])
        step(), step(), step()
    execute(process_id=proc["id"])  # stops on an unverified second step
    step(), step("failed", "BROWSER-PAGE-NOT-READY")
    execute(process_id=proc["id"])  # cancelled while step 1 ran; step 1 completed and is kept, step 2 never queued
    step(cancel=True)
    execute(process_id=other["id"])
    step("uncertain")
    for rid in loose[:4]:
        execute(routine_id=rid)
        step()
    # Reviews: one to approve, one approved, one with the other member.
    me = a.call("GET", "/api/v1/me")["id"]
    op_id = next(u["id"] for u in a.call("GET", "/api/v1/users") if u["username"] == "operador")
    rev = a.call("POST", "/api/v1/processes", {"name": "Aprovacao de pedidos", "items": []})
    first = a.call("POST", "/api/v1/routines", {"name": "Abrir pedido", "category": "browser", "link": {"process_id": rev["id"]},
                                                "version": {"kind": "browser_open", "config": site("aprovacao")}})["routine"]["id"]
    review = a.call("POST", "/api/v1/routines", {"name": "Conferir pedido", "category": "windows", "link": {"process_id": rev["id"], "after_position": 1},
                                                 "version": {"kind": "followup", "config": {"action": "review", "assignee_id": me}}})["routine"]["id"]
    a.call("POST", f"/api/v1/processes/{rev['id']}/items", {"routine_id": loose[-3]})
    assert first and review
    execute(process_id=rev["id"])
    step()
    done = next(q for q in a.call("GET", "/api/v1/reviews"))
    a.call("POST", f"/api/v1/reviews/{done['id']}/approve")
    step()
    for _ in range(2):
        execute(process_id=rev["id"])
        step()
    a.call("POST", "/api/v1/routines", {"name": "Revisao do operador", "category": "windows", "link": {"process_id": other["id"], "after_position": 1},
                                        "version": {"kind": "followup", "config": {"action": "review", "assignee_id": op_id}}})
    a.call("POST", f"/api/v1/processes/{other['id']}/step1", {"routine_id": loose[-5]})
    threading.Thread(target=simulated_runner, args=(a, r, hb), daemon=True).start()


def simulated_runner(a, r, hb) -> None:
    """Answers the assistant's preparation and test jobs. Declared simulation: opens nothing."""
    while True:
        time.sleep(0.5)
        for _ in [x for x in a.call("GET", "/api/v1/jobs") if x["state"] == "queued"]:
            job = r.call("POST", "/api/v1/runner/claim", hb)["job"]
            if not job:
                continue
            if job["mode"] == "run":
                time.sleep(4)  # long enough to be seen in progress
            r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/start", {"lease_id": job["lease_id"]})
            ctx = {"opened": {"name": "simulated"}}
            if job["kind"] == "followup":
                ctx = {"report": {"file": "Relatorio_simulado.pdf", "bytes": 1, "pages": 1}}
                if (job["config"] or {}).get("action") == "notify":
                    ctx = {"message": {"status": "prepared", "to": job["config"]["to"], "channel": job["config"]["channel"]["name"]}}
            if job["mode"] == "prepare":
                t = (job["config"] or {}).get("target") or {}
                missing = "ausente" in str(t.get("path") or "").lower()
                for check, detail in (("session", None), ("target", t.get("name") or job["config"].get("url") or job["config"].get("path")), ("launch", "simulated")):
                    bad = check == "target" and missing
                    r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/progress", {"lease_id": job["lease_id"], "check": {"id": check, "state": "running"}})
                    time.sleep(0.6)
                    r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/progress", {"lease_id": job["lease_id"], "check": {"id": check, "state": "failed" if bad else "ok", "detail": detail}})
                    if bad:
                        break
                ctx = {"resolved": {"how": "simulated", "launch": "simulated", "name": t.get("name") or "site"}}
            r.call("POST", f"/api/v1/runner/jobs/{job['job_id']}/result", {"lease_id": job["lease_id"], "result": {
                "schema": "redrise.job-result/1", "state": "verified", "verified": True, "details": {"context": ctx}}})


def make_handler(dist: Path, info: dict):
    tokenless = CoreClient

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, status, body: bytes, ctype: str):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status, obj):
            self._send(status, json.dumps(obj).encode("utf-8"), "application/json")

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/__shim.js":
                return self._send(200, SHIM.encode("utf-8"), "text/javascript")
            f = (dist / path.lstrip("/")).resolve() if path != "/" else dist / "index.html"
            if not f.is_file() or dist.resolve() not in f.resolve().parents:
                return self._send(404, b"not found", "text/plain")
            data = f.read_bytes()
            if f.name == "index.html":
                data = data.replace(b"<head>", b'<head><script src="/__shim.js"></script>', 1)
            self._send(200, data, mimetypes.guess_type(f.name)[0] or "application/octet-stream")

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
            cmd, args = req["cmd"], req.get("args") or {}
            if cmd == "app_info":
                return self._json(200, {"connection": True, "desktop": "inspecao", "core": "lab"})
            if cmd == "update_check":
                return self._json(200, {"available": False})
            if cmd == "pick_file":  # the Windows file picker is exercised in the installed build
                return self._json(200, r"C:\Exemplos\planilha.xlsx")
            if cmd == "open_report_folder":  # the Explorer is exercised in the installed build
                return self._json(200, {"opened": args.get("name")})
            if cmd == "storage_local":
                return self._json(200, {"data_bytes": 1048576, "logs_bytes": 2048})
            if cmd != "api":
                return self._json(501, {"diagnostic": {"error_code": "CONTRACT-PAYLOAD", "category": "contract", "what_happened": f"{cmd} not simulated",
                                                        "completed": "", "pending": "", "effect_state": "none", "next_action": "", "retry": "not_useful",
                                                        "details_summary": "", "reported_by": "RR-UI", "module_hints": ["RR-UI"], "diagnosis_status": "unconfirmed",
                                                        "correlation_id": "inspect", "boundary": None, "version": {}, "technical_details": {}, "cause": None}})
            client = tokenless("127.0.0.1", info["lan_port"], info["fingerprint"], args.get("token"))
            try:
                self._json(200, client.call(args["method"], args["path"], args.get("body")))
            except CoreError as e:
                self._json(e.status or 500, {"diagnostic": e.diagnostic.to_dict()})

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5199)
    ap.add_argument("--dist", type=Path, default=LAB / "build/ui-dev/dist")
    args = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="rr-ui-inspect-", dir=LAB / "scratch"))
    inst = tmp / "install"
    shutil.copytree(ROOT / "templates", inst / "templates")
    h = host.Host(host.HostPaths(inst, tmp / "data", pg_bin=PG_BIN), MemoryVault(), log=lambda m: None)
    info = h.start(lan_port=0, bind="127.0.0.1")
    try:
        seed(info)
        httpd = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.dist, info))
        print(f"ready http://127.0.0.1:{args.port}/ login admin", flush=True)
        httpd.serve_forever()
    finally:
        h.stop()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
