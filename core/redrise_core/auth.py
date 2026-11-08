"""Passwords (scrypt, stdlib) and opaque tokens stored only as hashes (P05-D6)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time

_N, _R, _P = 2 ** 14, 8, 1
MIN_PASSWORD = 8


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        kind, n, r, p, salt, dk = stored.split("$")
        if kind != "scrypt":
            return False
        got = hashlib.scrypt(pw.encode("utf-8"), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(got, base64.b64decode(dk))
    except (ValueError, TypeError):
        return False


def new_token() -> tuple[str, bytes]:
    """(token for the client, sha256 to store)."""
    t = secrets.token_urlsafe(32)
    return t, token_hash(t)


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


# A real hash to compare against when the user does not exist (uniform timing).
DUMMY_HASH = hash_password(secrets.token_urlsafe(12))


class AttemptLimiter:
    """Sign-in and sign-up attempts, in Core memory (decision of 2026-11-07).

    After LIMIT counted attempts within WINDOW_S on one key, that key waits FIRST_WAIT_S;
    each new wait on the same key doubles, up to MAX_WAIT_S. Nothing is permanent: a key
    with no counted attempt for MAX_WAIT_S after its last wait is forgotten, a success
    clears what the account caused, and a restart clears everything. While a key waits,
    the request is refused before the password is checked, so a wait reveals nothing and
    refused requests do not lengthen it."""

    LIMIT, WINDOW_S, FIRST_WAIT_S, MAX_WAIT_S = 5, 300.0, 60.0, 900.0
    MAX_KEYS = 4096  # memory bound; above it, the stalest keys are dropped first

    def __init__(self, clock=None):
        self.clock = clock or time.monotonic
        self._lock = threading.Lock()
        # key -> {"hits": [(t, account)], "until": t, "level": n, "last": t, "accounts": accounts that counted here}
        self._keys: dict[tuple, dict] = {}

    def _entry(self, key, now):
        e = self._keys.get(key)
        if e is not None and now >= max(e["until"], e["last"]) + self.MAX_WAIT_S:
            del self._keys[key]
            e = None
        return e

    def _wait(self, keys, now) -> int:
        left = 0.0
        for k in keys:
            e = self._entry(k, now)
            if e is not None:
                left = max(left, e["until"] - now)
        return int(left + 0.999) if left > 0 else 0

    def _hit(self, keys, account, now) -> None:
        if len(self._keys) > self.MAX_KEYS:
            for k in sorted(self._keys, key=lambda k: self._keys[k]["last"])[: len(self._keys) - self.MAX_KEYS]:
                del self._keys[k]
        for k in keys:
            e = self._entry(k, now) or self._keys.setdefault(k, {"hits": [], "until": 0.0, "level": 0, "last": now, "accounts": set()})
            e["hits"] = [h for h in e["hits"] if h[0] > now - self.WINDOW_S] + [(now, account)]
            e["last"] = now
            e["accounts"].add(account)
            if len(e["hits"]) >= self.LIMIT:
                e["until"] = now + min(self.FIRST_WAIT_S * 2 ** e["level"], self.MAX_WAIT_S)
                e["level"] += 1
                e["hits"] = []

    def wait_s(self, keys) -> int:
        """Seconds still to wait (0: may try now), the longest over the keys."""
        with self._lock:
            return self._wait(keys, self.clock())

    def hit(self, keys, account: str | None = None) -> None:
        """Counts one attempt on each key; a key reaching LIMIT starts its next wait."""
        with self._lock:
            self._hit(keys, account, self.clock())

    def attempt(self, keys, account: str | None = None) -> int:
        """Check and count in one step, BEFORE the slow password check: seconds to wait (nothing
        counted), or 0 with this attempt counted. Parallel requests cannot all pass the check before
        any of them is counted. A right password then calls success(), which forgets the attempt."""
        with self._lock:
            now = self.clock()
            left = self._wait(keys, now)
            if not left:
                self._hit(keys, account, now)
            return left

    def success(self, account_key, client_key, account: str) -> None:
        """A right password: the account starts over, and so does the client address unless it
        also counted attempts on other accounts; then only the failures on this account are forgotten."""
        with self._lock:
            self._keys.pop(account_key, None)
            e = self._keys.get(client_key)
            if e is not None:
                e["hits"] = [h for h in e["hits"] if h[1] != account]
                e["accounts"].discard(account)
                if not e["accounts"]:
                    del self._keys[client_key]
