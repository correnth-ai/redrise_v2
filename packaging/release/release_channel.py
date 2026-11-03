"""Release channel tool (P11): Ed25519 key in the OS vault, signed manifest.

    keygen                      create the channel key in the vault if absent; print the public key (base64)
    sign --installer F --version V --out DIR [--notes TEXT]
                                write DIR/latest.json, DIR/latest.json.sig and copy the installer;
                                refused unless verification.json beside the installer passed for it

The private key never touches a file, log or argv; it lives only in Windows
Credential Manager (RedRise/release/channel-ed25519). Run with the lab python
with contracts/python and the cryptography package on sys.path."""

from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import json
import shutil
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from redrise_contracts.vault import WindowsVault

NAME = "channel-ed25519"


def _key(create: bool) -> Ed25519PrivateKey:
    v = WindowsVault("release")
    raw = v.get(NAME)
    if raw is None:
        if not create:
            sys.exit("no channel key in the vault; run keygen")
        k = Ed25519PrivateKey.generate()
        v.set(NAME, base64.b64encode(k.private_bytes_raw()).decode())
        return k
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(raw))


def public_b64(k: Ed25519PrivateKey) -> str:
    return base64.b64encode(k.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("keygen")
    s = sub.add_parser("sign")
    s.add_argument("--installer", type=Path, required=True)
    s.add_argument("--version", required=True)
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--notes", default="")
    a = ap.parse_args()
    if a.cmd == "keygen":
        print(public_b64(_key(True)))
        return 0
    if a.installer.name != f"RedRise-Setup-{a.version}.exe":
        sys.exit(f"installer name does not match version {a.version}: {a.installer.name}")
    data = a.installer.read_bytes()
    # Release gate: only an installer that passed verify-candidate.ps1 (isolated
    # install + functional template smoke) enters the update channel.
    ver_p = a.installer.parent / "verification.json"
    try:
        ver = json.loads(ver_p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        sys.exit(f"no verification record at {ver_p}; run packaging/release/verify-candidate.ps1 first")
    if not (ver.get("passed") is True and ver.get("version") == a.version
            and ver.get("installer_sha256") == hashlib.sha256(data).hexdigest()):
        sys.exit(f"verification record does not cover this installer as passed: {ver_p}")
    k = _key(False)
    manifest = {"schema": "redrise.release/1", "version": a.version, "notes": a.notes,
                "published_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "installer": {"file": a.installer.name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}}
    a.out.mkdir(parents=True, exist_ok=True)
    body = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    (a.out / "latest.json").write_bytes(body)
    (a.out / "latest.json.sig").write_text(base64.b64encode(k.sign(body)).decode(), encoding="ascii")
    if a.installer.resolve() != (a.out / a.installer.name).resolve():
        shutil.copyfile(a.installer, a.out / a.installer.name)
    print(json.dumps({"out": str(a.out), **manifest}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
