"""S4: binary rollback versus data recovery, on an isolated COPY of the lab team (synthetic data).
No window, no input: the Cores run headless on the copy and are stopped by their stop file.

    <new install>\\runtime\\python\\python.exe -B -X utf8 rollback_check.py --new <install-new> --old <install-old>
        --data <copy of lab-test\\data> --vault rrtest2-host --account <lab-test\\test-account.json> --out <report.json>

 1. the new Core opens the copy: version and counts (processes, routines, executions, users, migrations)
 2. the old Core opens the same copy (binary rollback): same counts, nothing migrated backwards
 3. backup of the copy (pg_dump) and restore into a separate database: same row counts; the restored
    database and the dump are removed afterwards

With --baseline-with <previous install> (and no --new/--old) it only records the counts the previous
version sees on the given data, before an upgrade; accept_s4.py --baseline compares against them.
The copy must not be in use (close the lab app first). Passwords stay in memory and are never printed."""

from __future__ import annotations

import argparse
import json
import subprocess
import threading
import time
from pathlib import Path

from redrise_contracts.client import CoreClient, CoreError
from redrise_contracts.vault import WindowsVault
from redrise_core import db, pg

TABLES = ("processes", "routines", "routine_versions", "executions", "jobs", "users", "schema_migrations",
          "schedules", "schedule_runs", "notifications")  # the schedule tables exist from Core 0.3.7 (migration 010)


def serve(install: Path, data: Path, vault: str, stop: Path) -> tuple[subprocess.Popen, dict]:
    stop.unlink(missing_ok=True)
    p = subprocess.Popen([str(install / "runtime" / "python" / "python.exe"), "-B", "-m", "redrise_core", "--install-root", str(install),
                          "--data-root", str(data), "--vault-namespace", vault, "serve", "--bind", "127.0.0.1", "--stop-file", str(stop)],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, encoding="utf-8")
    end = time.monotonic() + 120
    while time.monotonic() < end:
        line = p.stdout.readline()
        if line.startswith("{") and '"core_ready"' in line:
            # Keep reading what it prints, so a full pipe can never block the Core (review R11).
            threading.Thread(target=lambda: [None for _ in p.stdout], daemon=True).start()
            return p, json.loads(line)
        if p.poll() is not None:
            break
    p.kill()
    raise SystemExit(f"Core did not start from {install.name}")


def counts(info: dict, account: dict) -> dict:
    c = CoreClient("127.0.0.1", info["lan_port"], info["fingerprint"])
    st = c.call("GET", "/api/v1/status")
    tok = c.call("POST", "/api/v1/login", {"username": account["admin_user"], "password": account["admin_password"]})["token"]
    a = CoreClient("127.0.0.1", info["lan_port"], info["fingerprint"], tok)
    out = {"core": st["core"], "processes": len(a.call("GET", "/api/v1/processes")), "routines": len(a.call("GET", "/api/v1/routines")),
           "executions_366d": _summary(a),
           "executions_listed": len(a.call("GET", "/api/v1/executions")), "users": len(a.call("GET", "/api/v1/users")),
           # an older Core must still read the notifications a newer one wrote (schedule notices from 0.3.7)
           "notifications": len(a.call("GET", "/api/v1/notifications")["items"])}
    a.call("POST", "/api/v1/logout")
    return out


def _summary(a: CoreClient):
    """The summary endpoint exists from Core 0.3.6; an older Core answers NOT-FOUND."""
    try:
        return a.call("GET", "/api/v1/executions/summary?days=366")["total"]
    except CoreError:
        return None


def stop_core(p: subprocess.Popen, stop: Path) -> None:
    stop.write_text("stop", encoding="ascii")
    try:
        p.wait(60)
    except subprocess.TimeoutExpired:
        p.kill()


def table_counts(port: int, vault: WindowsVault, dbname: str) -> dict:
    import psycopg
    with psycopg.connect(db.conninfo(port, pg.SUPERUSER, vault.get("pg-superuser"), dbname)) as c:
        present = [t for t in TABLES if c.execute("SELECT to_regclass(%s)", (f"public.{t}",)).fetchone()[0]]
        return {t: c.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in present}  # a table an older schema lacks is left out


def baseline(install: Path, data: Path, vault: str, account: dict, out: Path) -> None:
    """Counts taken by the version installed BEFORE an upgrade, on the data the upgrade will open
    (the app closed). The proof of the new version compares its own counts with these (review R4)."""
    stop = data / "baseline.stop"
    p, info = serve(install, data, vault, stop)
    try:
        cfg = json.loads((data / "host" / "host.json").read_text(encoding="utf-8-sig"))
        rep = {"schema": "redrise.proof/1", "kind": "baseline_before_upgrade", "install": install.name,
               "api": counts(info, account), "tables": table_counts(cfg["pg_port"], WindowsVault(vault), db.DBNAME)}
    finally:
        stop_core(p, stop)
        stop.unlink(missing_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False))


def deleted_users(port: int, vault: WindowsVault, dbname: str) -> int:
    """Accounts deleted logically (migration 011, Core 0.3.8): a newer Core leaves them out of its list, an older
    one lists them as inactive (the database still refuses to reactivate them: users_deleted_inactive)."""
    import psycopg
    with psycopg.connect(db.conninfo(port, pg.SUPERUSER, vault.get("pg-superuser"), dbname)) as c:
        has = c.execute("SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'deleted_at'").fetchone()
        return c.execute("SELECT count(*) FROM users WHERE deleted_at IS NOT NULL").fetchone()[0] if has else 0


def drop_db(port: int, vault: WindowsVault, name: str) -> None:
    import psycopg
    with psycopg.connect(db.conninfo(port, pg.SUPERUSER, vault.get("pg-superuser"), "postgres"), autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{name}"')


def main() -> None:
    ap = argparse.ArgumentParser()
    for a in ("--data", "--account", "--out"):
        ap.add_argument(a, type=Path, required=True)
    ap.add_argument("--new", type=Path)
    ap.add_argument("--old", type=Path)
    ap.add_argument("--baseline-with", type=Path, help="only take the counts of this (previous) install and stop")
    ap.add_argument("--vault", required=True)
    a = ap.parse_args()
    account = json.loads(a.account.read_text(encoding="utf-8-sig"))
    if a.baseline_with:
        return baseline(a.baseline_with, a.data, a.vault, account, a.out)
    stop = a.data / "rollback-check.stop"
    report: dict = {"schema": "redrise.proof/1", "kind": "rollback_isolated_copy", "data": "isolated copy of the lab team"}

    p, info = serve(a.new, a.data, a.vault, stop)
    try:
        report["new"] = counts(info, account)
        port = json.loads((a.data / "host" / "host.json").read_text(encoding="utf-8-sig"))["pg_port"]
        report["new_tables"] = table_counts(port, WindowsVault(a.vault), db.DBNAME)
        report["deleted_users"] = deleted_users(port, WindowsVault(a.vault), db.DBNAME)
    finally:
        stop_core(p, stop)

    p, info = serve(a.old, a.data, a.vault, stop)
    try:
        report["old"] = counts(info, account)
        cfg = json.loads((a.data / "host" / "host.json").read_text(encoding="utf-8-sig"))
        report["old_tables"] = table_counts(cfg["pg_port"], WindowsVault(a.vault), db.DBNAME)
    finally:
        stop_core(p, stop)

    # Data recovery: backup and restore need the cluster up, so a Core of the new version serves the copy meanwhile.
    dump = a.data.parent / "rollback-check.dump"
    dump.unlink(missing_ok=True)
    target = "redrise_restore_check"
    py = [str(a.new / "runtime" / "python" / "python.exe"), "-B", "-m", "redrise_core", "--install-root", str(a.new), "--data-root", str(a.data),
          "--vault-namespace", a.vault]
    p, info = serve(a.new, a.data, a.vault, stop)
    try:
        b = subprocess.run(py + ["backup", "--out", str(dump)], capture_output=True, encoding="utf-8")
        report["backup"] = {"exit": b.returncode, "bytes": dump.stat().st_size if dump.exists() else 0}
        r = subprocess.run(py + ["restore", "--dump", str(dump), "--target-db", target], capture_output=True, encoding="utf-8")
        report["restore"] = {"exit": r.returncode, "target_db": target, "error": r.stderr[-300:] if r.returncode else None}
        cfg = json.loads((a.data / "host" / "host.json").read_text(encoding="utf-8-sig"))
        v = WindowsVault(a.vault)
        if r.returncode == 0:
            report["restored_tables"] = table_counts(cfg["pg_port"], v, target)
            report["live_tables"] = table_counts(cfg["pg_port"], v, db.DBNAME)
        drop_db(cfg["pg_port"], v, target)  # the copy is left as it was: a rerun can restore again (review R11)
        report["cleanup"] = {"restore_db_dropped": True}
    finally:
        stop_core(p, stop)
        dump.unlink(missing_ok=True)
    skip = ("core", "executions_366d", "users")
    # A Core before 0.3.8 knows no deleted_at and lists deleted accounts as inactive; 0.3.8 and later leave them out.
    old_lists_deleted = tuple(int(x) for x in str(report["old"]["core"]).split(".")[:3]) < (0, 3, 8)
    report["old_lists_deleted_accounts"] = old_lists_deleted
    same_api = ({k: v for k, v in report["new"].items() if k not in skip} == {k: v for k, v in report["old"].items() if k not in skip}
                and report["old"]["users"] == report["new"]["users"] + (report["deleted_users"] if old_lists_deleted else 0))
    report["passed"] = (same_api and report["new_tables"] == report["old_tables"] and report["backup"]["exit"] == 0
                        and report.get("restore", {}).get("exit") == 0 and report.get("restored_tables") == report.get("live_tables"))
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    print("PASSED" if report["passed"] else "FAILED")


if __name__ == "__main__":
    main()
