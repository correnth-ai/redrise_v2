"""Boas-vindas process: three routines on the Windows Notepad, in one execution.

open:  identify the window and tabs. The only empty untitled tab of a clean
       start is reused; an app already open or a restored session gets a tab
       dedicated to the run, and the existing tabs are kept.
save:  confirm focus on that tab, type the text and save through the Save As
       dialog on the user's Desktop, under the first free name. An existing
       file is never overwritten.
close: a shared window loses only the tab of the run. In a window dedicated
       to the run, extra tabs identified as the run's (empty and untitled, or
       showing exactly the text of the run) are closed, discarding only those;
       the window ends when the last tab closes. Any other tab, such as one a
       person opened meanwhile, is kept and the window stays open.

Every action reaches the visible UI as keyboard events sent by the Engine,
bound to the window of the run. A tab is identified by its UI Automation
runtime id, never by its title, and is checked again before typing, saving or
closing: a lost target stops the step without acting. The result file is read
back independently. Nothing is repeated automatically after a failure or an
uncertain effect."""

from __future__ import annotations

import ctypes
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from . import apps, verifiers
from .jobs import JobSpec, run_job
from .paths import Layout

TEXT = "Boas-vindas a Redrise Automa\xe7\xf5es B2B"
STEM, SUFFIX = "Boas_Vindas", ".txt"
IMAGE, MAIN_CLASS, DIALOG_CLASS = "notepad.exe", "Notepad", "#32770"
# Names Notepad gives an untitled tab and the discard button, in the languages exercised.
UNTITLED = ("Sem t\xedtulo", "Untitled")
DISCARD = ("N\xe3o salvar", "Don't save")
REFUSE = ("N\xe3o", "No")  # the answer to "replace the file?"
VK_TAB, VK_RETURN, VK_ESCAPE, VK_F24 = 9, 13, 27, 0x87
VK_A, VK_D, VK_N, VK_S, VK_T, VK_W = 65, 68, 78, 83, 84, 87
MAX_NAME_TRIES = 3
SAVE_TIMEOUT_S = 15.0
CLOSE_TIMEOUT_S = 10.0
POLL_S = 0.25


class Desk(Protocol):
    """What the steps read from and do to the desktop, besides Engine input."""
    def windows(self) -> list[int]: ...
    def foreground(self) -> int: ...
    def is_window(self, hwnd: int) -> bool: ...
    def launch(self) -> int | None: ...
    def tabs(self, hwnd: int) -> list: ...  # uia.TabRef
    def text(self, hwnd: int) -> str | None: ...
    def buttons(self, hwnd: int) -> list[str]: ...
    def focused(self) -> str | None: ...
    def dialogs(self) -> int: ...
    def desktop(self) -> Path: ...


class UiaDesk:
    def __init__(self) -> None:
        from . import uia
        self._uia = uia
        self._client = uia.Uia()

    def windows(self) -> list[int]:
        return [w["hwnd"] for w in verifiers.top_windows() if w["process_image"] == IMAGE and w["class"] == MAIN_CLASS]

    def foreground(self) -> int:
        return apps.foreground_window()

    def is_window(self, hwnd: int) -> bool:
        return bool(ctypes.windll.user32.IsWindow(hwnd))

    def launch(self) -> int | None:
        exe, _ = apps.resolve("notepad")
        if exe is None:
            return None
        apps.launch(exe, [])
        return apps.launched_window(IMAGE, MAIN_CLASS, set(), apps.foreground_window, verifiers.top_windows)

    def tabs(self, hwnd: int) -> list:
        try:
            return self._client.tabs(hwnd)
        except self._uia.UiaError:  # the window closed while it was being read
            return []

    def text(self, hwnd: int) -> str | None:
        try:
            return self._client.document_text(hwnd)
        except self._uia.UiaError:
            return None

    def buttons(self, hwnd: int) -> list[str]:
        try:
            return self._client.buttons(hwnd)
        except self._uia.UiaError:
            return []

    def focused(self) -> str | None:
        return self._client.focused_name()

    def dialogs(self) -> int:
        return sum(1 for w in verifiers.top_windows() if w["process_image"] == IMAGE and w["class"] == DIALOG_CLASS)

    def desktop(self) -> Path:
        return apps.desktop()

    def close(self) -> None:
        self._client.close()


def key(vk: int, *mods: str, on: str = MAIN_CLASS, effectful: bool = False) -> dict:
    return {"expect": on, "effectful": effectful, "action": {"type": "key", "vk": vk, "mods": {m: True for m in mods}}}


def typed(text: str, on: str = MAIN_CLASS) -> dict:
    return {"expect": on, "effectful": False, "action": {"type": "type_text", "text": {"literal": text}}}


def procedure(actions: list[dict]) -> dict:
    return {"ir_version": 1, "category": "windows", "platform": "windows-x86_64",
            "source": {"recording_id": "authored:boas-vindas-process", "events_sha256": "authored",
                       "input_origin": "authored-template"},
            "target_process": IMAGE, "params": [],
            "steps": [{"id": i, "from_seq": [0, 0], "expect": {"process_image": IMAGE, "class": a["expect"]},
                       "action": a["action"], **({"effectful": True} if a["effectful"] else {})}
                      for i, a in enumerate(actions)]}


Send = Callable[[int, list[dict]], dict]


def engine_sender(job_id: str, layout: Layout, engine, cancel) -> Send:
    """Each batch of keystrokes is a job of the Engine, bound to the window of the run."""
    work = layout.data_root / "agent" / "procedures"
    count = [0]

    def send(hwnd: int, actions: list[dict]) -> dict:
        count[0] += 1
        sub = f"{job_id}-{count[0]}"
        work.mkdir(parents=True, exist_ok=True)
        path = work / f"{sub}.json"
        path.write_text(json.dumps(procedure(actions), ensure_ascii=False), encoding="utf-8")
        args = ["--step-timeout-ms", "20000", "--settle-ms", "900", "--char-delay-ms", "80", "--stable-ms", "1500",
                "--bound-window", str(hwnd)]
        return run_job(JobSpec(sub, path), layout, engine, cancel, engine_args=args, session_lock_held=True)
    return send


def free_name(folder: Path) -> str:
    """First free name: Boas_Vindas.txt, then Boas_Vindas[2].txt, Boas_Vindas[3].txt and so on."""
    if not (folder / f"{STEM}{SUFFIX}").exists():
        return f"{STEM}{SUFFIX}"
    n = 2
    while (folder / f"{STEM}[{n}]{SUFFIX}").exists():
        n += 1
    return f"{STEM}[{n}]{SUFFIX}"


@dataclass
class _Stop(Exception):
    state: str
    code: str
    detail: str


def _title_of(tab) -> str:
    return tab.name.split(". ")[0]


def _is_clean_start(tabs: list, text: str | None) -> bool:
    return len(tabs) == 1 and _title_of(tabs[0]) in UNTITLED and text == ""


def _engine_ok(job: dict, doing: str, after_effect: bool = False) -> None:
    """Engine outcomes other than a completed run stop the step with their own state and code."""
    state = job.get("state")
    if state != "completed_unverified":
        raise _Stop("uncertain" if after_effect and state == "failed" else state or "error",
                    job.get("code") or "notepad_engine_stopped", f"{doing}: {job.get('detail') or job.get('code')}")


def _bring_forward(desk: Desk, send: Send, hwnd: int) -> bool:
    """Windows refuses the foreground to a background process, and an app in front keeps it. The Engine
    gets it (its injected input counts as the last input) and activates the bound window before its
    first step, so a key that nothing binds is enough."""
    if desk.foreground() != hwnd:
        send(hwnd, [key(VK_F24)])
    return desk.foreground() == hwnd


def _target(desk: Desk, send: Send, ctx: dict) -> dict:
    """The window and tab this execution identified, confirmed in the foreground, or a stop before any input."""
    ref = (ctx.get("notepad") or {}) if isinstance(ctx, dict) else {}
    hwnd, tab = ref.get("window"), ref.get("tab_id")
    if not isinstance(hwnd, int) or not isinstance(tab, str):
        raise _Stop("refused", "notepad_context_missing", "the previous step left no window and tab reference")
    if not desk.is_window(hwnd):
        raise _Stop("failed", "notepad_target_lost", "the window of this run is no longer open")
    if not _bring_forward(desk, send, hwnd):
        raise _Stop("failed", "notepad_target_lost", "the window of this run could not be brought to the foreground")
    if not any(t.tab_id == tab for t in desk.tabs(hwnd)):
        raise _Stop("failed", "notepad_target_lost", "the tab of this run is no longer in the window")
    return ref


def _focused_on(desk: Desk, ref: dict) -> None:
    hwnd, tab = ref["window"], ref["tab_id"]
    if desk.foreground() != hwnd:
        raise _Stop("failed", "notepad_target_lost", "the window of this run lost the foreground")
    if not any(t.tab_id == tab and t.selected for t in desk.tabs(hwnd)):
        raise _Stop("failed", "notepad_target_lost", "another tab is selected")


def open_step(desk: Desk, send: Send, ctx: dict) -> dict:
    existing = desk.windows()
    if existing:
        fg = desk.foreground()
        hwnd = fg if fg in existing else existing[0]
        if not _bring_forward(desk, send, hwnd):
            raise _Stop("failed", "notepad_target_lost", "the open window could not be brought to the foreground")
        mode, owned = "already_open", False
    else:
        hwnd = desk.launch()
        if hwnd is None:
            raise _Stop("failed", "notepad_window_not_found", "no Notepad window appeared after opening it")
        owned = True
        mode = "clean"
    tabs = desk.tabs(hwnd)
    if not tabs:
        raise _Stop("refused", "notepad_tabs_unavailable", "this Notepad shows no tabs; version without tabs is not supported")
    if owned and _is_clean_start(tabs, desk.text(hwnd)):
        tab = tabs[0].tab_id
        before: list[str] = []
    else:
        if owned:  # opened by this run, but it brought back the tabs of an earlier session
            mode, owned = "restored_session", False
        before = [t.tab_id for t in tabs]
        _engine_ok(send(hwnd, [key(VK_T, "ctrl")]), "new tab")
        tab = _new_tab(desk, hwnd, before)
    return {"notepad": {"window": hwnd, "tab_id": tab, "mode": mode, "window_of_run": owned, "tabs_before": before,
                        "tabs_seen": len(before) + 1}}


def _new_tab(desk: Desk, hwnd: int, before: list[str], timeout_s: float = 5.0) -> str:
    deadline = time.monotonic() + timeout_s
    while True:
        new = [t for t in desk.tabs(hwnd) if t.tab_id not in before]
        if len(new) == 1 and new[0].selected and desk.text(hwnd) == "":
            return new[0].tab_id
        if time.monotonic() >= deadline:
            raise _Stop("failed", "notepad_tab_not_identified", f"{len(new)} new tab(s) after the request; expected one, empty and selected")
        time.sleep(POLL_S)


def _save_actions(folder: str, name: str) -> list[dict]:
    return [key(VK_S, "ctrl", effectful=True), key(VK_D, "alt", on=DIALOG_CLASS), typed(folder, on=DIALOG_CLASS),
            key(VK_RETURN, on=DIALOG_CLASS), *_name_actions(name)]


def _name_actions(name: str) -> list[dict]:
    return [key(VK_N, "alt", on=DIALOG_CLASS), key(VK_A, "ctrl", on=DIALOG_CLASS), typed(name, on=DIALOG_CLASS),
            key(VK_RETURN, on=DIALOG_CLASS, effectful=True)]


def _await_save(desk: Desk, ref: dict, path: Path, base: int, timeout_s: float) -> str:
    """'saved', or 'conflict' while Windows asks whether to replace a file. Only the dialogs are
    counted (`base` were open before saving): the question is one more dialog over Save As, in any language."""
    deadline = time.monotonic() + timeout_s
    stem = path.stem
    while True:
        n = desk.dialogs() - base
        if n >= 2:
            return "conflict"
        if n == 0 and path.exists() and any(t.tab_id == ref["tab_id"] and stem in _title_of(t) for t in desk.tabs(ref["window"])):
            return "saved"
        if time.monotonic() >= deadline:
            raise _Stop("uncertain", "notepad_save_unconfirmed", f"{n} dialog(s) open and the tab does not show {path.name}")
        time.sleep(POLL_S)


def _refuse_overwrite(desk: Desk, send: Send, hwnd: int) -> None:
    """Answers No, with the focus confirmed on that button first. Enter is never sent on anything else."""
    for _ in range(2):
        if desk.focused() in REFUSE:
            _engine_ok(send(hwnd, [key(VK_RETURN, on=DIALOG_CLASS)]), "refusing to overwrite", after_effect=True)
            return
        _engine_ok(send(hwnd, [key(VK_TAB, on=DIALOG_CLASS)]), "reaching the No button", after_effect=True)
    raise _Stop("uncertain", "notepad_save_unconfirmed", "the No button of the overwrite question did not take the focus; nothing was overwritten")


def save_step(desk: Desk, send: Send, ctx: dict) -> dict:
    ref = _target(desk, send, ctx)
    hwnd = ref["window"]
    _focused_on(desk, ref)
    if desk.text(hwnd) != "":
        raise _Stop("failed", "notepad_target_lost", "the tab of this run is not empty")
    _engine_ok(send(hwnd, [typed(TEXT)]), "typing")
    _focused_on(desk, ref)
    if desk.text(hwnd) != TEXT:
        raise _Stop("failed", "notepad_text_mismatch", "the editor does not show the typed text; nothing was saved")
    folder = desk.desktop()
    name = free_name(folder)
    conflicts: list[str] = []
    base = desk.dialogs()
    _engine_ok(send(hwnd, _save_actions(str(folder), name)), "save", after_effect=True)
    for _ in range(MAX_NAME_TRIES):
        path = folder / name
        if _await_save(desk, ref, path, base, SAVE_TIMEOUT_S) == "saved":
            break
        # Windows asks to replace a file that appeared meanwhile: refuse and take another free name.
        conflicts.append(name)
        _refuse_overwrite(desk, send, hwnd)
        name = free_name(folder)
        _engine_ok(send(hwnd, _name_actions(name)), "save under another name", after_effect=True)
    else:
        raise _Stop("uncertain", "notepad_save_unconfirmed", f"name conflicts: {len(conflicts)}")
    check = verifiers.text_file_equals(path, TEXT)
    if not check["verified"]:
        raise _Stop("failed", "notepad_file_mismatch", check.get("code") or "content differs")
    return {"notepad": ref, "output_path": str(path), "output_name": name, "name_conflicts": conflicts,
            "verification": {k: check.get(k) for k in ("verified", "encoding", "bytes")}}


def _select(desk: Desk, send: Send, hwnd: int, tab: str) -> None:
    """Moves to a tab with Ctrl+Tab, confirming its id; at most one full turn."""
    for _ in range(len(desk.tabs(hwnd)) + 1):
        if any(t.tab_id == tab and t.selected for t in desk.tabs(hwnd)):
            return
        _engine_ok(send(hwnd, [key(VK_TAB, "ctrl")]), "changing tab")
    raise _Stop("failed", "notepad_target_lost", "the tab to close could not be selected")


def _is_own_extra(desk: Desk, hwnd: int, tab: str) -> bool:
    """A selected extra tab is the run's when closing it can lose nothing but the run's own text."""
    current = next((t for t in desk.tabs(hwnd) if t.tab_id == tab and t.selected), None)
    if current is None:
        raise _Stop("failed", "notepad_target_lost", "the tab to check is not selected")
    text = desk.text(hwnd)
    return text == TEXT or (text == "" and _title_of(current) in UNTITLED)


def _discard_prompt(desk: Desk, hwnd: int) -> bool:
    return any(b in DISCARD for b in desk.buttons(hwnd))


def _close_tab(desk: Desk, send: Send, hwnd: int, tab: str, discardable: tuple[str, ...] = ()) -> None:
    """Closes a tab. Unsaved changes are discarded only if the editor shows one of the `discardable`
    texts at the moment of the question; anything else cancels the question and stops."""
    _select(desk, send, hwnd, tab)
    if desk.foreground() != hwnd:
        raise _Stop("failed", "notepad_target_lost", "the window of this run lost the foreground")
    _engine_ok(send(hwnd, [key(VK_W, "ctrl")]), "closing the tab", after_effect=True)
    deadline = time.monotonic() + CLOSE_TIMEOUT_S
    discarded = False
    while True:
        if not desk.is_window(hwnd):
            return
        now = desk.tabs(hwnd)
        if now and not any(t.tab_id == tab for t in now):  # an empty read proves nothing
            return
        if not discarded and _discard_prompt(desk, hwnd):
            if desk.text(hwnd) not in discardable:  # a saved tab, or text this run did not type
                _engine_ok(send(hwnd, [key(VK_ESCAPE)]), "cancelling the prompt")
                raise _Stop("failed", "notepad_close_unexpected_changes", "the tab has changes this run did not make; it stays open")
            _engine_ok(send(hwnd, [key(VK_TAB)]), "reaching the discard button")
            if desk.focused() not in DISCARD:
                _engine_ok(send(hwnd, [key(VK_ESCAPE)]), "cancelling the prompt")
                raise _Stop("failed", "notepad_close_unconfirmed", "the discard button did not take the focus; nothing was discarded")
            _engine_ok(send(hwnd, [key(VK_RETURN)]), "discarding", after_effect=True)
            discarded = True
        if time.monotonic() >= deadline:
            raise _Stop("uncertain", "notepad_close_unconfirmed", "the tab did not close in time")
        time.sleep(POLL_S)


def close_step(desk: Desk, send: Send, ctx: dict) -> dict:
    ref = _target(desk, send, ctx)
    hwnd, tab = ref["window"], ref["tab_id"]
    before = list(ref.get("tabs_before") or [])
    now = [t.tab_id for t in desk.tabs(hwnd)]
    missing = [t for t in before if t not in now]
    if missing:
        raise _Stop("failed", "notepad_target_lost", f"{len(missing)} earlier tab(s) are missing; nothing was closed")
    others = [t for t in now if t != tab]
    closed = 0
    if ref.get("window_of_run"):
        for extra in list(others):
            _select(desk, send, hwnd, extra)
            if _is_own_extra(desk, hwnd, extra):
                _close_tab(desk, send, hwnd, extra, discardable=(TEXT, ""))
                others.remove(extra)
                closed += 1
    if ref.get("window_of_run") and not others:
        _close_tab(desk, send, hwnd, tab)
        deadline = time.monotonic() + CLOSE_TIMEOUT_S
        while desk.is_window(hwnd):
            if time.monotonic() >= deadline:
                raise _Stop("uncertain", "notepad_close_unconfirmed", "the window of this run stayed open after its last tab")
            time.sleep(POLL_S)
        final = {"window_closed": True, "tabs_closed": closed + 1, "extra_tabs_closed": closed}
    else:
        _close_tab(desk, send, hwnd, tab)
        left = [t.tab_id for t in desk.tabs(hwnd)] if desk.is_window(hwnd) else []
        if not left or tab in left or [t for t in others if t not in left]:
            raise _Stop("uncertain", "notepad_close_unconfirmed", "the tab of this run or another tab is not as expected")
        final = {"window_closed": False, "tabs_closed": closed + 1, "extra_tabs_closed": closed, "tabs_kept": len(left), "earlier_tabs_kept": len(before)}
    out = {k: ctx[k] for k in ("output_path", "output_name", "name_conflicts") if k in ctx}
    return {"notepad": ref, **out, "final": final}


STEPS = {"open": open_step, "save": save_step, "close": close_step}


def run(step: str, ctx: dict, desk: Desk, send: Send) -> dict:
    """One routine of the process. `ctx` is what the previous routine of this execution produced."""
    fn = STEPS.get(step)
    if fn is None:
        return {"state": "refused", "code": "invalid_job", "detail": f"unknown step {step!r}"}
    try:
        produced = fn(desk, send, ctx if isinstance(ctx, dict) else {})
    except _Stop as s:
        return {"state": s.state, "code": s.code, "detail": s.detail, "context": ctx or None}
    return {"state": "verified", "verified": True, "code": None, "context": produced}


def tabs_at_launch(desk: Desk, hwnd: int) -> dict | None:
    """What a template that saves in a new tab needs later to close it, read before its first input.
    None for a Notepad without tabs, which keeps no session: closing its window is enough."""
    tabs = desk.tabs(hwnd)
    if not tabs:
        return None
    return {"window": hwnd, "tabs_before": [t.tab_id for t in tabs], "window_of_run": _is_clean_start(tabs, desk.text(hwnd))}


def close_template_tab(desk: Desk, send: Send, start: dict, stem: str) -> dict:
    """Closes the tab a template saved, by the same rules as the close step, so that Notepad does not
    bring it back at the next start. Closing the window instead would keep every saved tab."""
    new = [t for t in desk.tabs(start["window"]) if t.tab_id not in start["tabs_before"] and stem in _title_of(t)]
    if len(new) != 1:
        return {"state": "failed", "code": "notepad_tab_not_identified", "detail": f"{len(new)} saved tab(s) of this run"}
    return run("close", {"notepad": {**start, "tab_id": new[0].tab_id}}, desk, send)
