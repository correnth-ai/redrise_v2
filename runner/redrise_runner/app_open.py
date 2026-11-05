"""Opening a registered destination: an installed application or a file chosen by the person.

discover: what the Start menu of this station can launch (Get-StartApps, no disk
          scan), plus the detected browsers, which keep their own opening rules.
prepare:  resolves the destination and its dependencies, one reported check per
          operation. It never opens the destination.
open_target: launches exactly the resolved destination and confirms a window of
          it reached the screen: of its program when that is known, of its package
          for a Store app, otherwise of a process that did not exist before. A toast,
          an error dialog or someone switching windows confirms nothing. Nothing is
          closed or repeated; without confirmation the result is uncertain, since the
          launch may have worked."""

from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Callable

from . import apps, browsers, verifiers

Report = Callable[[str, str, str | None], None]
OPEN_TIMEOUT_S = 30.0
POLL_S = 0.25
FRAME_HOST = "applicationframehost.exe"
_POWERSHELL = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
_START_APPS = ("[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
               "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress")
_NOT_APPS = (".url", ".chm", ".txt", ".pdf", ".htm", ".html", ".lnk", ".rtf", ".md", ".log", ".ini")
_UNINSTALL = re.compile(r"(^|[\\/])(unins|uninstall)[^\\/]*$", re.IGNORECASE)


def launchable(app_id: str) -> bool:
    """Start menu entries that start a program: not web links, documents or uninstallers."""
    low = app_id.lower()
    return bool(app_id) and not low.startswith(("http:", "https:")) and not low.endswith(_NOT_APPS) and not _UNINSTALL.search(app_id)


def _start_apps() -> list[dict]:
    out = subprocess.run([str(_POWERSHELL), "-NoProfile", "-NonInteractive", "-Command", _START_APPS],
                         capture_output=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if out.returncode != 0:
        raise OSError(f"Get-StartApps exit {out.returncode}")
    raw = json.loads(out.stdout.decode("utf-8-sig") or "[]")
    return raw if isinstance(raw, list) else [raw]


def discover(start_apps: Callable[[], list[dict]] = _start_apps, found_browsers: Callable[[], list[dict]] | None = None) -> list[dict]:
    """[{id, name, browser_id?}] sorted by name. A detected browser replaces its Start menu entry."""
    known = (found_browsers or (lambda: browsers.discover()["browsers"]))()
    names = {b["name"].casefold() for b in known}
    entries = {}
    for a in start_apps():
        name, app_id = str(a.get("Name") or "").strip(), str(a.get("AppID") or "").strip()
        if name and launchable(app_id) and name.casefold() not in names:
            entries.setdefault((name.casefold(), app_id), {"id": app_id, "name": name})
    listed = list(entries.values()) + [{"id": f"browser:{b['id']}", "name": b["name"], "browser_id": b["id"]} for b in known]
    return sorted(listed, key=lambda x: x["name"].casefold())


def association_program(path: str) -> str | None:
    """The program Windows opens this file type with, or None."""
    ext = Path(path).suffix
    if not ext:
        return None
    buf = ctypes.create_unicode_buffer(1024)
    n = ctypes.c_uint32(len(buf))
    # AssocQueryStringW(ASSOCF_INIT_IGNOREUNKNOWN, ASSOCSTR_EXECUTABLE, ext, "open", out, &n). Without a
    # program, Windows may answer with its "Open with" dialog, which is not an association.
    hr = ctypes.windll.shlwapi.AssocQueryStringW(0x400, 2, ext, "open", buf, ctypes.byref(n))
    return buf.value if hr == 0 and buf.value and Path(buf.value).name.lower() != "openwith.exe" else None


def _image_of(path: str) -> str:
    return re.split(r"[\\/]", path)[-1].lower()


def resolve_target(target: dict, listed: Callable[[], list[dict]] = discover, associated: Callable[[str], str | None] = association_program) -> dict:
    """{"how", "launch", "name", "image"?, "package"?} or {"code", "detail"} when it cannot be opened on this station."""
    name = str(target.get("name") or "")
    if target.get("kind") == "app":
        app_id = str(target.get("app_id") or "")
        if not any(a["id"] == app_id for a in listed()):
            return {"code": "app_target_not_found", "detail": name or app_id}
        out = {"how": "start_menu", "launch": "shell:AppsFolder\\" + app_id, "name": name}
        office = re.search(r"([\w-]+)\.exe(\.|$)", _image_of(app_id))  # also Office style ids, as Vendor.Product.WINWORD.EXE.15
        if office:
            out["image"] = office.group(1) + ".exe"
        elif "!" in app_id:
            out["package"] = app_id.split("!", 1)[0].split("_", 1)[0]  # Store app: Name_publisher!App
        return out
    if target.get("kind") == "file":
        path = str(target.get("path") or "")
        if not Path(path).is_file():
            return {"code": "app_target_not_found", "detail": path}
        if path.lower().endswith(".exe"):
            return {"how": "program", "launch": path, "name": name or Path(path).name, "image": _image_of(path)}
        program = associated(path)
        if not program:
            return {"code": "app_no_association", "detail": path}
        return {"how": "association", "launch": path, "name": name or Path(path).name, "image": _image_of(program)}
    return {"code": "invalid_job", "detail": "unknown destination"}


def prepare_app(config: dict, report: Report, listed: Callable[[], list[dict]] = discover, associated: Callable[[str], str | None] = association_program) -> dict:
    report("target", "running", None)
    resolved = resolve_target((config or {}).get("target") or {}, listed, associated)
    if "code" in resolved:
        report("target", "failed", resolved["detail"])
        return {"state": "failed", "code": resolved["code"], "detail": resolved["detail"]}
    report("target", "ok", resolved["name"])
    report("launch", "ok", resolved["how"])
    return {"state": "verified", "verified": True, "context": {"resolved": resolved}}


def prepare_browser(config: dict, report: Report, resolve_browser=browsers.resolve) -> dict:
    """Same checks the opening itself does first (browser_open.run); no browser is started."""
    report("target", "running", None)
    if config.get("origin") == "site":
        browser = resolve_browser(config.get("browser") or "")
        if browser is None:
            report("target", "failed", config.get("browser"))
            return {"state": "refused", "code": "browser_not_found", "detail": config.get("browser")}
        report("target", "ok", browser["name"])
        report("launch", "ok", config.get("url"))
        return {"state": "verified", "verified": True, "context": {"resolved": {"how": "browser", "browser": browser["id"], "name": browser["name"]}}}
    path = config.get("path") or ""
    if not Path(path).is_file():
        report("target", "failed", path)
        return {"state": "refused", "code": "input_missing", "detail": path}
    report("target", "ok", Path(path).name)
    report("launch", "ok", "association")
    return {"state": "verified", "verified": True, "context": {"resolved": {"how": "association", "path": path, "name": Path(path).name}}}


def _launch(target: str) -> None:
    os.startfile(target)  # noqa: S606 - the destination the person registered, through the Windows shell


def open_target(resolved: dict, launch: Callable[[str], None] = _launch, windows: Callable[[], list[dict]] = verifiers.top_windows,
                foreground: Callable[[], int] = apps.foreground_window, running: Callable[[], set[int]] = apps.running_pids,
                path_of: Callable[[int], str] = apps.process_path, timeout_s: float = OPEN_TIMEOUT_S,
                clock=time.monotonic, sleep=time.sleep, text_of: Callable[[int], str] = apps.window_title) -> dict:
    """Confirmed by a new window of this destination, or by one already open coming to the front."""
    before = {w["hwnd"] for w in windows()}
    pids_before = running()
    previous = foreground()
    image, package = resolved.get("image"), (resolved.get("package") or "").lower()
    title = (resolved.get("title") or "").lower()  # when given, only a window showing it counts

    def package_running() -> bool:
        return any(package in path_of(p).lower() for p in running())

    def ours(w: dict) -> bool:
        if title and title not in text_of(w["hwnd"]).lower():
            return False
        if image:
            return w["process_image"] == image
        if package:  # a Store app shows through the frame host, or through its own process
            return package in path_of(w["pid"]).lower() or (w["process_image"] == FRAME_HOST and package_running())
        # Nothing names the program: a window of a process that did not exist, and only in front (see below).
        return w["pid"] not in pids_before

    identified = bool(image or package)
    try:
        launch(resolved["launch"])
    except OSError as e:
        return {"state": "failed", "code": "app_open_failed", "detail": resolved.get("name"), "reason": type(e).__name__}
    deadline = clock() + timeout_s
    while True:
        current = windows()
        fg = foreground()
        new = [w for w in current if w["hwnd"] not in before and ours(w)]
        hit = next((w for w in new if w["hwnd"] == fg), new[0] if new and identified else None)
        if hit is None and fg != previous:
            hit = next((w for w in current if w["hwnd"] == fg and ours(w)), None)
        if hit is not None:
            return {"state": "verified", "verified": True, "context": {"opened": {
                "name": resolved.get("name"), "how": resolved.get("how"), "hwnd": hit["hwnd"], "pid": hit["pid"],
                "image": hit["process_image"], "new_window": hit["hwnd"] not in before}}}
        if clock() >= deadline:
            return {"state": "uncertain", "code": "app_open_unconfirmed", "detail": resolved.get("name")}
        sleep(POLL_S)
