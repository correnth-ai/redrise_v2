"""Independent, read-only result verifiers shipped with the Runner (stdlib
only). They read the system of record (files, process/window list, final
URL); they never write and never call the Engine."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import re
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "rel": "http://schemas.openxmlformats.org/package/2006/relationships"}


def text_file_equals(path: Path, expected: str) -> dict:
    if not path.is_file():
        return {"verified": False, "code": "file_missing", "path": str(path)}
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {"verified": False, "code": "not_utf8", "path": str(path)}
    body = text.rstrip("\r\n")
    ok = body == expected
    return {"verified": ok, "code": None if ok else "content_mismatch", "path": str(path), "name": path.name,
            "encoding": "utf-8-bom" if bom else "utf-8", "content": body, "bytes": len(raw)}


# ---------------------------------------------------------------- XLSX

def _first_sheet_path(z: zipfile.ZipFile) -> str:
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    first = wb.find("m:sheets/m:sheet", NS)
    rid = first.get(f"{{{NS['r']}}}id")
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    for r in rels.findall("rel:Relationship", NS):
        if r.get("Id") == rid:
            target = r.get("Target").lstrip("/")
            return target if target.startswith("xl/") else "xl/" + target
    raise ValueError("first sheet not found")


def read_cells(path: Path, refs: list[str]) -> dict[str, object]:
    """Values of `refs` on the first sheet: str, int/float, bool or None."""
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
        sheet = ET.fromstring(z.read(_first_sheet_path(z)))
    found: dict[str, object] = {r: None for r in refs}
    for c in sheet.iter(f"{{{NS['m']}}}c"):
        ref = c.get("r")
        if ref not in found:
            continue
        t = c.get("t")
        v = c.find("m:v", NS)
        if t == "inlineStr":
            found[ref] = "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
        elif v is None:
            found[ref] = None
        elif t == "s":
            found[ref] = shared[int(v.text)]
        elif t == "str":
            found[ref] = v.text
        elif t == "b":
            found[ref] = v.text == "1"
        else:
            n = float(v.text)
            found[ref] = int(n) if n.is_integer() else n
    return found


def xlsx_cells(path: Path, expected: dict[str, object]) -> dict:
    """`expected` values: str (exact text), None (empty), "number:<n>" (numeric)."""
    if not path.is_file():
        return {"verified": False, "code": "file_missing", "path": str(path)}
    try:
        got = read_cells(path, list(expected))
    except (zipfile.BadZipFile, KeyError, ValueError, ET.ParseError) as e:
        return {"verified": False, "code": "not_xlsx", "path": str(path), "detail": str(e)}
    mismatches = {}
    for ref, want in expected.items():
        have = got[ref]
        if isinstance(want, str) and want.startswith("number:"):
            n = float(want.split(":", 1)[1])
            ok = isinstance(have, (int, float)) and not isinstance(have, bool) and float(have) == n
        else:
            ok = have == want and (want is None or isinstance(have, str))
        if not ok:
            mismatches[ref] = {"expected": want, "found": have}
    return {"verified": not mismatches, "code": None if not mismatches else "cells_mismatch",
            "path": str(path), "cells": got, "mismatches": mismatches}


# ---------------------------------------------------------------- windows

_user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None


def top_windows() -> list[dict]:
    from .apps import process_image  # local import: Windows only

    out: list[dict] = []
    if _user32 is None:
        return out

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if not _user32.IsWindowVisible(hwnd):
            return True
        pid = wt.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        buf = ctypes.create_unicode_buffer(256)
        _user32.GetClassNameW(hwnd, buf, 256)
        out.append({"hwnd": int(hwnd or 0), "pid": pid.value, "process_image": process_image(pid.value), "class": buf.value})
        return True

    _user32.EnumWindows(cb, 0)
    return out


def matching_windows(candidates: list[dict]) -> list[dict]:
    return [w for w in top_windows() for c in candidates
            if w["process_image"] == c["process_image"] and (c.get("class") is None or w["class"] == c["class"])]


def window_present(candidates: list[dict], timeout_ms: int, preexisting: list[dict] | None = None) -> dict:
    """The app's main window is present. A window that already existed before
    the launch is reported as such (`window_preexisting`), not as a new one."""
    before = {(w.get("hwnd"), w["process_image"]) for w in (preexisting or [])}
    deadline = time.monotonic() + timeout_ms / 1000
    while True:
        found = matching_windows(candidates)
        new = [w for w in found if (w.get("hwnd"), w["process_image"]) not in before]
        if new or (found and time.monotonic() > deadline):
            w = (new or found)[0]
            return {"verified": True, "code": None, "window": w, "window_preexisting": not new}
        if time.monotonic() > deadline:
            return {"verified": False, "code": "window_not_found", "candidates": candidates}
        time.sleep(0.5)


def browser_final_url(url: str | None, rules: list[dict], otherwise: dict) -> dict:
    if not url:
        return {"verified": False, "code": "no_final_url", "state": "unknown"}
    for r in rules:
        if url.startswith(r["prefix"]):
            res = {"verified": bool(r["verified"]), "state": r["state"], "final_url_origin": re.sub(r"^(https?://[^/]+).*$", r"\1", url)}
            if r.get("reason"):
                res["reason"] = r["reason"]
            res["code"] = None if r["verified"] else r["state"]
            return res
    return {"verified": bool(otherwise.get("verified")), "state": otherwise["state"], "code": otherwise["state"],
            "final_url_origin": re.sub(r"^(https?://[^/]+).*$", r"\1", url)}
