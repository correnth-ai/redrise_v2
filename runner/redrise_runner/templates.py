"""Installed templates: inputs → preconditions → session readiness → launch
→ Engine job → independent verifier. Each refusal happens before anything
is launched or typed; `verified` comes only from the template's verifier."""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

from . import apps, notepad_steps, verifiers
from .engine import EngineClient, EngineError
from .jobs import JobSpec, SessionBusy, _write_atomic, check_compatibility, run_job, session_lock
from .paths import Layout


def _subst(value, inputs: dict[str, str]):
    if isinstance(value, str):
        return re.sub(r"\{(\w+)\}", lambda m: inputs.get(m.group(1), m.group(0)), value)
    return value


def list_templates(root: Path) -> list[dict]:
    out = []
    for t in sorted(root.glob("*/template.json")):
        j = json.loads(t.read_text(encoding="utf-8"))
        out.append({"id": j["id"], "version": j["version"], "title": j["title"], "category": j["category"],
                    "shipped": j.get("shipped", True)})
    return out


def run_template(template_id: str, layout: Layout, engine: EngineClient, given: dict[str, str],
                 desktop_dir: Path | None = None, dry_run: bool = False,
                 cancel: threading.Event | None = None) -> dict:
    tdir = layout.install_root / "templates" / template_id
    tfile = tdir / "template.json"
    if not tfile.is_file():
        return {"template": template_id, "state": "refused", "code": "template_not_installed"}
    t = json.loads(tfile.read_text(encoding="utf-8"))
    res: dict = {"template": t["id"], "version": t["version"], "verified": False}

    def done(state: str, **kw) -> dict:
        res.update(state=state, **kw)
        return res

    if t.get("shipped") is False:
        return done("refused", code="template_candidate_not_shipped", detail=t.get("open_decision"))

    # ---- inputs
    unknown = set(given) - set(t["inputs"])
    if unknown:
        return done("refused", code="unknown_input", detail=sorted(unknown))
    ctx = {"desktop": str(desktop_dir or apps.desktop())}
    inputs: dict[str, str] = {}
    for name, spec in t["inputs"].items():
        if name in given:
            inputs[name] = given[name]
        elif "default" in spec:
            inputs[name] = _subst(spec["default"], ctx)
        elif spec.get("required"):
            return done("refused", code="missing_input", detail=name)
    res["inputs"] = inputs

    # ---- preconditions (no side effects)
    exe = None
    for pc in t.get("preconditions", []):
        kind = pc["kind"]
        if kind == "app_installed":
            exe, why = apps.resolve(pc["app"])
            if exe is None:
                return done("precondition_missing", code=why, detail=f"{pc['app']} is required and was not found")
        elif kind == "output_absent":
            p = Path(inputs[pc["input"]])
            if p.exists():
                return done("refused", code="output_exists", detail=f"{p} already exists; it is never overwritten")
            if not p.parent.is_dir():
                return done("refused", code="output_parent_missing", detail=str(p.parent))
        elif kind == "file_exists":
            if not Path(inputs[pc["input"]]).is_file():
                return done("precondition_missing", code="input_missing", detail=inputs[pc["input"]])
        elif kind == "browser_packaged":
            if not (layout.install_root / "browsers").is_dir():
                return done("precondition_missing", code="browser_not_packaged")
        else:
            return done("refused", code="unknown_precondition", detail=kind)

    # ---- session readiness before launching anything
    try:
        ready = engine.readiness(probe_hooks=False)
    except EngineError as e:
        return done("error", code=e.code, detail=e.detail)
    if not ready.get("ready"):
        return done("refused", code="session_unavailable", detail=ready.get("readiness", {}).get("detail"))

    if dry_run:
        return done("ready", app=str(exe) if exe else None)

    # ---- compatibility, then the exclusive session lock, both before launching:
    # a busy session must not get a new app window stealing focus.
    if t.get("procedure"):
        ok, code, detail = check_compatibility(json.loads((tdir / t["procedure"]).read_text(encoding="utf-8")))
        if not ok:
            return done("refused", code=code, detail=detail)
    try:
        with session_lock(layout.locks_dir):
            return _launch_run_verify(t, tdir, layout, engine, inputs, exe, res, done, cancel or threading.Event())
    except SessionBusy as e:
        return done("refused", code="session_busy", detail=str(e))


def _launch_run_verify(t: dict, tdir: Path, layout: Layout, engine: EngineClient, inputs: dict[str, str],
                       exe, res: dict, done, cancel: threading.Event) -> dict:
    preexisting = verifiers.matching_windows(t["verifier"]["candidates"]) if t["verifier"]["kind"] == "window_present" else None

    # ---- launch target app (noting whether it was already open: an app the
    # user had open stays open; one opened only for this run is closed at the end)
    opened = None
    if t.get("launch"):
        image = Path(exe).name.lower()
        opened = {"image": image, "was_running": apps.is_running(image),
                  "before": {w["hwnd"] for w in verifiers.top_windows() if w["process_image"] == image}}
        args = [_subst(a, inputs) for a in t["launch"].get("args", [])]
        res["launched"] = {"app": t["launch"]["app"], "pid": apps.launch(exe, args)}
    finish = _finisher(t, opened, res, done)
    proc = json.loads((tdir / t["procedure"]).read_text(encoding="utf-8")) if t.get("procedure") else None

    # ---- the window this run opened: the Engine acts only there, never in
    # another window of the same app (restored session, a user's document)
    bound = None
    first = (proc or {}).get("steps", [{}])[0].get("expect") if proc and proc.get("category") != "browser" else None
    if opened is not None and first and first["process_image"] == opened["image"]:
        bound = apps.launched_window(opened["image"], first["class"], opened["before"],
                                     apps.foreground_window, verifiers.top_windows)
        if bound is None:
            return finish("error", code="launched_window_not_found",
                          detail=f"no new {opened['image']} {first['class']} window appeared")
        res["launched"]["window"] = bound
        if t.get("close_by") == "notepad_tab":
            opened["close_tab"] = _notepad_closer(t, bound, layout, engine, inputs, cancel)

    # ---- procedure as a job
    job = None
    if proc:
        job_id = f"tpl-{t['id']}-{time.strftime('%Y%m%d-%H%M%S')}"
        params = {p["name"] for p in proc.get("params", [])}
        if "output_path" in inputs:
            # Save As dialogs: folder goes to the navigation field, the bare
            # name to "Nome do arquivo" (never a full path in the name field).
            out_p = Path(inputs["output_path"])
            inputs = {**inputs, "output_dir": str(out_p.parent), "output_name": out_p.name}
        engine_args = ["--step-timeout-ms", str(t.get("step_timeout_ms", 10000))]
        for key, flag in (("settle_ms", "--settle-ms"), ("char_delay_ms", "--char-delay-ms"), ("stable_ms", "--stable-ms")):
            if key in t:
                engine_args += [flag, str(t[key])]
        if bound is not None:
            engine_args += ["--bound-window", str(bound)]
        if t.get("browser_profile") == "persistent":
            engine_args += ["--profile", str(layout.data_root / "browser-profile")]
        job = run_job(JobSpec(job_id, tdir / t["procedure"], {k: v for k, v in inputs.items() if k in params}),
                      layout, engine, cancel, engine_args=engine_args, session_lock_held=True)
        res["job"] = {k: job.get(k) for k in ("job_id", "state", "code", "failed_step")}
        if job["state"] not in ("completed_unverified", "uncertain"):
            return finish(job["state"], code=job.get("code"), detail=job.get("detail"))

    # ---- independent verification
    v = t["verifier"]
    kind = v["kind"]
    if kind == "text_file_equals":
        ver = verifiers.text_file_equals(Path(inputs[v["input"]]), v["text"])
    elif kind == "xlsx_cells":
        parts = [verifiers.xlsx_cells(Path(inputs[c["input"]]), {r: _subst(x, inputs) for r, x in c["cells"].items()})
                 for c in v["checks"]]
        ver = {"verified": all(p["verified"] for p in parts), "checks": parts,
               "code": None if all(p["verified"] for p in parts) else "cells_mismatch"}
    elif kind == "window_present":
        ver = verifiers.window_present(v["candidates"], v.get("timeout_ms", 60000), preexisting)
    elif kind == "browser_final_url":
        run = json.loads((layout.jobs_dir / job["job_id"] / "run.json").read_text(encoding="utf-8-sig")) if job else {}
        final = (run.get("report") or {}).get("browser_final") or {}
        ver = verifiers.browser_final_url(final.get("url"), v["rules"], v["otherwise"])
    else:
        return finish("error", code="unknown_verifier", detail=kind)
    res["verification"] = ver
    if job and job["state"] == "uncertain":
        # Reconciliation only: the verifier tells whether the uncertain effect happened.
        return finish("uncertain", code=job.get("code"), detail=job.get("detail"),
                    reconciled_effect_present=ver["verified"])
    if ver["verified"]:
        res["verified"] = True
        return finish("verified")
    return finish(ver.get("state", "refuted"), code=ver.get("code"), reason=ver.get("reason"))


def _notepad_closer(t: dict, hwnd: int, layout: Layout, engine: EngineClient, inputs: dict[str, str], cancel: threading.Event):
    """Reads the tabs now, before the first input; the returned call closes the tab of the run at the end."""
    desk = notepad_steps.UiaDesk()
    try:
        start = notepad_steps.tabs_at_launch(desk, hwnd)
    finally:
        desk.close()
    if start is None:
        return None

    def close_tab() -> dict:
        desk = notepad_steps.UiaDesk()
        try:
            send = notepad_steps.engine_sender(f"tpl-{t['id']}-close-{time.strftime('%Y%m%d-%H%M%S')}", layout, engine, cancel)
            return notepad_steps.close_template_tab(desk, send, start, Path(inputs["output_path"]).stem)
        finally:
            desk.close()
    return close_tab


def _finisher(t: dict, opened: dict | None, res: dict, done):
    """`done` plus the end-of-run rule for the app this template launched."""
    def finish(state: str, **kw) -> dict:
        if opened is not None:
            info = {"image": opened["image"], "was_running": opened["was_running"]}
            if opened["was_running"]:
                info["action"] = "kept_open_was_running"
            elif not t.get("close_opened_app", True):
                info["action"] = "kept_open_by_template"  # opening the app is the result
            elif state != "verified":
                info["action"] = "kept_open_for_checking"
            else:
                closing = opened["close_tab"]() if opened.get("close_tab") else None
                if closing and closing["state"] != "verified":
                    info.update(action="kept_open_close_failed", code=closing.get("code"))
                elif closing and closing["context"]["notepad"]["window_of_run"] and not closing["context"]["final"]["window_closed"]:
                    info["action"] = "kept_open_other_tabs"  # a tab this run did not open appeared in its window
                else:  # a restored session goes back to how it was: its tabs return at the next start
                    new = [w["hwnd"] for w in verifiers.top_windows()
                           if w["process_image"] == opened["image"] and w["hwnd"] not in opened["before"]]
                    left = apps.close_windows(new)
                    info["action"] = "closed" if not left else "close_requested_still_open"
            res["opened_app"] = info
        return done(state, **kw)
    return finish


def save_result(layout: Layout, result: dict) -> Path:
    d = layout.data_root / "template-runs"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{result.get('template')}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    _write_atomic(p, result)
    return p
