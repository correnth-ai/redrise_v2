"""`redrise-core prepare | serve | backup | restore` (host only).

`serve` stops when the file given by --stop-file appears or on Ctrl+C, so the
desktop app can stop it cleanly (no process kill while writing)."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

from . import host as h
from redrise_contracts.vault import WindowsVault


def _layout(a) -> h.HostPaths:
    install = a.install_root or Path(sys.executable).resolve().parent.parent.parent
    data = a.data_root
    if data is None:
        sys.path.insert(0, str(install / "runner"))
        from redrise_runner.paths import local_app_data
        data = local_app_data() / "RedRise"
    return h.HostPaths(Path(install).resolve(), Path(data).resolve())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="redrise-core")
    ap.add_argument("--install-root", type=Path)
    ap.add_argument("--data-root", type=Path)
    ap.add_argument("--vault-namespace", default="host", help="testing only")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("prepare")
    pr.add_argument("--port", type=int)
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int)
    s.add_argument("--bind", default="0.0.0.0")
    s.add_argument("--stop-file", type=Path)
    b = sub.add_parser("backup")
    b.add_argument("--out", type=Path, required=True)
    r = sub.add_parser("restore")
    r.add_argument("--dump", type=Path, required=True)
    r.add_argument("--target-db", required=True)
    a = ap.parse_args(argv)
    p = _layout(a)
    vault = WindowsVault(a.vault_namespace)

    def log(msg: str) -> None:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()

    if a.cmd == "prepare":
        print(json.dumps(h.prepare(p, vault, a.port, log=log)))
        return 0
    host = h.Host(p, vault, log)
    if a.cmd == "serve":
        stop = threading.Event()
        if a.stop_file:
            a.stop_file.unlink(missing_ok=True)

            def watch():
                while not stop.is_set():
                    if a.stop_file.exists():
                        stop.set()
                    time.sleep(0.5)
            threading.Thread(target=watch, daemon=True).start()
        try:
            info = host.start(a.port, a.bind)
            print(json.dumps({"event": "core_ready", **info}), flush=True)
            while not stop.wait(1):
                pass
        except KeyboardInterrupt:
            pass
        finally:
            host.stop()
        return 0
    if a.cmd == "backup":
        print(json.dumps({"backup": str(host.backup(a.out))}))
        return 0
    host.restore(a.dump, a.target_db)
    print(json.dumps({"restored_into": a.target_db}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
