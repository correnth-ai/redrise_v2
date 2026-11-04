"""Runner results -> structured diagnostics (contracts/errors.json).

Existing result `state`/`code` fields stay as they are (their consumers and
tests are preserved); a non-successful result additionally carries
`diagnostic` (redrise.diagnostic/1) and the rendered `message`."""

from __future__ import annotations

from redrise_contracts import diagnostics as dg

from . import __version__

# runner/template code -> (error code, reported_by, params builder)
_CODES: dict[str, tuple[str, str]] = {
    "session_unavailable": ("SESSION-UNAVAILABLE", "RR-RUNNER"),
    "session_busy": ("SESSION-BUSY", "RR-RUNNER"),
    "runtime_not_private": ("RUNTIME-NOT-PRIVATE", "RR-RUNTIME"),
    "browser_not_packaged": ("RUNTIME-NOT-PRIVATE", "RR-RUNTIME"),
    "engine_missing": ("ENGINE-MISSING", "RR-RUNTIME"),
    "engine_timeout": ("ENGINE-NO-RESPONSE", "RR-RUNNER"),
    "engine_bad_output": ("ENGINE-NO-RESPONSE", "RR-RUNNER"),
    "engine_unhealthy": ("ENGINE-NO-RESPONSE", "RR-RUNNER"),
    "job_already_exists": ("JOB-ALREADY-EXISTS", "RR-RUNNER"),
    "invalid_job": ("JOB-INVALID", "RR-RUNNER"),
    "procedure_unreadable": ("JOB-INVALID", "RR-RUNNER"),
    "category_incompatible": ("PROCEDURE-INCOMPATIBLE", "RR-RUNNER"),
    "platform_incompatible": ("PROCEDURE-INCOMPATIBLE", "RR-RUNNER"),
    "output_exists": ("OUTPUT-EXISTS", "RR-FLOW"),
    "unknown_input": ("INPUT-INVALID", "RR-FLOW"),
    "missing_input": ("INPUT-INVALID", "RR-FLOW"),
    "output_parent_missing": ("INPUT-INVALID", "RR-FLOW"),
    "input_missing": ("INPUT-FILE-MISSING", "RR-FLOW"),
    "excel_not_installed": ("EXCEL-NOT-FOUND", "RR-EXCEL-DISC"),
    "outlook_not_installed": ("APP-NOT-INSTALLED", "RR-FLOW"),
    "notepad_not_found": ("APP-NOT-INSTALLED", "RR-FLOW"),
    "launched_window_not_found": ("APP-WINDOW-NOT-FOUND", "RR-FLOW"),
    "template_not_installed": ("TEMPLATE-UNAVAILABLE", "RR-FLOW"),
    "template_candidate_not_shipped": ("TEMPLATE-UNAVAILABLE", "RR-FLOW"),
    "login_required": ("LOGIN-REQUIRED", "RR-FLOW"),
    "station_not_joined": ("STATION-NOT-JOINED", "RR-RUNNER"),
    "invalid_join_code": ("JOIN-CODE-INVALID", "RR-RUNNER"),
    "runner_restarted_during_job": ("STEP-UNCERTAIN", "RR-RUNNER"),
    "runner_exception": ("STEP-UNCERTAIN", "RR-RUNNER"),
    "input_monitor_unavailable": ("SESSION-UNAVAILABLE", "RR-ENGINE-EXEC"),
}
# Browser opening routine (browser_open.py): its own codes win over the generic Engine state mapping.
_BROWSER: dict[str, tuple[str, str]] = {
    "browser_not_found": ("BROWSER-NOT-FOUND", "RR-BROWSER-OPEN"),
    "browser_open_failed": ("BROWSER-OPEN-FAILED", "RR-BROWSER-OPEN"),
    "browser_open_unconfirmed": ("BROWSER-OPEN-UNCONFIRMED", "RR-BROWSER-OPEN"),
    "browser_page_not_ready": ("BROWSER-PAGE-NOT-READY", "RR-BROWSER-OPEN"),
    "browser_uia_unavailable": ("BROWSER-IDENTIFY-UNAVAILABLE", "RR-BROWSER-OPEN"),
}
# Boas-vindas process (notepad_steps.py): a lost target or an unconfirmed effect keeps its own message.
_NOTEPAD: dict[str, str] = {
    "notepad_window_not_found": "APP-WINDOW-NOT-FOUND",
    "notepad_context_missing": "NOTEPAD-CONTEXT-MISSING",
    "notepad_tabs_unavailable": "NOTEPAD-TABS-UNAVAILABLE",
    "notepad_tab_not_identified": "NOTEPAD-TAB-NOT-IDENTIFIED",
    "notepad_target_lost": "NOTEPAD-TARGET-LOST",
    "notepad_text_mismatch": "NOTEPAD-TEXT-MISMATCH",
    "notepad_file_mismatch": "NOTEPAD-FILE-MISMATCH",
    "notepad_save_unconfirmed": "NOTEPAD-SAVE-UNCONFIRMED",
    "notepad_close_unexpected_changes": "NOTEPAD-CLOSE-CHANGES",
    "notepad_close_unconfirmed": "NOTEPAD-CLOSE-UNCONFIRMED",
}
_STATES = {"failed": "STEP-FAILED", "uncertain": "STEP-UNCERTAIN", "cancelled": "RUN-CANCELLED"}
SUCCESS = {"verified", "completed_unverified", "ready"}


def for_result(res: dict, correlation_id: str | None = None) -> dg.Diagnostic | None:
    state, code = res.get("state"), res.get("code")
    if state in SUCCESS:
        return None
    detail = res.get("detail")
    params = {"reason": detail if isinstance(detail, str) else (code or state), "path": detail, "app": code,
              "prior_state": detail, "failed_step": _step(res), "engine_code": code or "-",
              "failed_checks": detail or code, "verifier_code": code, "original_code": code or state}
    tech = {"state": state, "code": code, "detail": detail, "job": res.get("job"), "template": res.get("template")}
    version = {"runner": __version__}
    if code in _BROWSER:
        ecode, by = _BROWSER[code]
        params["browser"] = detail if isinstance(detail, str) else "-"
    elif code in _NOTEPAD:
        ecode, by = _NOTEPAD[code], "RR-NOTEPAD"
        params["app"] = "notepad"
    elif state in ("failed", "uncertain") and code == "user_input_detected":
        ecode, by = "RUN-INTERRUPTED-BY-INPUT", "RR-ENGINE-EXEC"
    elif state in _STATES:  # Engine outcome; its own code stays in the details
        ecode, by = _STATES[state], "RR-ENGINE-EXEC"
    elif code in _CODES:
        ecode, by = _CODES[code]
    elif state in ("refuted", "unknown") or (state == "error" and code == "cells_mismatch"):
        ecode, by = ("LOGIN-REQUIRED", "RR-FLOW") if code == "login_required" else ("RESULT-NOT-VERIFIED", "RR-FLOW")
        params["reason"] = res.get("reason") or code
    else:
        ecode, by = code or state or "?", "RR-RUNNER"  # unmapped -> UNMAPPED / RR-DIAG
    return dg.make(ecode, reported_by=by, params=params, correlation_id=correlation_id or res.get("correlation_id"),
                   version=version, technical_details=tech)


def _step(res: dict):
    job = res.get("job") or {}
    s = res.get("failed_step", job.get("failed_step"))
    return f"step {s}" if s is not None else "step not reported"


def attach(res: dict, correlation_id: str | None = None) -> dict:
    d = for_result(res, correlation_id)
    if d is not None:
        res["diagnostic"] = d.to_dict()
        res["message"] = d.render()
    return res
