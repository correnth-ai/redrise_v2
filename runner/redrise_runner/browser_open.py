"""Browser opening routine (update Browser, B01-B06/G13/G14/G18/G33).

site: the chosen browser on this station opens the address in a new tab
      (the browser is never substituted by another one);
html: the file is opened by the Windows opening mechanism (its association),
      and the browser/tab where it actually opened is identified afterwards.
      When that mechanism raises the "Open with" dialog instead of a browser,
      the dialog is cancelled and the file opens in Microsoft Edge (decision
      of 01/11/2026); the association is never changed.

Confirmation (<= 30 s in total, earlier if confirmed), in two levels:
1. tab open: a browser window of the expected image that is new or gained a
   tab after the request, whose selected tab shows the target address;
2. page ready: the document of that tab is committed at the target (not the
   previous page, not a browser error page such as chrome-error://).
Only level 2 is `verified`. Level 1 alone is `failed` browser_page_not_ready
(a tab exists); nothing at all is `failed` with an unknown effect. No retry,
no kill, no repair, and the tab stays open at the end (G28). Identification
is read-only UI Automation; nothing is typed or clicked."""

from __future__ import annotations

import os
import subprocess
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from . import browsers

TIMEOUT_S = 30.0
POLL_S = 0.25
HTML_DEFAULT_BROWSER = "msedge"  # used only when the .html association raises "Open with"
ERROR_SCHEMES = ("chrome-error:", "edge-error:", "about:neterror", "about:certerror")


class Probe(Protocol):
    def windows(self, images: set[str]) -> list[dict]: ...
    def strip(self, hwnd: int): ...  # -> uia.TabStrip | None
    def address(self, hwnd: int) -> str | None: ...
    def document(self, hwnd: int): ...  # -> uia.PageDoc | None
    def prompts(self) -> list[int]: ...
    def close_prompt(self, hwnd: int) -> None: ...


class UiaProbe:
    def __init__(self) -> None:
        from . import uia
        self._uia = uia
        self._client = uia.Uia()

    def windows(self, images: set[str]) -> list[dict]:
        return self._uia.browser_windows(images)

    def strip(self, hwnd: int):
        try:
            return self._client.tab_strip(hwnd)
        except self._uia.UiaError:
            return None

    def address(self, hwnd: int) -> str | None:
        try:
            return self._client.address(hwnd)
        except self._uia.UiaError:
            return None

    def document(self, hwnd: int):
        try:
            return self._client.document(hwnd)
        except self._uia.UiaError:
            return None

    def prompts(self) -> list[int]:
        return self._uia.prompt_windows()

    def close_prompt(self, hwnd: int) -> None:
        self._uia.close_prompt(hwnd)

    def close(self) -> None:
        self._client.close()


def _detached(args: list[str]) -> None:
    # The launcher may hand the request to a running browser and exit at once:
    # its PID is never taken as proof of anything.
    subprocess.Popen(args, close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=0x00000008 | 0x00000200)  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def launch_site(browser: dict, url: str) -> None:
    args = [browser["path"], "-new-tab", url] if browser["id"] == "firefox" else [browser["path"], url]
    _detached(args)


def launch_html(path: str) -> None:
    os.startfile(path)  # ShellExecute "open": the file's association decides the browser


def launch_file_in(browser: dict, path: str) -> None:
    _detached([browser["path"], path])


# ---------------------------------------------------------------- address matching
def _norm_site(addr: str) -> tuple[str, str]:
    a = addr.strip()
    if "://" not in a:
        a = "https://" + a  # Chromium elides the scheme in the address field
    u = urllib.parse.urlsplit(a)
    host = (u.hostname or "").lower().removeprefix("www.")
    return host, (u.path or "/").rstrip("/")


def site_matches(observed: str | None, target: str) -> bool:
    """Same host (ignoring www.) as the registered address; the path may differ (redirects inside the site)."""
    if not observed:
        return False
    return _norm_site(observed)[0] == _norm_site(target)[0] != ""


def _norm_path(p: str) -> str:
    s = urllib.parse.unquote(p.strip())
    for prefix in ("file:///", "file://"):
        if s.lower().startswith(prefix):
            s = s[len(prefix):]
            break
    return os.path.normcase(os.path.normpath(s.replace("/", "\\")))


def html_matches(observed: str | None, path: str) -> bool:
    return bool(observed) and _norm_path(observed) == _norm_path(path)


def is_error_page(url: str | None) -> bool:
    return bool(url) and url.strip().lower().startswith(ERROR_SCHEMES)


# ---------------------------------------------------------------- run
@dataclass
class Snapshot:
    tabs: dict[int, int] = field(default_factory=dict)  # hwnd -> tab count before the request


def _snapshot(probe: Probe, images: set[str]) -> Snapshot:
    snap = Snapshot()
    for w in probe.windows(images):
        s = probe.strip(w["hwnd"])
        snap.tabs[w["hwnd"]] = s.count if s else -1
    return snap


PROMPT = "prompt"


def confirm(probe: Probe, images: set[str], before: Snapshot, matches: Callable[[str | None], bool],
            deadline: float, clock=time.monotonic, sleep=time.sleep,
            interrupt: Callable[[], bool] | None = None) -> dict | str | None:
    """Level 1: reference of the new tab showing the target, PROMPT when `interrupt` fires first,
    or None when not confirmed in time."""
    while True:
        if interrupt is not None and interrupt():
            return PROMPT
        for w in probe.windows(images):
            s = probe.strip(w["hwnd"])
            prior = before.tabs.get(w["hwnd"])
            gained = prior is None or (s is not None and prior >= 0 and s.count > prior)
            if not gained:
                continue  # an existing window without a new tab: never a personal tab by coincidence
            addr = probe.address(w["hwnd"])
            if matches(addr):
                return {"hwnd": w["hwnd"], "pid": w["pid"], "image": w["image"], "exe": w["exe"],
                        "new_window": prior is None, "tab_title": s.selected if s else None, "address": addr,
                        "tab_count": s.count if s else None}
        if clock() >= deadline:
            return None
        sleep(POLL_S)


def wait_ready(probe: Probe, hwnd: int, matches: Callable[[str | None], bool], deadline: float,
               clock=time.monotonic, sleep=time.sleep) -> tuple[bool, object]:
    """Level 2: the selected tab's document is committed at the target and is not an error page.
    Right after the tab appears the document can still be the previous page, so it must match the target.
    Returns (ready, last document seen)."""
    while True:
        doc = probe.document(hwnd)
        url = getattr(doc, "url", None)
        if url and not is_error_page(url) and matches(url):
            return True, doc
        if clock() >= deadline:
            return False, doc
        sleep(POLL_S)


def run(config: dict, probe_factory: Callable[[], Probe] = UiaProbe, resolve=browsers.resolve,
        open_site=launch_site, open_html=launch_html, open_file_in=launch_file_in, timeout_s: float = TIMEOUT_S,
        clock=time.monotonic, sleep=time.sleep) -> dict:
    """Local result: state verified | failed | refused | error, code, detail, context (when a tab was identified)."""
    origin = config.get("origin")
    started = time.time()
    if origin == "site":
        browser = resolve(config.get("browser") or "")
        if browser is None:
            return {"state": "refused", "code": "browser_not_found", "detail": config.get("browser")}
        images = {browsers.CANDIDATES[browser["id"]]["image"]}
        target = config["url"]
        matches = lambda a: site_matches(a, target)  # noqa: E731
    elif origin == "html":
        path = config.get("path") or ""
        if not Path(path).is_file():
            return {"state": "refused", "code": "input_missing", "detail": path}
        images = set(browsers.HTML_IMAGES)
        target = path
        matches = lambda a: html_matches(a, path)  # noqa: E731
        browser = None
    else:
        return {"state": "refused", "code": "invalid_job", "detail": f"origin {origin!r}"}
    try:
        probe = probe_factory()
    except Exception as e:  # noqa: BLE001 - without UI Automation the tab cannot be identified: do not open blindly
        return {"state": "refused", "code": "browser_uia_unavailable", "detail": f"{type(e).__name__}: {e}"[:200]}
    opened_by = "chosen_browser" if origin == "site" else "association"
    deadline = clock() + timeout_s
    try:
        before = _snapshot(probe, images)
        prompts_before = set(probe.prompts()) if origin == "html" else set()
        try:
            open_site(browser, target) if origin == "site" else open_html(target)
        except OSError as e:
            return {"state": "failed", "code": "browser_open_failed", "detail": f"{type(e).__name__}: {e}"[:200]}

        def new_prompts() -> list[int]:
            return [h for h in probe.prompts() if h not in prompts_before]

        ref = confirm(probe, images, before, matches, deadline, clock, sleep,
                      interrupt=(lambda: bool(new_prompts())) if origin == "html" else None)
        if ref == PROMPT:
            # Our own request raised "Open with": cancel it (no app chosen, association untouched), open in Edge.
            for h in new_prompts():
                probe.close_prompt(h)
            browser = resolve(HTML_DEFAULT_BROWSER)
            if browser is None:
                return {"state": "refused", "code": "browser_not_found",
                        "detail": f"no working .html association and {HTML_DEFAULT_BROWSER} not found"}
            images = {browsers.CANDIDATES[browser["id"]]["image"]}
            before = _snapshot(probe, images)
            opened_by = "default_browser_after_prompt"
            try:
                open_file_in(browser, target)
            except OSError as e:
                return {"state": "failed", "code": "browser_open_failed", "detail": f"{type(e).__name__}: {e}"[:200]}
            ref = confirm(probe, images, before, matches, deadline, clock, sleep)
        ready, doc = (False, None) if ref is None else wait_ready(probe, ref["hwnd"], matches, deadline, clock, sleep)
        if ready:  # the tab name read at level 1 can be the pre-load one ("Untitled")
            final = probe.strip(ref["hwnd"])
            ref["tab_title"] = (final.selected if final else None) or getattr(doc, "title", None) or ref["tab_title"]
    finally:
        getattr(probe, "close", lambda: None)()
    elapsed_ms = int((time.time() - started) * 1000)
    if ref is None:
        return {"state": "failed", "code": "browser_open_unconfirmed", "elapsed_ms": elapsed_ms,
                "detail": f"no new tab showing the target within {int(timeout_s)} s"}
    bid = browser["id"] if browser else browsers.classify(ref["exe"])
    page_url = getattr(doc, "url", None)
    context = {"origin": origin, "browser_id": bid, "browser_name": browsers.display_name(bid),
               "opened_by": opened_by, "confirmation": "page_ready" if ready else "tab_open",
               "image": ref["image"], "pid": ref["pid"], "hwnd": ref["hwnd"], "new_window": ref["new_window"],
               "tab_title": ref["tab_title"], "address": ref["address"], "page_url": page_url,
               "page_title": getattr(doc, "title", None), "target": target, "confirmed_ms": elapsed_ms}
    if not ready:
        why = "browser error page" if is_error_page(page_url) else "document not at the target"
        return {"state": "failed", "code": "browser_page_not_ready", "context": context, "elapsed_ms": elapsed_ms,
                "detail": f"tab open at the target, page not ready within {int(timeout_s)} s ({why})"}
    return {"state": "verified", "verified": True, "code": None, "context": context, "elapsed_ms": elapsed_ms}
