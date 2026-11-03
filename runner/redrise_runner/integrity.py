"""Install integrity: every file listed in `manifest.json` must exist with
its recorded SHA-256, and no unlisted file may appear in the install tree
(binaries are never mutated at runtime)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(install_root: Path) -> dict:
    mpath = install_root / "manifest.json"
    if not mpath.is_file():
        return {"ok": False, "code": "manifest_missing"}
    manifest = json.loads(mpath.read_text(encoding="utf-8-sig"))
    listed = {f["path"]: f["sha256"] for f in manifest["files"]}
    missing, modified = [], []
    for rel, digest in listed.items():
        p = install_root / rel
        if not p.is_file():
            missing.append(rel)
        elif _sha256(p) != digest:
            modified.append(rel)
    present = {p.relative_to(install_root).as_posix() for p in install_root.rglob("*") if p.is_file()}
    # uninstall.exe is written by the installer itself (stub without payload, P10).
    unexpected = sorted(present - set(listed) - {"manifest.json", "uninstall.exe"})
    ok = not (missing or modified or unexpected)
    return {"ok": ok, "code": None if ok else "integrity_failed", "files": len(listed),
            "missing": missing[:20], "modified": modified[:20], "unexpected": unexpected[:20]}
