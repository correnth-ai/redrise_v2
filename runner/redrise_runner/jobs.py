"""Job execution on this Runner.

Order is fixed: validate job → compatibility (category/platform of the
procedure vs this Runner) → session readiness → exclusive session lock →
Engine run → durable result. Every refusal happens before the Engine is
asked to touch the UI. A job id is executed at most once: an existing job
record is never re-run automatically (uncertain effects need reconciliation,
not replay).
"""

from __future__ import annotations

import json
import msvcrt
import os
import threading
import time
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from pathlib import Path

from .engine import EngineClient, EngineError
from .paths import Layout

RUNNER_PLATFORM = "windows-x86_64"
RUNNER_CATEGORIES = ("windows", "browser")  # Mac/Linux are not releases of this Beta.
TERMINAL = {"completed_unverified", "failed", "uncertain", "refused", "cancelled", "error"}


@dataclass
class JobSpec:
    job_id: str
    procedure: Path
    bindings: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def load(path: Path) -> "JobSpec":
        raw = json.loads(path.read_text(encoding="utf-8-sig"))  # tolerate BOM (Windows tools)
        unknown = set(raw) - {"job_id", "procedure", "bindings"}
        if unknown:
            raise ValueError(f"unknown job fields: {sorted(unknown)}")
        job_id = str(raw["job_id"])
        if not job_id or any(c in job_id for c in '\\/:*?"<>|') or job_id in {".", ".."}:
            raise ValueError("invalid job_id")
        return JobSpec(job_id, Path(raw["procedure"]), {str(k): str(v) for k, v in raw.get("bindings", {}).items()})


def _write_atomic(path: Path, value: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


class SessionBusy(Exception):
    pass


@contextmanager
def session_lock(locks_dir: Path):
    """One UI-driving execution per interactive session (OS file lock; it
    is released automatically if the process dies)."""
    locks_dir.mkdir(parents=True, exist_ok=True)
    f = open(locks_dir / "session.lock", "a+b")
    try:
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as e:
            raise SessionBusy("another job is driving this session") from e
        try:
            yield
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        f.close()


def check_compatibility(procedure: dict) -> tuple[bool, str | None, str]:
    cat, plat = procedure.get("category"), procedure.get("platform")
    if cat not in RUNNER_CATEGORIES:
        return False, "category_incompatible", f"procedure category {cat!r}; this Runner supports {list(RUNNER_CATEGORIES)}"
    if plat != RUNNER_PLATFORM:
        return False, "platform_incompatible", f"procedure platform {plat!r}; this Runner is {RUNNER_PLATFORM}"
    return True, None, "compatible"


def run_job(spec: JobSpec, layout: Layout, engine: EngineClient, cancel: threading.Event | None = None,
            engine_args: list[str] | None = None, session_lock_held: bool = False) -> dict:
    """`session_lock_held`: the caller (template flow) already holds the
    session lock, taken before it launched the target app."""
    cancel = cancel or threading.Event()
    job_dir = layout.jobs_dir / spec.job_id
    record_path = job_dir / "job.json"
    if record_path.exists():
        prior = json.loads(record_path.read_text(encoding="utf-8"))
        return {"job_id": spec.job_id, "state": "refused", "code": "job_already_exists",
                "detail": f"existing state {prior.get('state')!r}; jobs are never re-run automatically"}
    job_dir.mkdir(parents=True, exist_ok=False)
    rec: dict = {"job_id": spec.job_id, "procedure": str(spec.procedure), "bindings": spec.bindings,
                 "runner_platform": RUNNER_PLATFORM, "history": []}

    def transition(state: str, **extra) -> dict:
        rec["state"] = state
        rec.update(extra)
        rec["history"].append({"state": state, "at_unix_ms": int(time.time() * 1000)})
        _write_atomic(record_path, rec)
        return rec

    transition("accepted")
    try:
        procedure = json.loads(spec.procedure.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return transition("refused", code="procedure_unreadable", detail=str(e))
    ok, code, detail = check_compatibility(procedure)
    if not ok:
        return transition("refused", code=code, detail=detail)
    try:
        ready = engine.readiness(probe_hooks=False)
    except EngineError as e:
        return transition("error", code=e.code, detail=e.detail)
    if not ready.get("ready"):
        # Session unavailable: wait-with-reason is the Runner/Core policy (P07);
        # here the job is refused with the reason and no UI action.
        return transition("refused", code="session_unavailable", detail=ready.get("readiness", {}).get("detail"))
    try:
        with (nullcontext() if session_lock_held else session_lock(layout.locks_dir)):
            transition("running")
            result = engine.run(spec.procedure, job_dir / "run.json", spec.bindings, cancel, job_dir / "cancel.flag",
                                extra_args=engine_args)
    except SessionBusy as e:
        return transition("refused", code="session_busy", detail=str(e))
    except EngineError as e:
        return transition("error", code=e.code, detail=e.detail)
    report = result.payload.get("report", {})
    return transition(result.outcome, engine_exit=result.exit_code, code=report.get("code"),
                      detail=report.get("message"), failed_step=report.get("failed_step"), observed_outputs=report.get("observed_outputs"),
                      verified=False)
