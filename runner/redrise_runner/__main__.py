"""`redrise-runner health | capabilities | run-job --job <file>`

Prints one JSON document. Exit codes: 0 ok/completed_unverified, 1 error,
2 refused, 3 failed, 4 uncertain, 5 cancelled, 6 unhealthy runtime.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path

from . import __version__
from . import diagnose, excel, integrity, paths, runtime, templates
from .engine import EngineClient, EngineError
from .jobs import RUNNER_CATEGORIES, RUNNER_PLATFORM, JobSpec, run_job

EXIT = {"completed_unverified": 0, "error": 1, "refused": 2, "failed": 3, "uncertain": 4, "cancelled": 5}


def emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="redrise-runner")
    ap.add_argument("--install-root", type=Path, help="testing only; default: derived from the interpreter")
    ap.add_argument("--data-root", type=Path, help="testing only; default: %%LOCALAPPDATA%%\\RedRise")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("health")
    sub.add_parser("capabilities")
    rj = sub.add_parser("run-job")
    rj.add_argument("--job", type=Path, required=True)
    sub.add_parser("templates")
    ct = sub.add_parser("check-template", help="inputs, preconditions and session only; launches nothing")
    ct.add_argument("--template", required=True)
    ct.add_argument("--input", action="append", default=[], help="name=value")
    ct.add_argument("--desktop-dir", type=Path, help="testing only")
    rt = sub.add_parser("run-template")
    rt.add_argument("--template", required=True)
    rt.add_argument("--input", action="append", default=[], help="name=value")
    rt.add_argument("--desktop-dir", type=Path, help="testing only: stands in for the real Desktop")
    sub.add_parser("excel-discover", help="locate Excel: found (descriptor) | not_found | failed")
    xs = sub.add_parser("excel-start", help="new Excel process + blank workbook from a descriptor file")
    xs.add_argument("--descriptor", type=Path, required=True)
    xs.add_argument("--timeout-s", type=float, default=45.0)
    sub.add_parser("excel-new", help="discover -> start, with diagnostics")
    jn = sub.add_parser("join", help="connect this station to a team host (admin login; password on stdin)")
    jn.add_argument("--code", required=True)
    jn.add_argument("--username", required=True)
    jn.add_argument("--station-name")
    jn.add_argument("--is-host", action="store_true")
    sub.add_parser("browsers", help="installed browsers on this station (registry + known paths; starts nothing)")
    bo = sub.add_parser("browser-open", help="one Browser opening routine on this session (new tab, <= 30 s confirmation)")
    bo.add_argument("--origin", choices=("site", "html"), required=True)
    bo.add_argument("--browser", help="site only: chrome | msedge | firefox | chromium")
    bo.add_argument("--url")
    bo.add_argument("--path", help="html only: full path of the file")
    ns = sub.add_parser("notepad-step", help="one routine of the Boas-vindas process, outside a team (lab checks)")
    ns.add_argument("--step", required=True, choices=["open", "save", "close"])
    ns.add_argument("--context-file", type=Path, help="JSON the previous step printed under `context`")
    ag = sub.add_parser("agent", help="station loop: heartbeat, claim, execute, report")
    ag.add_argument("--stop-file", type=Path)
    ag.add_argument("--poll-s", type=float, default=3.0)
    ap.add_argument("--vault-namespace", default="station", help="testing only")
    ap.add_argument("--correlation-id", default=None)
    a = ap.parse_args(argv)
    cid = a.correlation_id

    layout = paths.resolve(a.install_root, a.data_root)
    rt = runtime.report(layout.runtime_dir)

    if a.cmd == "browsers":
        from . import browsers
        emit(browsers.discover())
        return 0

    if a.cmd == "browser-open":
        from . import browser_open
        config = {"origin": a.origin, "browser": a.browser, "url": a.url, "path": a.path, "isolated": True}
        res = diagnose.attach(browser_open.run(config), cid)
        emit(res)
        return 0 if res["state"] == "verified" else EXIT.get(res["state"], 1)

    if a.cmd == "notepad-step":
        import time
        from . import notepad_steps
        from .jobs import SessionBusy, session_lock
        ctx = json.loads(a.context_file.read_text(encoding="utf-8-sig")) if a.context_file else {}
        desk = notepad_steps.UiaDesk()
        try:
            with session_lock(layout.locks_dir):
                send = notepad_steps.engine_sender(f"cli-{a.step}-{time.strftime('%Y%m%d-%H%M%S')}", layout,
                                                   EngineClient.at(layout.engine), threading.Event())
                res = diagnose.attach(notepad_steps.run(a.step, ctx, desk, send), cid)
        except SessionBusy as e:
            res = diagnose.attach({"state": "refused", "code": "session_busy", "detail": str(e)}, cid)
        finally:
            desk.close()
        emit(res)
        return 0 if res["state"] == "verified" else EXIT.get(res["state"], 1)

    if a.cmd == "templates":
        emit({"templates": templates.list_templates(layout.install_root / "templates")})
        return 0

    if a.cmd == "join":
        from redrise_contracts.client import CoreError
        from redrise_contracts.vault import WindowsVault
        from . import station
        try:
            conn = station.join(layout.data_root, a.code, a.username, sys.stdin.readline().rstrip("\r\n"),
                                a.station_name, a.is_host, WindowsVault(a.vault_namespace))
        except ValueError as e:
            emit(diagnose.attach({"state": "refused", "code": "invalid_join_code", "detail": str(e)}, cid))
            return 2
        except CoreError as e:
            emit({"state": "error", "diagnostic": e.diagnostic.to_dict(), "message": e.diagnostic.render()})
            return 3
        emit({"state": "joined", "station": conn.station_name, "station_id": conn.station_id, "host": conn.host})
        return 0

    if a.cmd == "excel-discover":
        res = excel.discover()
        d = excel.present_discovery(res, cid)
        if d is not None:
            res.update(diagnostic=d.to_dict(), message=d.render())
        emit(res)
        return {"found": 0, "not_found": 2}.get(res["status"], 1)

    if a.cmd == "capabilities":
        emit({"runner": __version__, "platform": RUNNER_PLATFORM, "categories": list(RUNNER_CATEGORIES)})
        return 0

    try:
        engine = EngineClient.at(layout.engine)
    except EngineError as e:
        emit(diagnose.attach({"status": "unhealthy", "state": "error", "code": e.code, "detail": e.detail, "runtime": rt}, cid))
        return 6

    if a.cmd == "agent":
        from redrise_contracts.vault import WindowsVault
        from . import station
        from .agent import Agent
        client = station.client(layout.data_root, WindowsVault(a.vault_namespace))
        if client is None:
            emit(diagnose.attach({"state": "refused", "code": "station_not_joined"}, cid))
            return 2
        stop = threading.Event()
        if a.stop_file:
            a.stop_file.unlink(missing_ok=True)

            def watch():
                while not stop.wait(0.5):
                    if a.stop_file.exists():
                        stop.set()
            threading.Thread(target=watch, daemon=True).start()
        Agent(layout, engine, client, a.poll_s).run_forever(stop)
        return 0

    if a.cmd in ("excel-start", "excel-new"):
        dismiss = excel.engine_dismisser(engine, layout.data_root / "work" / "excel-start")
        timeout_s = getattr(a, "timeout_s", 45.0)

        def start(desc, correlation_id=None):
            return excel.start(desc, dismiss_start_screen=dismiss, timeout_s=timeout_s, correlation_id=correlation_id)

        if a.cmd == "excel-start":
            try:
                desc = json.loads(a.descriptor.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as e:
                desc = {"unreadable": str(e)}
            res = start(desc, correlation_id=cid)
        else:
            res = excel.new_workbook(start_fn=start, correlation_id=cid)
        emit(res)
        return 0 if res["status"] == "ready" else 3

    if a.cmd == "health":
        try:
            ver = engine.version()
            ready = engine.readiness(probe_hooks=True)
        except EngineError as e:
            emit({"status": "unhealthy", "code": e.code, "detail": e.detail, "runtime": rt})
            return 6
        integ = integrity.verify(layout.install_root)
        healthy = rt["ok"] and ready.get("ready") is True and integ["ok"]
        emit({
            "status": "healthy" if healthy else "unhealthy",
            "runner": __version__,
            "platform": RUNNER_PLATFORM,
            "categories": list(RUNNER_CATEGORIES),
            "install_root": str(layout.install_root),
            "data_root": str(layout.data_root),
            "engine": {"path": str(layout.engine), **ver},
            "session": ready,
            "runtime": rt,
            "integrity": integ,
        })
        return 0 if healthy else 6

    if not rt["ok"]:
        emit(diagnose.attach({"state": "refused", "code": "runtime_not_private", "runtime": rt,
                              "detail": ", ".join(k for k, v in rt["checks"].items() if not v)}, cid))
        return 6
    if a.cmd == "check-template":
        res = templates.run_template(a.template, layout, engine, dict(kv.split("=", 1) for kv in a.input), a.desktop_dir, dry_run=True)
        emit(diagnose.attach(res, cid))
        return 0 if res["state"] == "ready" else 2

    if a.cmd == "run-template":
        given = dict(kv.split("=", 1) for kv in a.input)
        res = templates.run_template(a.template, layout, engine, given, a.desktop_dir)
        diagnose.attach(res, cid)
        res["result_file"] = str(templates.save_result(layout, res))
        emit(res)
        return {"verified": 0, "refused": 2, "precondition_missing": 2, "failed": 3, "uncertain": 4, "cancelled": 5}.get(res["state"], 1)

    try:
        spec = JobSpec.load(a.job)
    except (OSError, ValueError, KeyError) as e:
        emit(diagnose.attach({"state": "refused", "code": "invalid_job", "detail": str(e)}, cid))
        return 2
    result = run_job(spec, layout, engine, threading.Event())
    emit(diagnose.attach(result, cid))
    return EXIT.get(result["state"], 1)


if __name__ == "__main__":
    sys.exit(main())
