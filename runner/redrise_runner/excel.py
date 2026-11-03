"""Excel capabilities (roadmap4 P01.1-P01.4), each testable on its own:

- `discover()`   -> Found(descriptor) | NotFound | DiscoveryFailed      [RR-EXCEL-DISC]
- `start(desc)`  -> consumes a validated descriptor given directly;
                   new Excel process, new blank workbook, readiness       [RR-EXCEL-START]
- `new_workbook()` composes them; absence/failure/contract errors become
  diagnostics (redrise_contracts.diagnostics)                             [RR-FLOW]

OS access goes through small injectable ports (registry, file version,
process launch, window probe, Engine key) so fixtures cover every branch
without uninstalling or launching Excel."""

from __future__ import annotations

import ctypes
import json
import re
import subprocess
import time
import winreg
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Callable, Protocol

from redrise_contracts import diagnostics as dg

DESCRIPTOR_SCHEMA = "redrise.excel-descriptor/1"
METHODS = ("app_paths", "click_to_run")
_VERSION = re.compile(r"^\d+(\.\d+){1,3}$")


# ---------------------------------------------------------------- descriptor contract

class DescriptorError(ValueError):
    pass


@dataclass(frozen=True)
class ExcelDescriptor:
    executable: str
    version: str
    method: str
    schema: str = DESCRIPTOR_SCHEMA

    def to_dict(self) -> dict:
        return {"schema": self.schema, "executable": self.executable, "version": self.version, "method": self.method}

    @staticmethod
    def parse(obj) -> "ExcelDescriptor":
        """Validates the locate -> start boundary. The executable is data
        naming EXCEL.EXE, never a command line."""
        if not isinstance(obj, dict):
            raise DescriptorError("descriptor is not an object")
        if obj.get("schema") != DESCRIPTOR_SCHEMA:
            raise DescriptorError(f"schema {obj.get('schema')!r}")
        extra = set(obj) - {"schema", "executable", "version", "method"}
        if extra:
            raise DescriptorError(f"unknown fields {sorted(extra)}")
        exe = obj.get("executable")
        if not isinstance(exe, str) or not PureWindowsPath(exe).is_absolute() or PureWindowsPath(exe).name.lower() != "excel.exe" \
                or any(c in exe for c in '"<>|*?\r\n'):
            raise DescriptorError("executable must be an absolute path to EXCEL.EXE")
        if not isinstance(obj.get("version"), str) or not _VERSION.match(obj["version"]):
            raise DescriptorError("version invalid")
        if obj.get("method") not in METHODS:
            raise DescriptorError("method invalid")
        return ExcelDescriptor(exe, obj["version"], obj["method"])


# ---------------------------------------------------------------- discovery

class Registry(Protocol):
    def value(self, hive: int, key: str, name: str | None) -> str | None:
        """None when the key/value does not exist; OSError for real failures."""


class WinRegistry:
    def value(self, hive, key, name):
        try:
            with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
                v, _ = winreg.QueryValueEx(k, name)
                return str(v)
        except FileNotFoundError:
            return None


def file_version(path: Path) -> str:
    v = ctypes.windll.version
    size = v.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        raise OSError(f"no version resource ({ctypes.GetLastError()})")
    buf = ctypes.create_string_buffer(size)
    if not v.GetFileVersionInfoW(str(path), 0, size, buf):
        raise OSError("GetFileVersionInfoW failed")
    ptr, n = ctypes.c_void_p(), ctypes.c_uint()
    if not v.VerQueryValueW(buf, "\\", ctypes.byref(ptr), ctypes.byref(n)):
        raise OSError("VerQueryValueW failed")
    ms, ls = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_uint32 * 13)).contents[2:4]
    return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"


_APP_PATHS = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\excel.exe"
_C2R = r"SOFTWARE\Microsoft\Office\ClickToRun"


def discover(reg: Registry | None = None, is_file: Callable[[Path], bool] = Path.is_file,
             version_of: Callable[[Path], str] = file_version) -> dict:
    """Returns {"status": "found", "descriptor": {...}} | {"status": "not_found"}
    | {"status": "failed", "reason": ...}. A failed query is never reported as
    not_found."""
    reg = reg or WinRegistry()
    candidates: list[tuple[str, Path]] = []
    try:
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            p = reg.value(hive, _APP_PATHS, None)
            if p:
                candidates.append(("app_paths", Path(p.strip().strip('"'))))
        root = reg.value(winreg.HKEY_LOCAL_MACHINE, _C2R, "InstallPath")
        if root:
            candidates.append(("click_to_run", Path(root) / "root" / "Office16" / "EXCEL.EXE"))
        for method, exe in candidates:
            if exe.name.lower() == "excel.exe" and is_file(exe):
                desc = ExcelDescriptor(str(exe), version_of(exe), method)
                ExcelDescriptor.parse(desc.to_dict())  # producer validates its own output
                return {"status": "found", "descriptor": desc.to_dict()}
    except (OSError, DescriptorError) as e:
        return {"status": "failed", "reason": f"{type(e).__name__}: {e}"}
    return {"status": "not_found", "checked": [m for m, _ in candidates] or ["app_paths", "click_to_run"]}


# ---------------------------------------------------------------- start

class WindowProbe(Protocol):
    def state(self, pid: int) -> str:
        """'none' | 'start_screen' | 'no_workbook' | 'workbook_ready'"""


class Win32ExcelWindows:
    """Classifies the XLMAIN window of one process by child window classes
    (locale independent): EXCEL7 = workbook window; FullpageUIHost = start screen."""

    def state(self, pid: int) -> str:
        u = ctypes.windll.user32
        proto = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        mains: list[int] = []

        def top(h, _):
            q = ctypes.c_uint32()
            u.GetWindowThreadProcessId(ctypes.c_void_p(h), ctypes.byref(q))
            if q.value == pid and u.IsWindowVisible(ctypes.c_void_p(h)) and _cls(h) == "XLMAIN":
                mains.append(h)
            return True

        u.EnumWindows(proto(top), None)
        if not mains:
            return "none"
        kids: set[str] = set()

        def child(h, _):
            kids.add(_cls(h))
            return True

        u.EnumChildWindows(ctypes.c_void_p(mains[0]), proto(child), None)
        if "EXCEL7" in kids:
            return "workbook_ready"
        return "start_screen" if "FullpageUIHost" in kids else "no_workbook"


def _cls(h) -> str:
    b = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetClassNameW(ctypes.c_void_p(h), b, 256)
    return b.value


def launch_new_process(exe: Path) -> int:
    # /x: a separate Excel process, so the user's open workbooks are not touched.
    p = subprocess.Popen([str(exe), "/x"], close_fds=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return p.pid


def start(descriptor, *, launcher: Callable[[Path], int] = launch_new_process, windows: WindowProbe | None = None,
          dismiss_start_screen: Callable[[], dict] | None = None, is_file: Callable[[Path], bool] = Path.is_file,
          timeout_s: float = 45.0, poll_s: float = 0.25, stable_s: float = 1.0,
          correlation_id: str | None = None) -> dict:
    """New blank workbook from a descriptor supplied directly (no discovery).
    Returns {"status": "ready", "pid", "observed"} or {"status": "error", "diagnostic"}."""
    cid = correlation_id or dg.new_correlation_id()
    try:
        desc = ExcelDescriptor.parse(descriptor)
    except DescriptorError as e:
        return _err(dg.make("CONTRACT-EXCEL-DESCRIPTOR", reported_by="RR-EXCEL-START", correlation_id=cid,
                            params={"reason": str(e)}, technical_details={"reason": str(e)},
                            boundary={"producer": "RR-EXCEL-DISC", "consumer": "RR-EXCEL-START", "contract": DESCRIPTOR_SCHEMA}))
    exe = Path(desc.executable)
    if not is_file(exe):
        return _err(dg.make("EXCEL-EXECUTABLE-MISSING", reported_by="RR-EXCEL-START", correlation_id=cid,
                            technical_details={"executable": desc.executable}))
    try:
        pid = launcher(exe)
    except OSError as e:
        return _err(dg.make("EXCEL-START-FAILED", reported_by="RR-EXCEL-START", correlation_id=cid,
                            params={"reason": type(e).__name__}, technical_details={"error": str(e)}))
    windows = windows or Win32ExcelWindows()
    deadline = time.monotonic() + timeout_s
    observed, since, dismissed = "none", None, False
    while time.monotonic() < deadline:
        cur = windows.state(pid)
        if cur != observed:
            observed, since = cur, time.monotonic()
        stable = since is not None and time.monotonic() - since >= stable_s
        if observed == "workbook_ready" and stable:
            return {"status": "ready", "pid": pid, "observed": observed, "correlation_id": cid,
                    "start_screen_dismissed": dismissed}
        if observed == "start_screen" and stable and not dismissed:
            dismissed = True
            if dismiss_start_screen is None:
                break
            r = dismiss_start_screen()
            if r.get("outcome") != "completed_unverified":
                return _err(dg.make("EXCEL-START-SCREEN-UNRESOLVED", reported_by="RR-EXCEL-START", correlation_id=cid,
                                    params={"engine_outcome": r.get("outcome"), "engine_code": r.get("code")},
                                    technical_details={"pid": pid, "engine": r}), pid)
        time.sleep(poll_s)
    return _err(dg.make("EXCEL-START-TIMEOUT", reported_by="RR-EXCEL-START", correlation_id=cid,
                        params={"observed": observed, "timeout_ms": int(timeout_s * 1000)},
                        technical_details={"pid": pid, "observed": observed}), pid)


def _err(d: dg.Diagnostic, pid: int | None = None) -> dict:
    out = {"status": "error", "diagnostic": d.to_dict(), "message": d.render()}
    if pid is not None:
        out["pid"] = pid
    return out


# ---------------------------------------------------------------- composition

def present_discovery(result: dict, correlation_id: str | None = None) -> dg.Diagnostic | None:
    """Discovery result -> diagnostic for absence/failure; None when found."""
    st = result.get("status") if isinstance(result, dict) else None
    if st == "found":
        return None
    if st == "not_found":
        return dg.make("EXCEL-NOT-FOUND", reported_by="RR-EXCEL-DISC", correlation_id=correlation_id,
                       technical_details={"checked": result.get("checked")})
    if st == "failed":
        return dg.make("EXCEL-DISCOVERY-FAILED", reported_by="RR-EXCEL-DISC", correlation_id=correlation_id,
                       params={"reason": result.get("reason", "?")}, technical_details={"reason": result.get("reason")})
    return dg.make("CONTRACT-EXCEL-DESCRIPTOR", reported_by="RR-FLOW", correlation_id=correlation_id,
                   params={"reason": f"discovery status {st!r}"},
                   boundary={"producer": "RR-EXCEL-DISC", "consumer": "RR-FLOW", "contract": "redrise.excel-discovery/1"})


def new_workbook(discover_fn: Callable[[], dict] = discover, start_fn: Callable[..., dict] = start,
                 correlation_id: str | None = None) -> dict:
    """Found -> start; NotFound/DiscoveryFailed -> diagnostic; invalid
    discovery contract -> CONTRACT-EXCEL-DESCRIPTOR at the boundary."""
    cid = correlation_id or dg.new_correlation_id()
    found = discover_fn()
    d = present_discovery(found, cid)
    if d is not None:
        return {"status": "error", "stage": "discover", "diagnostic": d.to_dict(), "message": d.render()}
    res = start_fn(found.get("descriptor"), correlation_id=cid)
    res["stage"] = "start"
    return res


def esc_procedure() -> dict:
    """Authored one-step IR: Esc on Excel's start screen opens a blank workbook."""
    return {
        "ir_version": 1, "category": "windows", "platform": "windows-x86_64",
        "source": {"recording_id": "authored:excel-start-screen", "events_sha256": "authored", "input_origin": "authored-template"},
        "target_process": "excel.exe", "params": [],
        "steps": [{"id": 0, "from_seq": [0, 0], "expect": {"process_image": "excel.exe", "class": "XLMAIN"},
                   "action": {"type": "key", "vk": 27}}],
    }


def engine_dismisser(engine, work_dir: Path) -> Callable[[], dict]:
    """Start-screen dismissal through the RedRise Engine (the Runner never injects input)."""
    import threading

    def run() -> dict:
        # A fresh directory per call: the Engine never overwrites an existing report.
        d = work_dir / f"{time.strftime('%Y%m%d-%H%M%S')}-{dg.new_correlation_id()[:6]}"
        d.mkdir(parents=True, exist_ok=False)
        proc = d / "excel-esc.procedure.json"
        proc.write_text(json.dumps(esc_procedure()), encoding="utf-8")
        r = engine.run(proc, d / "run.json", {}, threading.Event(), d / "stop.flag",
                       timeout_s=60, extra_args=["--step-timeout-ms", "15000", "--stable-ms", "800"])
        report = r.payload.get("report") or {}
        return {"outcome": r.outcome, "code": report.get("code") or r.payload.get("code") or f"exit {r.exit_code}",
                "engine_exit": r.exit_code}

    return run
