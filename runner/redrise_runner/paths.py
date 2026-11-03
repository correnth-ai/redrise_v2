"""Install and data locations.

Binaries live in the install root (``%LOCALAPPDATA%\\Programs\\@redrise`` when
installed); mutable state lives under ``%LOCALAPPDATA%\\RedRise``. The real
LocalAppData is resolved through the Shell known-folder API, not from the
process environment.
"""

from __future__ import annotations

import ctypes
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

ENGINE_EXE = "redrise-engine.exe"


class _GUID(ctypes.Structure):
    _fields_ = [("d1", ctypes.c_uint32), ("d2", ctypes.c_uint16), ("d3", ctypes.c_uint16), ("d4", ctypes.c_ubyte * 8)]


def _guid(s: str) -> _GUID:
    u = uuid.UUID(s)
    g = _GUID()
    g.d1, g.d2, g.d3 = u.fields[0], u.fields[1], u.fields[2]
    g.d4[:] = list(u.bytes[8:])
    return g


FOLDERID_LOCAL_APP_DATA = "F1B32785-6FBA-4FCF-9D55-7B8E7F157091"


def local_app_data() -> Path:
    """Real per-user LocalAppData via SHGetKnownFolderPath."""
    if sys.platform != "win32":
        raise OSError("windows only")
    path_ptr = ctypes.c_wchar_p()
    guid = _guid(FOLDERID_LOCAL_APP_DATA)
    hr = ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(path_ptr))
    try:
        if hr != 0:
            raise OSError(f"SHGetKnownFolderPath failed: 0x{hr & 0xFFFFFFFF:08X}")
        return Path(path_ptr.value)
    finally:
        ctypes.windll.ole32.CoTaskMemFree(path_ptr)


@dataclass(frozen=True)
class Layout:
    install_root: Path
    runtime_dir: Path
    engine: Path
    data_root: Path

    @property
    def jobs_dir(self) -> Path:
        return self.data_root / "jobs"

    @property
    def locks_dir(self) -> Path:
        return self.data_root / "locks"

    @property
    def logs_dir(self) -> Path:
        return self.data_root / "logs"


def default_install_root() -> Path:
    """`<install>/runtime/python/python.exe` -> `<install>`."""
    return Path(sys.executable).resolve().parent.parent.parent


def resolve(install_root: Path | None = None, data_root: Path | None = None, engine: Path | None = None) -> Layout:
    root = (install_root or default_install_root()).resolve()
    data = data_root if data_root is not None else local_app_data() / "RedRise"
    return Layout(
        install_root=root,
        runtime_dir=root / "runtime" / "python",
        engine=(engine or root / "engine" / ENGINE_EXE),
        data_root=Path(data).resolve(),
    )
