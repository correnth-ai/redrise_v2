"""Station connection to a team host (P05-D5/D6).

`join`: join code (host, port, certificate fingerprint) + an administrator's
login on this station -> registers the station and keeps its runner token in
the OS vault. `<data>/agent/connection.json` holds only non-secret data."""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from pathlib import Path

from redrise_contracts.client import CoreClient
from redrise_contracts.vault import WindowsVault

from .jobs import _write_atomic

TOKEN = "runner-token"


@dataclass
class Connection:
    host: str
    port: int
    fingerprint: str
    station_id: int
    station_name: str

    @staticmethod
    def load(data_root: Path) -> "Connection | None":
        p = data_root / "agent" / "connection.json"
        if not p.is_file():
            return None
        return Connection(**json.loads(p.read_text(encoding="utf-8")))

    def save(self, data_root: Path) -> None:
        _write_atomic(data_root / "agent" / "connection.json", self.__dict__)


def parse_join_code(code: str) -> tuple[str, int, str]:
    parts = (code or "").strip().split(":")
    if len(parts) != 4 or parts[0] != "rr1" or not parts[2].isdigit() or len(parts[3]) != 64:
        raise ValueError("invalid connection code")
    return parts[1], int(parts[2]), parts[3].lower()


def join(data_root: Path, code: str, username: str, password: str, station_name: str | None = None,
         is_host: bool = False, vault: WindowsVault | None = None, host_override: str | None = None) -> Connection:
    host, port, fp = parse_join_code(code)
    host = host_override or host
    vault = vault or WindowsVault("station")
    c = CoreClient(host, port, fp, reported_by="RR-RUNNER")
    token = c.call("POST", "/api/v1/login", {"username": username, "password": password})["token"]
    admin = CoreClient(host, port, fp, token, reported_by="RR-RUNNER")
    try:
        s = admin.call("POST", "/api/v1/stations", {"name": station_name or socket.gethostname(), "is_host": is_host})
    finally:
        admin.call("POST", "/api/v1/logout")
    vault.set(TOKEN, s["runner_token"])
    conn = Connection(host, port, fp, s["station"]["id"], s["station"]["name"])
    conn.save(data_root)
    return conn


def client(data_root: Path, vault: WindowsVault | None = None) -> CoreClient | None:
    conn = Connection.load(data_root)
    token = (vault or WindowsVault("station")).get(TOKEN)
    if conn is None or not token:
        return None
    return CoreClient(conn.host, conn.port, conn.fingerprint, token, reported_by="RR-RUNNER")
