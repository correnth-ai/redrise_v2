"""Team host: private PostgreSQL + migrations + TLS + API, app-managed.

Layout (P05-D2/D3): binaries in the install root; mutable state in
`<data>/host/{pgdata,logs,backups,tls,host.json}`; secrets only in the vault."""

from __future__ import annotations

import json
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import psycopg

from . import db, identity, pg, tls
from .api import ApiServer
from .service import Core
from redrise_contracts.vault import WindowsVault

DEFAULT_PORT = 47800


@dataclass
class HostPaths:
    install_root: Path
    data_root: Path
    pg_bin: Path | None = None  # testing only; default <install>/postgres/bin

    @property
    def host(self) -> Path:
        return self.data_root / "host"

    @property
    def config(self) -> Path:
        return self.host / "host.json"

    def cluster(self, port: int) -> pg.Cluster:
        return pg.Cluster(self.pg_bin or self.install_root / "postgres" / "bin", self.host / "pgdata", port,
                          self.host / "logs" / "postgres.log")


def load_templates(install_root: Path) -> dict[str, dict]:
    out = {}
    for f in sorted((install_root / "templates").glob("*/template.json")):
        t = json.loads(f.read_text(encoding="utf-8"))
        out[t["id"]] = t
    return out


def _read_config(p: HostPaths) -> dict:
    return json.loads(p.config.read_text(encoding="utf-8")) if p.config.is_file() else {}


def _write_config(p: HostPaths, cfg: dict) -> None:
    p.host.mkdir(parents=True, exist_ok=True)
    tmp = p.config.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    tmp.replace(p.config)


def prepare(p: HostPaths, vault: WindowsVault, lan_port: int | None = None, bind: str = "0.0.0.0",
            log=print) -> dict:
    """Idempotent host preparation: secrets, cluster, migrations (backup
    first when a database already exists), certificate, config."""
    cfg = _read_config(p)
    cfg.setdefault("pg_port", pg.free_port())
    cfg["lan_port"] = lan_port if lan_port is not None else (cfg.get("lan_port") or DEFAULT_PORT)
    cfg["bind"] = bind
    su = vault.ensure("pg-superuser")
    app = vault.ensure("pg-app")
    cluster = p.cluster(cfg["pg_port"])
    fresh = not cluster.initialized
    cluster.init(su)
    cluster.start()
    cluster.wait_ready()
    if not fresh:
        with psycopg.connect(db.conninfo(cfg["pg_port"], pg.SUPERUSER, su, "postgres"), autocommit=True) as c:
            exists = c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db.DBNAME,)).fetchone()
        if exists:
            with psycopg.connect(db.conninfo(cfg["pg_port"], pg.SUPERUSER, su)) as c:
                pending = db.pending_migrations(c)
                c.commit()
            if pending:
                out = p.host / "backups" / f"pre-migration-{time.strftime('%Y%m%d-%H%M%S')}.dump"
                cluster.dump(db.DBNAME, out, su)
                log(f"backup before migration: {out.name}")
    applied = db.provision(cfg["pg_port"], pg.SUPERUSER, su, app)
    cert, key, fp = tls.ensure_cert(p.host / "tls")
    cfg["fingerprint"] = fp
    _write_config(p, cfg)
    return {"pg_port": cfg["pg_port"], "lan_port": cfg["lan_port"], "migrations_applied": applied, "fingerprint": fp,
            "join_code": tls.join_code(socket.gethostname(), cfg["lan_port"], fp)}


class Host:
    def __init__(self, p: HostPaths, vault: WindowsVault, log=print):
        self.p, self.vault, self.log = p, vault, log
        self.api: ApiServer | None = None
        self.database: db.Database | None = None

    def start(self, lan_port: int | None = None, bind: str = "0.0.0.0") -> dict:
        info = prepare(self.p, self.vault, lan_port, bind, self.log)
        cfg = _read_config(self.p)
        self.database = db.Database(db.conninfo(cfg["pg_port"], db.APP_ROLE, self.vault.get("pg-app")))
        self.core = core = Core(self.database, load_templates(self.p.install_root), identity.load_verifier(self.p.install_root))
        core.ensure_welcome_process()
        self.api = ApiServer(core, bind, cfg["lan_port"], self.p.host / "tls" / "host-cert.pem",
                             self.p.host / "tls" / "host-key.pem", log=self.log).start()
        info["lan_port"] = self.api.port
        return info

    def stop(self) -> None:
        if self.api:
            self.api.stop()
        if self.database:
            self.database.close()
        cfg = _read_config(self.p)
        if cfg.get("pg_port"):
            self.p.cluster(cfg["pg_port"]).stop()

    def backup(self, out: Path) -> Path:
        cfg = _read_config(self.p)
        self.p.cluster(cfg["pg_port"]).dump(db.DBNAME, out, self.vault.get("pg-superuser"))
        return out

    def restore(self, dump: Path, target_db: str) -> None:
        if target_db == db.DBNAME:
            raise pg.PgError("restore_target_is_live", "restore goes to a separate database")
        cfg = _read_config(self.p)
        self.p.cluster(cfg["pg_port"]).restore(dump, target_db, self.vault.get("pg-superuser"))


def serve_forever(host: Host, stop: threading.Event, **kw) -> None:
    info = host.start(**kw)
    host.log(json.dumps({"event": "core_ready", **info}))
    try:
        while not stop.wait(1):
            pass
    finally:
        host.stop()
