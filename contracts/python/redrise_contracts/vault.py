"""OS vault for host secrets (P05-D3): Windows Credential Manager generic
credentials of the current user (DPAPI-protected). Secrets never go to
files, logs or the binary folder. `MemoryVault` is the test double."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import secrets
import sys

PREFIX = "RedRise/"
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2  # this user, this machine (not roamed)
ERROR_NOT_FOUND = 1168


class _CRED(ctypes.Structure):
    _fields_ = [("Flags", w.DWORD), ("Type", w.DWORD), ("TargetName", w.LPWSTR), ("Comment", w.LPWSTR),
                ("LastWritten", w.FILETIME), ("CredentialBlobSize", w.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", w.DWORD), ("AttributeCount", w.DWORD), ("Attributes", ctypes.c_void_p),
                ("TargetAlias", w.LPWSTR), ("UserName", w.LPWSTR)]


class VaultError(Exception):
    pass


class WindowsVault:
    def __init__(self, namespace: str = "host"):
        if sys.platform != "win32":  # pragma: no cover
            raise VaultError("windows only")
        self.ns = namespace
        self._adv = ctypes.WinDLL("advapi32", use_last_error=True)

    def _target(self, name: str) -> str:
        return f"{PREFIX}{self.ns}/{name}"

    def get(self, name: str) -> str | None:
        p = ctypes.POINTER(_CRED)()
        if not self._adv.CredReadW(self._target(name), CRED_TYPE_GENERIC, 0, ctypes.byref(p)):
            err = ctypes.get_last_error()
            if err == ERROR_NOT_FOUND:
                return None
            raise VaultError(f"CredReadW failed ({err})")
        try:
            c = p.contents
            return bytes(c.CredentialBlob[: c.CredentialBlobSize]).decode("utf-16-le")
        finally:
            self._adv.CredFree(p)

    def set(self, name: str, value: str) -> None:
        blob = value.encode("utf-16-le")
        buf = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        c = _CRED(Type=CRED_TYPE_GENERIC, TargetName=self._target(name), CredentialBlobSize=len(blob),
                  CredentialBlob=ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)), Persist=CRED_PERSIST_LOCAL_MACHINE,
                  UserName="redrise")
        if not self._adv.CredWriteW(ctypes.byref(c), 0):
            raise VaultError(f"CredWriteW failed ({ctypes.get_last_error()})")

    def delete(self, name: str) -> None:
        if not self._adv.CredDeleteW(self._target(name), CRED_TYPE_GENERIC, 0):
            err = ctypes.get_last_error()
            if err != ERROR_NOT_FOUND:
                raise VaultError(f"CredDeleteW failed ({err})")

    def ensure(self, name: str, nbytes: int = 24) -> str:
        v = self.get(name)
        if v is None:
            v = secrets.token_urlsafe(nbytes)
            self.set(name, v)
        return v


class MemoryVault(WindowsVault):
    """Test double (declared as simulated in evidence)."""

    def __init__(self, namespace: str = "test"):
        self.ns, self._d = namespace, {}

    def get(self, name):
        return self._d.get(name)

    def set(self, name, value):
        self._d[name] = value

    def delete(self, name):
        self._d.pop(name, None)
