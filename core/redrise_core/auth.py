"""Passwords (scrypt, stdlib) and opaque tokens stored only as hashes (P05-D6)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

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
