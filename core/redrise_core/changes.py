"""What changed on the Core, for screens to refresh when something really changed.

PostgreSQL announces each committed change by domain (migration 009, NOTIFY, so a
rollback announces nothing and a transaction never waits on a counter row). One
listener keeps a sequence here, and a client asks for what is newer than the
sequence it has, waiting a bounded time. It only says "read again": the data
still comes from the usual endpoints, with their permissions. If the listener is
down, clients still have their slow periodic read, and it counts a change for
everything when it comes back, since it may have missed some."""

from __future__ import annotations

import threading
import uuid

import psycopg

CHANNEL = "rr_changes"
MAX_WAIT_S = 20.0
EVERYTHING = "*"


class ChangeFeed:
    def __init__(self, conninfo: str | None, log=None):
        self.conninfo, self.log = conninfo, log
        self.epoch = uuid.uuid4().hex  # a new Core restarts the sequence: a client with another epoch reads again
        self.seq = 0
        self._last: dict[str, int] = {}
        self._cond = threading.Condition()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.conninfo and not self._thread:
            self._thread = threading.Thread(target=self._listen, name="core-changes", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._cond:
            self._cond.notify_all()
        if self._thread:
            self._thread.join(timeout=3)

    def bump(self, domain: str) -> None:
        with self._cond:
            self.seq += 1
            self._last[domain] = self.seq
            self._cond.notify_all()

    def _listen(self) -> None:
        first = True
        while not self._stop.is_set():
            try:
                with psycopg.connect(self.conninfo, autocommit=True) as conn:
                    conn.execute(f"LISTEN {CHANNEL}")
                    if not first:
                        self.bump(EVERYTHING)
                    first = False
                    while not self._stop.is_set():
                        for n in conn.notifies(timeout=1.0):
                            self.bump(n.payload)
            except Exception as e:  # noqa: BLE001 - nothing may end the listener: clients would only have the slow read
                if self.log and not self._stop.is_set():
                    self.log(f"change feed reconnecting: {type(e).__name__}")
                self._stop.wait(2.0)

    def since(self, seq, epoch, wait_s=0.0) -> dict:
        """Waits up to wait_s for something newer than seq. The answer's seq is what to send next."""
        wait = min(max(float(wait_s) if isinstance(wait_s, (int, float)) else 0.0, 0.0), MAX_WAIT_S)
        with self._cond:
            if epoch != self.epoch or not isinstance(seq, int):
                return {"epoch": self.epoch, "seq": self.seq, "domains": [EVERYTHING]}
            self._cond.wait_for(lambda: self.seq > seq or self._stop.is_set(), timeout=wait)
            return {"epoch": self.epoch, "seq": self.seq, "domains": sorted(d for d, s in self._last.items() if s > seq)}
