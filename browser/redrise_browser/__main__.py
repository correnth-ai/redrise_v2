"""`python -m redrise_browser record|serve` (spawned by redrise-engine.exe).

record --url U --profile DIR [--browsers DIR]
    stdout: one JSON event per line ({"type": "ready"|"browser_goto"|"browser_click"|
    "browser_fill"|"browser_press"|"unsupported"|"pong"|"stopped"|"error", ...})
    stdin:  "stop" | "ping"
serve --profile DIR [--browsers DIR]
    stdin:  one JSON command per line; stdout: one JSON response per line.
    {"cmd": "goto"|"click"|"fill"|"press"|"state"|"close", ...}
    Errors carry "delivery": "not_attempted" | "partial".
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import sys
import threading
from pathlib import Path


def default_browsers() -> Path:
    # <install>/runtime/python/python.exe -> <install>/browsers
    return Path(sys.executable).resolve().parent.parent.parent / "browsers"


def out(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


class StdinPoller:
    """Non-blocking control lines from a stdin pipe (Windows PeekNamedPipe).

    A thread blocked in a synchronous ReadFile on stdin stalled Playwright's
    event dispatch in the record loop (observed 2026-10-27), so control is
    polled from the main loop instead."""

    def __init__(self) -> None:
        import msvcrt

        self._fd = sys.stdin.fileno()
        self._handle = msvcrt.get_osfhandle(self._fd)
        self._buf = b""
        self.eof = False

    def lines(self) -> list[str]:
        import _winapi

        try:
            avail = _winapi.PeekNamedPipe(self._handle, 0)[0]
        except OSError:
            self.eof = True
            return []
        if avail:
            self._buf += os.read(self._fd, avail)
        *done, self._buf = self._buf.split(b"\n")
        return [d.decode("utf-8", "replace").strip() for d in done]


def launch(p, profile: Path):
    ctx = p.chromium.launch_persistent_context(
        str(profile), headless=False, accept_downloads=False, no_viewport=True, args=["--no-first-run", "--disable-sync"]
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return ctx, page


def cmd_record(a) -> int:
    from playwright.sync_api import sync_playwright

    recorder = (Path(__file__).with_name("recorder.js")).read_text(encoding="utf-8")
    events: "queue.Queue[dict]" = queue.Queue()
    with sync_playwright() as p:
        ctx, page = launch(p, a.profile)
        ctx.expose_binding("__rrEmit", lambda source, ev: events.put(ev))
        ctx.add_init_script(recorder)
        page.goto(a.url)
        page.wait_for_load_state("load")
        # "ready" only once the start page is loaded and the recorder is
        # installed: input given earlier would be lost.
        out({"type": "ready", "browser_executable": p.chromium.executable_path})
        out({"type": "browser_goto", "url": a.url, "title": page.title()})
        control = StdinPoller()
        closed = threading.Event()
        ctx.on("close", lambda _: closed.set())
        stop = False
        while not closed.is_set() and not stop:
            try:
                while True:
                    out(events.get_nowait())
            except queue.Empty:
                pass
            for msg in control.lines():
                if msg == "stop":
                    stop = True
                elif msg == "ping":
                    out({"type": "pong"})
            if control.eof:
                break
            page.wait_for_timeout(50)  # services Playwright's event loop (bindings)
        try:
            while True:
                out(events.get_nowait())
        except queue.Empty:
            pass
        # End the event stream before closing Chromium (which can take
        # seconds), so the Engine can seal within its finalize deadline.
        out({"type": "stopped"})
        if not closed.is_set():
            ctx.close()
    return 0


def cmd_serve(a) -> int:
    from playwright.sync_api import Error as PwError
    from playwright.sync_api import TimeoutError as PwTimeout
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx, page = launch(p, a.profile)
        out({"ok": True, "ready": True, "browser_executable": p.chromium.executable_path})
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                c = json.loads(line)
            except ValueError:
                out({"ok": False, "code": "bad_command", "delivery": "not_attempted"})
                continue
            kind = c.get("cmd")
            timeout = int(c.get("timeout_ms", 10000))
            try:
                if kind == "state":
                    out({"ok": True, "url": page.url, "title": page.title()})
                elif kind == "goto":
                    page.goto(c["url"], timeout=timeout)
                    out({"ok": True, "url": page.url})
                elif kind in ("click", "fill", "press"):
                    loc = page.locator(c["selector"])
                    n = loc.count()
                    if n != 1:
                        out({"ok": False, "code": "selector_not_found" if n == 0 else "selector_ambiguous",
                             "matches": n, "delivery": "not_attempted"})
                        continue
                    if kind == "click":
                        loc.click(timeout=timeout)
                    elif kind == "fill":
                        loc.fill(c["value"], timeout=timeout)
                    else:
                        loc.press(c["key"], timeout=timeout)
                    out({"ok": True, "url": page.url})
                elif kind == "close":
                    out({"ok": True})
                    break
                else:
                    out({"ok": False, "code": "unknown_command", "delivery": "not_attempted"})
            except PwTimeout as e:
                # A timeout during goto/click/fill/press can occur after the input
                # was dispatched (e.g. waiting for navigation), so delivery is not
                # known: report partial (-> uncertain, no blind retry).
                out({"ok": False, "code": "timeout", "detail": str(e).splitlines()[0],
                     "delivery": "not_attempted" if kind == "state" else "partial"})
            except PwError as e:
                out({"ok": False, "code": "browser_error", "detail": str(e).splitlines()[0], "delivery": "partial"})
        try:
            ctx.close()
        except PwError:
            pass
    return 0


def cmd_open(a) -> int:
    """Opens the RedRise browser profile for the user to act by hand (e.g. sign
    in to Gmail). RedRise records nothing and types nothing; returns when the
    user closes the window."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx, page = launch(p, a.profile)
        page.goto(a.url)
        out({"type": "opened", "url": a.url})
        closed = threading.Event()
        ctx.on("close", lambda _: closed.set())
        while not closed.is_set() and ctx.pages:
            try:
                ctx.pages[0].wait_for_timeout(500)  # services Playwright's event loop
            except Exception:  # noqa: BLE001 - the user closed the window
                break
        try:
            ctx.close()
        except Exception:  # noqa: BLE001 - already closed by the user
            pass
    out({"type": "closed"})
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="redrise_browser")
    ap.add_argument("--browsers", type=Path, default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("open", help="manual use of the RedRise browser profile (sign-in)")
    o.add_argument("--url", required=True)
    o.add_argument("--profile", type=Path, required=True)
    r = sub.add_parser("record")
    r.add_argument("--url", required=True)
    r.add_argument("--profile", type=Path, required=True)
    s = sub.add_parser("serve")
    s.add_argument("--profile", type=Path, required=True)
    a = ap.parse_args(argv)
    # Force the packaged browsers; never the global ms-playwright cache.
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str((a.browsers or default_browsers()).resolve())
    os.environ["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"
    try:
        if a.cmd == "open":
            return cmd_open(a)
        return cmd_record(a) if a.cmd == "record" else cmd_serve(a)
    except Exception as e:  # report, never hang the Engine
        out({"type": "error", "ok": False, "code": "adapter_failed", "detail": f"{type(e).__name__}: {e}".splitlines()[0]})
        return 1


if __name__ == "__main__":
    sys.exit(main())
