"""Installed browser discovery on this station (R09/G13): registered sources
(StartMenuInternet clients, App Paths) and known install locations, then
file presence and version. No recursive disk scan, no browser is started.
A detected browser is not a homologated one: `homologated` stays False until
a practical campaign proves opening/identification for that browser."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import winreg
from pathlib import Path

# id -> display name, executable image, known locations (env vars resolved per user/system).
CANDIDATES: dict[str, dict] = {
    "chrome": {"name": "Google Chrome", "image": "chrome.exe",
               "paths": [r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
                         r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
                         r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"]},
    "msedge": {"name": "Microsoft Edge", "image": "msedge.exe",
               "paths": [r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
                         r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
                         r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"]},
    "firefox": {"name": "Mozilla Firefox", "image": "firefox.exe",
                "paths": [r"%ProgramFiles%\Mozilla Firefox\firefox.exe", r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe"]},
    "chromium": {"name": "Chromium", "image": "chrome.exe",
                 "paths": [r"%LOCALAPPDATA%\Chromium\Application\chrome.exe", r"%ProgramFiles%\Chromium\Application\chrome.exe"]},
}
IMAGES = {c["image"] for c in CANDIDATES.values()}
# Identified only where a local HTML actually opened (B03, decision of 01/11/2026); never discovered,
# offered or chosen for a site.
HTML_ONLY: dict[str, dict] = {"brave": {"name": "Brave", "image": "brave.exe"}}
HTML_IMAGES = IMAGES | {c["image"] for c in HTML_ONLY.values()}


def display_name(browser_id: str | None) -> str | None:
    return (CANDIDATES.get(browser_id or "") or HTML_ONLY.get(browser_id or "") or {}).get("name")


def classify(exe: str) -> str | None:
    """Browser id of an executable path, by image name (and folder for Chromium)."""
    p = exe.replace("/", "\\").lower()
    name = p.rsplit("\\", 1)[-1]
    if name == "msedge.exe":
        return "msedge"
    if name == "brave.exe":
        return "brave"
    if name == "firefox.exe":
        return "firefox"
    if name == "chrome.exe":
        return "chromium" if "\\chromium\\" in p else "chrome" if "\\google\\chrome\\application\\" in p else None
    return None


def _clean(cmd: str) -> str:
    cmd = os.path.expandvars(cmd.strip())
    if cmd.startswith('"'):
        return cmd[1:].split('"', 1)[0]
    return cmd.split(" -", 1)[0].strip()


def _registered() -> list[tuple[str, str]]:
    """(path, source) from StartMenuInternet clients and App Paths, user and machine, both views."""
    out: list[tuple[str, str]] = []
    roots = [(winreg.HKEY_CURRENT_USER, "HKCU"), (winreg.HKEY_LOCAL_MACHINE, "HKLM")]
    for hive, hname in roots:
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\Clients\StartMenuInternet", 0, winreg.KEY_READ | view) as k:
                    for i in range(winreg.QueryInfoKey(k)[0]):
                        sub = winreg.EnumKey(k, i)
                        try:
                            with winreg.OpenKey(k, sub + r"\shell\open\command") as c:
                                out.append((_clean(winreg.QueryValue(c, None)), f"{hname}:StartMenuInternet"))
                        except OSError:
                            continue
            except OSError:
                pass
            for image in sorted(IMAGES):
                try:
                    with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{image}", 0,
                                        winreg.KEY_READ | view) as k:
                        out.append((_clean(winreg.QueryValue(k, None)), f"{hname}:AppPaths"))
                except OSError:
                    continue
    return out


def file_version(path: str) -> str | None:
    """Product version from the executable's version resource (read-only)."""
    ver = ctypes.windll.version
    size = ver.GetFileVersionInfoSizeW(path, None)
    if not size:
        return None
    buf = ctypes.create_string_buffer(size)
    if not ver.GetFileVersionInfoW(path, 0, size, buf):
        return None
    ptr, n = ctypes.c_void_p(), wt.UINT()
    if not ver.VerQueryValueW(buf, "\\", ctypes.byref(ptr), ctypes.byref(n)) or not n.value:
        return None
    ffi = ctypes.cast(ptr, ctypes.POINTER(wt.DWORD * 13)).contents  # VS_FIXEDFILEINFO
    ms, ls = ffi[4], ffi[5]  # dwProductVersionMS/LS
    return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"


def discover() -> dict:
    """{"browsers": [...], "checked": [{"id", "status"}]}; status: found | absent | failed."""
    found: dict[str, dict] = {}
    errors: dict[str, str] = {}
    try:
        registered = _registered()
    except Exception as e:  # noqa: BLE001 - a failed registry query is not "absent"
        registered, errors["registry"] = [], type(e).__name__
    known = [(os.path.expandvars(p), "known_path") for c in CANDIDATES.values() for p in c["paths"]]
    seen: set[str] = set()
    for path, source in registered + known:
        if not path or "%" in path:
            continue
        key = os.path.normcase(os.path.normpath(path))
        bid = classify(path)
        if key in seen or bid not in CANDIDATES or bid in found:
            continue
        seen.add(key)
        try:
            if not Path(path).is_file():
                continue
            version = file_version(path)
        except OSError as e:
            errors[bid] = type(e).__name__
            continue
        found[bid] = {"id": bid, "name": CANDIDATES[bid]["name"], "path": path, "version": version,
                      "source": source, "homologated": False}
    checked = [{"id": b, "status": "found" if b in found else "failed" if b in errors else "absent"} for b in CANDIDATES]
    if "registry" in errors:
        checked.append({"id": "registry", "status": "failed", "detail": errors["registry"]})
    return {"browsers": list(found.values()), "checked": checked}


def resolve(browser_id: str) -> dict | None:
    """The chosen browser on this station, or None (no substitution by another browser)."""
    return next((b for b in discover()["browsers"] if b["id"] == browser_id), None)
