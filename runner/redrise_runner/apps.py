"""Target applications (preconditions, launch) and known folders.

Applications are the customer's own installs (Excel, Outlook) or Windows
components (Notepad); RedRise never installs or redistributes them."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
import winreg
from collections.abc import Callable
from pathlib import Path

from .paths import _guid  # known-folder GUID helper

FOLDERID_DESKTOP = "B4BFCC3A-DB2C-424C-B029-7FE99A87C641"


def known_folder(folder_id: str) -> Path:
    p = ctypes.c_wchar_p()
    hr = ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(_guid(folder_id)), 0, None, ctypes.byref(p))
    try:
        if hr != 0:
            raise OSError(f"SHGetKnownFolderPath 0x{hr & 0xFFFFFFFF:08X}")
        return Path(p.value)
    finally:
        ctypes.windll.ole32.CoTaskMemFree(p)


def desktop() -> Path:
    """Real (possibly OneDrive/redirected) Desktop of the current user."""
    return known_folder(FOLDERID_DESKTOP)


def _app_path(exe: str) -> Path | None:
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}") as k:
                v, _ = winreg.QueryValueEx(k, None)
                p = Path(v.strip('"'))
                if p.is_file():
                    return p
        except OSError:
            continue
    return None


def resolve(app: str) -> tuple[Path | None, str]:
    """Executable of a supported target app, or (None, reason)."""
    if app == "notepad":
        p = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "notepad.exe"
        return (p, "windows notepad") if p.is_file() else (None, "notepad_not_found")
    if app == "excel":
        p = _app_path("excel.exe")
        return (p, "microsoft excel") if p else (None, "excel_not_installed")
    if app == "outlook":
        p = _app_path("outlook.exe")
        if p:
            return p, "classic outlook"
        olk = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "olk.exe"
        return (olk, "new outlook") if olk.is_file() else (None, "outlook_not_installed")
    return None, f"unknown_app:{app}"


def launch(exe: Path, args: list[str]) -> int:
    """Starts the target app detached in the user's session; returns its pid."""
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    p = subprocess.Popen([str(exe), *args], creationflags=flags, close_fds=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return p.pid


def is_running(image: str) -> bool:
    """Any process of `image` (e.g. `excel.exe`), with or without a window.
    Win32 enumeration, not tasklist: no console output and no localized text."""
    ids = (ctypes.c_uint32 * 4096)()
    got = ctypes.c_uint32()
    if not ctypes.windll.psapi.EnumProcesses(ids, ctypes.sizeof(ids), ctypes.byref(got)):
        raise OSError("EnumProcesses failed")
    image = image.lower()
    return any(process_image(pid) == image for pid in ids[: got.value // 4] if pid)


def launched_window(image: str, cls: str, before: set[int], foreground: Callable[[], int],
                    windows: Callable[[], list[dict]], timeout_s: float = 30.0, quiet_s: float = 2.0,
                    poll_s: float = 0.25) -> int | None:
    """The top-level window the launch opened: a new `image`/`cls` window not in
    `before`. Waits until the set of new windows stops changing for `quiet_s`
    (an app may restore several windows from its last session), then prefers
    the one in the foreground, else the topmost. None if none appeared."""
    deadline = time.monotonic() + timeout_s
    seen: list[int] = []
    since = time.monotonic()
    while True:
        new = [w["hwnd"] for w in windows()
               if w["process_image"] == image and w["class"] == cls and w["hwnd"] not in before]
        now = time.monotonic()
        if new != seen:
            seen, since = new, now
        elif seen and now - since >= quiet_s:
            fg = foreground()
            return fg if fg in seen else seen[0]
        if now >= deadline:
            return None
        time.sleep(poll_s)


def foreground_window() -> int:
    return int(ctypes.windll.user32.GetForegroundWindow() or 0)


def close_windows(hwnds: list[int], timeout_s: float = 10.0) -> list[int]:
    """Asks windows to close as the title-bar X would (never a forced kill); an
    app may keep a window open, e.g. to ask about unsaved changes. Returns the
    windows still open after `timeout_s`."""
    u32 = ctypes.windll.user32
    for h in hwnds:
        u32.PostMessageW(h, 0x0112, 0xF060, 0)  # WM_SYSCOMMAND, SC_CLOSE
    deadline = time.monotonic() + timeout_s
    left = list(hwnds)
    while left and time.monotonic() < deadline:
        time.sleep(0.25)
        left = [h for h in left if u32.IsWindow(h)]
    return left


def window_title(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(512)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def process_path(pid: int) -> str:
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        n = ctypes.c_uint32(1024)
        if not k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return ""
        return buf.value
    finally:
        k32.CloseHandle(h)


def process_image(pid: int) -> str:
    path = process_path(pid)
    return Path(path).name.lower() if path else ""


def running_pids() -> set[int]:
    ids = (ctypes.c_uint32 * 4096)()
    got = ctypes.c_uint32()
    if not ctypes.windll.psapi.EnumProcesses(ids, ctypes.sizeof(ids), ctypes.byref(got)):
        raise OSError("EnumProcesses failed")
    return {pid for pid in ids[: got.value // 4] if pid}


if sys.platform != "win32":  # pragma: no cover
    raise ImportError("windows only")
