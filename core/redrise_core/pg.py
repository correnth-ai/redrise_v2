"""Private PostgreSQL lifecycle (P05-D2): initdb / start / stop / status /
dump / restore with the packaged binaries, bound to 127.0.0.1 only.
The superuser password comes from the vault and is passed to initdb through
a short-lived file in the cluster's parent folder, removed immediately."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SUPERUSER = "redrise_admin"


class PgError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class Cluster:
    bin_dir: Path        # <install>/postgres/bin
    data_dir: Path       # <data>/host/pgdata
    port: int
    log_file: Path

    def _exe(self, name: str) -> str:
        p = self.bin_dir / f"{name}.exe"
        if not p.is_file():
            raise PgError("postgres_missing", str(p))
        return str(p)

    def _run(self, args: list[str], timeout: float = 120, env: dict | None = None) -> subprocess.CompletedProcess:
        e = {k: v for k, v in os.environ.items() if not k.upper().startswith("PG")}  # never inherit PG* settings
        e.update(env or {})
        return subprocess.run(args, capture_output=True, timeout=timeout, creationflags=NO_WINDOW, env=e,
                              stdin=subprocess.DEVNULL)

    @property
    def initialized(self) -> bool:
        return (self.data_dir / "PG_VERSION").is_file()

    def init(self, superuser_password: str) -> None:
        if self.initialized:
            return
        self.data_dir.parent.mkdir(parents=True, exist_ok=True)
        pw = self.data_dir.parent / f".pw-{os.getpid()}"
        try:
            pw.write_text(superuser_password, encoding="utf-8")
            r = self._run([self._exe("initdb"), "-D", str(self.data_dir), "-U", SUPERUSER, "--pwfile", str(pw),
                           "-A", "scram-sha-256", "-E", "UTF8", "--locale=C"], timeout=300)
        finally:
            pw.unlink(missing_ok=True)
        if r.returncode != 0:
            raise PgError("initdb_failed", r.stderr.decode("utf-8", "replace")[-500:])
        # Loopback only; stations talk to the Core API, never to PostgreSQL.
        with open(self.data_dir / "postgresql.auto.conf", "a", encoding="utf-8") as f:
            f.write("listen_addresses = '127.0.0.1'\n")
        (self.data_dir / "pg_hba.conf").write_text(
            "host all all 127.0.0.1/32 scram-sha-256\n", encoding="utf-8")

    def running(self) -> bool:
        r = self._run([self._exe("pg_ctl"), "status", "-D", str(self.data_dir)], timeout=30)
        return r.returncode == 0

    def start(self, timeout_s: float = 60) -> None:
        if self.running():
            return
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        # No pipes: the server started by pg_ctl inherits its handles, so captured
        # pipes would never reach EOF. pg_ctl's own output goes to a file.
        ctl_log = self.log_file.with_name("pg_ctl.log")
        e = {k: v for k, v in os.environ.items() if not k.upper().startswith("PG")}
        with open(ctl_log, "ab") as out:
            rc = subprocess.run([self._exe("pg_ctl"), "start", "-D", str(self.data_dir), "-l", str(self.log_file), "-w",
                                 "-t", str(int(timeout_s)), "-o", f"-p {self.port} -c listen_addresses=127.0.0.1"],
                                stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, env=e,
                                creationflags=NO_WINDOW, timeout=timeout_s + 30).returncode
        if rc != 0:
            raise PgError("postgres_start_failed", ctl_log.read_text(encoding="utf-8", errors="replace")[-500:])

    def stop(self) -> None:
        if self.running():
            self._run([self._exe("pg_ctl"), "stop", "-D", str(self.data_dir), "-m", "fast", "-w"], timeout=90)

    def wait_ready(self, timeout_s: float = 30) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            r = self._run([self._exe("pg_isready"), "-h", "127.0.0.1", "-p", str(self.port)], timeout=10)
            if r.returncode == 0:
                return
            time.sleep(0.3)
        raise PgError("postgres_not_ready", f"port {self.port}")

    def dump(self, dbname: str, out: Path, password: str) -> None:
        out.parent.mkdir(parents=True, exist_ok=True)
        r = self._run([self._exe("pg_dump"), "-h", "127.0.0.1", "-p", str(self.port), "-U", SUPERUSER, "-Fc",
                       "-f", str(out), dbname], timeout=600, env={"PGPASSWORD": password})
        if r.returncode != 0:
            out.unlink(missing_ok=True)
            raise PgError("backup_failed", r.stderr.decode("utf-8", "replace")[-500:])

    def restore(self, dump: Path, target_db: str, password: str) -> None:
        """Restores into a NEW database `target_db` (refuses an existing one)."""
        env = {"PGPASSWORD": password}
        r = self._run([self._exe("createdb"), "-h", "127.0.0.1", "-p", str(self.port), "-U", SUPERUSER, target_db],
                      env=env)
        if r.returncode != 0:
            raise PgError("restore_target_exists_or_failed", r.stderr.decode("utf-8", "replace")[-500:])
        r = self._run([self._exe("pg_restore"), "-h", "127.0.0.1", "-p", str(self.port), "-U", SUPERUSER,
                       "--no-owner", "--role", SUPERUSER, "-d", target_db, str(dump)], timeout=600, env=env)
        if r.returncode != 0:
            raise PgError("restore_failed", r.stderr.decode("utf-8", "replace")[-500:])
