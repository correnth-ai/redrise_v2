"""Read-only Windows UI Automation (stdlib ctypes, no extra package).

Used to identify a browser tab after an opening request: the tab strip of a
top-level browser window (TabItem names, which one is selected), the address
shown in its toolbar Edit and the document of the selected tab (its URL and
title). It never sets focus, clicks, types or invokes patterns; it only reads
properties. The one write is `close_prompt`: WM_CLOSE (cancel) to a Windows
"Open with" dialog that the routine's own request raised."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
from dataclasses import dataclass

_ole32 = ctypes.windll.ole32
_oleaut32 = ctypes.windll.oleaut32
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

UIA_ControlTypePropertyId = 30003
UIA_NamePropertyId = 30005
UIA_ValueValuePropertyId = 30045
UIA_SelectionItemIsSelectedPropertyId = 30079
CT_EDIT, CT_TAB, CT_TABITEM, CT_DOCUMENT = 50004, 50018, 50019, 50030
TreeScope_Children, TreeScope_Descendants = 2, 4
VT_I4, VT_BSTR, VT_BOOL = 3, 8, 11


class GUID(ctypes.Structure):
    _fields_ = [("d1", wt.DWORD), ("d2", wt.WORD), ("d3", wt.WORD), ("d4", ctypes.c_ubyte * 8)]

    @staticmethod
    def parse(s: str) -> "GUID":
        g = GUID()
        _ole32.CLSIDFromString(ctypes.c_wchar_p("{" + s + "}"), ctypes.byref(g))
        return g


class _VU(ctypes.Union):
    _fields_ = [("lVal", ctypes.c_long), ("boolVal", ctypes.c_short), ("ptr", ctypes.c_void_p), ("pad", ctypes.c_byte * 16)]


class VARIANT(ctypes.Structure):
    _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort), ("r3", ctypes.c_ushort), ("u", _VU)]


CLSID_CUIAutomation = GUID.parse("ff48dba4-60ef-4201-aa87-54103eef594e")
IID_IUIAutomation = GUID.parse("30cbe57d-d9d0-452a-ab13-7ac5ac4825ee")
HRESULT = ctypes.c_long


def _method(ptr: ctypes.c_void_p, index: int, *argtypes):
    vtbl = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, *argtypes)(vtbl[index])


def _release(ptr) -> None:
    if ptr:
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(
            ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents[2])(ptr)


class UiaError(Exception):
    pass


@dataclass
class PageDoc:
    url: str | None
    title: str | None


@dataclass
class TabStrip:
    count: int
    selected: str | None
    names: list[str]


class Uia:
    """One IUIAutomation client for the calling thread (COM apartment)."""

    def __init__(self) -> None:
        _ole32.CoInitializeEx(None, 2)  # COINIT_APARTMENTTHREADED; S_FALSE if already initialized
        self._p = ctypes.c_void_p()
        hr = _ole32.CoCreateInstance(ctypes.byref(CLSID_CUIAutomation), None, 1, ctypes.byref(IID_IUIAutomation),
                                     ctypes.byref(self._p))
        if hr != 0 or not self._p:
            raise UiaError(f"CoCreateInstance CUIAutomation hr=0x{hr & 0xFFFFFFFF:08x}")

    def close(self) -> None:
        _release(self._p)
        self._p = ctypes.c_void_p()

    # -- IUIAutomation
    def _from_handle(self, hwnd: int) -> ctypes.c_void_p:
        el = ctypes.c_void_p()
        hr = _method(self._p, 6, wt.HWND, ctypes.POINTER(ctypes.c_void_p))(self._p, hwnd, ctypes.byref(el))
        if hr != 0 or not el:
            raise UiaError(f"ElementFromHandle hr=0x{hr & 0xFFFFFFFF:08x}")
        return el

    def _condition(self, prop: int, control_type: int) -> ctypes.c_void_p:
        v = VARIANT()
        v.vt, v.u.lVal = VT_I4, control_type
        cond = ctypes.c_void_p()
        hr = _method(self._p, 23, ctypes.c_int, VARIANT, ctypes.POINTER(ctypes.c_void_p))(self._p, prop, v, ctypes.byref(cond))
        if hr != 0 or not cond:
            raise UiaError(f"CreatePropertyCondition hr=0x{hr & 0xFFFFFFFF:08x}")
        return cond

    # -- IUIAutomationElement
    @staticmethod
    def _find_first(el, scope: int, cond) -> ctypes.c_void_p:
        out = ctypes.c_void_p()
        _method(el, 5, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(el, scope, cond, ctypes.byref(out))
        return out

    @staticmethod
    def _find_all(el, scope: int, cond) -> list[ctypes.c_void_p]:
        arr = ctypes.c_void_p()
        _method(el, 6, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(el, scope, cond, ctypes.byref(arr))
        if not arr:
            return []
        try:
            n = ctypes.c_int()
            _method(arr, 3, ctypes.POINTER(ctypes.c_int))(arr, ctypes.byref(n))
            items = []
            for i in range(n.value):
                e = ctypes.c_void_p()
                _method(arr, 4, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))(arr, i, ctypes.byref(e))
                items.append(e)
            return items
        finally:
            _release(arr)

    @staticmethod
    def _prop(el, prop: int):
        v = VARIANT()
        hr = _method(el, 10, ctypes.c_int, ctypes.POINTER(VARIANT))(el, prop, ctypes.byref(v))
        if hr != 0:
            return None
        try:
            if v.vt == VT_BSTR:
                return ctypes.wstring_at(v.u.ptr) if v.u.ptr else ""
            if v.vt == VT_BOOL:
                return v.u.boolVal != 0
            if v.vt == VT_I4:
                return v.u.lVal
            return None
        finally:
            _oleaut32.VariantClear(ctypes.byref(v))

    # -- public, read-only
    def tab_strip(self, hwnd: int) -> TabStrip | None:
        """Tabs of the first Tab control in tree order (the browser tab strip precedes page content)."""
        root = self._from_handle(hwnd)
        conds = []
        try:
            conds.append(self._condition(UIA_ControlTypePropertyId, CT_TAB))
            strip = self._find_first(root, TreeScope_Descendants, conds[-1])
            if not strip:
                return None
            try:
                conds.append(self._condition(UIA_ControlTypePropertyId, CT_TABITEM))
                tabs = self._find_all(strip, TreeScope_Descendants, conds[-1])
                names, selected = [], None
                for t in tabs:
                    try:
                        name = self._prop(t, UIA_NamePropertyId) or ""
                        names.append(name)
                        if self._prop(t, UIA_SelectionItemIsSelectedPropertyId):
                            selected = name
                    finally:
                        _release(t)
                return TabStrip(len(names), selected, names)
            finally:
                _release(strip)
        finally:
            for c in conds:
                _release(c)
            _release(root)

    def address(self, hwnd: int) -> str | None:
        """Value of the first Edit in tree order: the toolbar address field in Chromium/Firefox windows."""
        root = self._from_handle(hwnd)
        cond = self._condition(UIA_ControlTypePropertyId, CT_EDIT)
        try:
            edit = self._find_first(root, TreeScope_Descendants, cond)
            if not edit:
                return None
            try:
                v = self._prop(edit, UIA_ValueValuePropertyId)
                return v if isinstance(v, str) else None
            finally:
                _release(edit)
        finally:
            _release(cond)
            _release(root)


    def document(self, hwnd: int) -> PageDoc | None:
        """Root document of the selected tab: the first Document in tree order (Chromium exposes only the
        active tab's; its Value is the committed URL, chrome-error://chromewebdata/ for a load error)."""
        root = self._from_handle(hwnd)
        cond = self._condition(UIA_ControlTypePropertyId, CT_DOCUMENT)
        try:
            doc = self._find_first(root, TreeScope_Descendants, cond)
            if not doc:
                return None
            try:
                url, title = self._prop(doc, UIA_ValueValuePropertyId), self._prop(doc, UIA_NamePropertyId)
                return PageDoc(url if isinstance(url, str) else None, title if isinstance(title, str) else None)
            finally:
                _release(doc)
        finally:
            _release(cond)
            _release(root)


# ---------------------------------------------------------------- top-level windows (read-only)
_WNDENUM = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def _image_of(pid: int) -> str | None:
    h = _kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        n = wt.DWORD(1024)
        if _kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return buf.value
        return None
    finally:
        _kernel32.CloseHandle(h)


def prompt_windows() -> list[int]:
    """Visible top-level windows of the Windows "Open with" dialog (OpenWith.exe)."""
    out: list[int] = []

    def cb(hwnd, _):
        if _user32.IsWindowVisible(hwnd):
            pid = wt.DWORD()
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            path = _image_of(pid.value)
            if path and path.rsplit("\\", 1)[-1].lower() == "openwith.exe":
                out.append(int(hwnd))
        return True

    _user32.EnumWindows(_WNDENUM(cb), 0)
    return out


def close_prompt(hwnd: int) -> None:
    _user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE: the dialog's cancel; no app is chosen, nothing is associated


def browser_windows(images: set[str]) -> list[dict]:
    """Visible, unowned top-level windows whose process image is in `images`."""
    out: list[dict] = []

    def cb(hwnd, _):
        if not _user32.IsWindowVisible(hwnd) or _user32.GetWindow(hwnd, 4):  # GW_OWNER
            return True
        pid = wt.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        path = _image_of(pid.value)
        if not path or path.rsplit("\\", 1)[-1].lower() not in images:
            return True
        cls = ctypes.create_unicode_buffer(256)
        _user32.GetClassNameW(hwnd, cls, 256)
        if cls.value not in ("Chrome_WidgetWin_1", "MozillaWindowClass"):
            return True
        title = ctypes.create_unicode_buffer(512)
        _user32.GetWindowTextW(hwnd, title, 512)
        if not title.value:
            return True
        out.append({"hwnd": int(hwnd), "pid": pid.value, "exe": path, "image": path.rsplit("\\", 1)[-1].lower(),
                    "class": cls.value, "title": title.value})
        return True

    _user32.EnumWindows(_WNDENUM(cb), 0)
    return out
