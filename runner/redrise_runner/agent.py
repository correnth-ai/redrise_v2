"""Runner agent (P07): station loop against the team Core.

heartbeat (platform, categories, session) -> claim (only with a ready
session and no job in hand) -> start -> execute locally -> durable outbox ->
report result until acknowledged. Rules (P05-D7..D10):
- a job id is executed at most once on this station: a local record means
  "never again"; after a crash an unfinished record is reported `uncertain`;
- a result is written to the outbox before it is sent, so a lost ack or a
  restart re-sends the same result (idempotent on the Core) instead of
  re-running the job;
- cancellation seen in a heartbeat signals the Engine stop file.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from redrise_contracts import diagnostics as dg
from redrise_contracts.client import CoreClient, CoreError

from . import __version__, browser_open, browsers, diagnose, notepad_steps, templates
from .engine import EngineClient, EngineError
from .jobs import RUNNER_CATEGORIES, RUNNER_PLATFORM, JobSpec, SessionBusy, _write_atomic, run_job, session_lock
from .paths import Layout

RESULT_SCHEMA = "redrise.job-result/1"
CORE_STATES = {"completed_unverified", "verified", "failed", "uncertain", "refused", "cancelled", "error"}
# Template/Runner states that are not Core job states.
_TO_CORE = {"precondition_missing": "refused", "refuted": "completed_unverified", "unknown": "completed_unverified",
            "login_required": "completed_unverified", "ready": "error"}


def to_result(local: dict, correlation_id: str | None) -> dict:
    state = local.get("state")
    core_state = state if state in CORE_STATES else _TO_CORE.get(state, "error")
    d = diagnose.for_result(local, correlation_id)
    return {"schema": RESULT_SCHEMA, "state": core_state, "verified": bool(local.get("verified")) and core_state == "verified",
            "code": local.get("code"), "local_state": state, "diagnostic": d.to_dict() if d else None,
            "details": dg.sanitize({k: local.get(k) for k in ("template", "version", "job", "verification", "inputs",
                                                               "failed_step", "observed_outputs", "reconciled_effect_present",
                                                               "context", "elapsed_ms")
                                    if k in local})}


@dataclass
class AgentState:
    job_id: str | None = None
    lease_id: str | None = None
    cancel: threading.Event = field(default_factory=threading.Event)
    session_state: str = "unknown"
    session_reason: str | None = None
    last_error: dict | None = None
    core_reachable: bool = False


class Agent:
    def __init__(self, layout: Layout, engine: EngineClient, client: CoreClient, poll_s: float = 3.0, log=print):
        self.layout, self.engine, self.client, self.poll_s, self.log = layout, engine, client, poll_s, log
        self.state = AgentState()
        self.outbox = layout.data_root / "agent" / "outbox"
        self.records = layout.data_root / "agent" / "jobs"
        self.status_file = layout.data_root / "agent" / "status.json"
        self._worker: threading.Thread | None = None
        self._browsers: tuple[float, list | None] = (0.0, None)  # (monotonic time, last discovery)
        self._flush_lock = threading.Lock()  # tick and the job worker both flush

    # ------------------------------------------------------------ session
    def readiness(self) -> tuple[str, str | None]:
        try:
            r = self.engine.readiness(probe_hooks=False)
        except EngineError as e:
            return "unavailable", f"engine: {e.code}"
        if r.get("ready"):
            return "ready", None
        detail = (r.get("readiness") or {}).get("detail")
        if isinstance(detail, list):
            detail = "; ".join(map(str, detail))
        return "locked", detail or "session unavailable"

    def detected_browsers(self) -> list | None:
        """Browsers on this station, re-discovered at most every 5 minutes (registry + known paths)."""
        at, found = self._browsers
        if found is None or time.monotonic() - at > 300:
            try:
                found = browsers.discover()["browsers"]
            except Exception:  # noqa: BLE001 - not reported this time; the Core keeps the previous list
                found = None
            self._browsers = (time.monotonic(), found)
        return found

    def info(self) -> dict:
        out = {"platform": RUNNER_PLATFORM, "categories": list(RUNNER_CATEGORIES), "runner_version": __version__,
               "session_state": self.state.session_state, "session_reason": self.state.session_reason,
               "job_id": self.state.job_id, "lease_id": self.state.lease_id}
        found = self.detected_browsers()
        if found is not None:
            out["browsers"] = found
        return out

    def _browser_open(self, job: dict) -> dict:
        """Same order as other jobs: validate -> session readiness -> exclusive session lock -> act."""
        config = job.get("config")
        if not isinstance(config, dict):
            return {"state": "refused", "code": "invalid_job", "detail": "browser_open job without config"}
        try:
            ready = self.engine.readiness(probe_hooks=False)
        except EngineError as e:
            return {"state": "error", "code": e.code, "detail": e.detail}
        if not ready.get("ready"):
            return {"state": "refused", "code": "session_unavailable", "detail": (ready.get("readiness") or {}).get("detail")}
        try:
            with session_lock(self.layout.locks_dir):
                return browser_open.run(config)
        except SessionBusy as e:
            return {"state": "refused", "code": "session_busy", "detail": str(e)}

    def _notepad_step(self, job: dict) -> dict:
        """Same order as other jobs. The context is what the previous routine of this execution produced."""
        step = (job.get("config") or {}).get("step")
        try:
            ready = self.engine.readiness(probe_hooks=False)
        except EngineError as e:
            return {"state": "error", "code": e.code, "detail": e.detail}
        if not ready.get("ready"):
            return {"state": "refused", "code": "session_unavailable", "detail": (ready.get("readiness") or {}).get("detail")}
        try:
            with session_lock(self.layout.locks_dir):
                desk = notepad_steps.UiaDesk()
                try:
                    send = notepad_steps.engine_sender(f"core-{job['job_id']}", self.layout, self.engine, self.state.cancel)
                    return notepad_steps.run(step, (job.get("context") or {}).get("last") or {}, desk, send)
                finally:
                    desk.close()
        except SessionBusy as e:
            return {"state": "refused", "code": "session_busy", "detail": str(e)}

    # ------------------------------------------------------------ loop
    def recover(self) -> None:
        """At start: re-send pending results; unfinished local records become
        uncertain (they may have had effects) and are never re-run."""
        self.outbox.mkdir(parents=True, exist_ok=True)
        self.records.mkdir(parents=True, exist_ok=True)
        for rec in self.records.glob("*.json"):
            r = json.loads(rec.read_text(encoding="utf-8"))
            if r.get("phase") != "reported" and not (self.outbox / rec.name).exists():
                local = {"state": "uncertain", "code": "runner_restarted_during_job",
                         "detail": f"fase local {r.get('phase')}"}
                self._stage_result(r["job_id"], r["lease_id"], to_result(local, r.get("correlation_id")))

    def tick(self) -> None:
        self.state.session_state, self.state.session_reason = self.readiness()
        try:
            self.flush_outbox()
            hb = self.client.call("POST", "/api/v1/runner/heartbeat", self.info())
            self.state.core_reachable, self.state.last_error = True, None
            if self.state.job_id and self.state.job_id in hb.get("cancel", []):
                self.state.cancel.set()
            if self.state.job_id is None and self.state.session_state == "ready" and not any(self.outbox.glob("*.json")):
                job = self.client.call("POST", "/api/v1/runner/claim", self.info()).get("job")
                if job:
                    self.begin(job)
        except CoreError as e:
            self.state.core_reachable = e.status != 0
            self.state.last_error = e.diagnostic.to_dict()
        except Exception as e:  # noqa: BLE001 - the agent must keep running; report, do not exit
            self.state.last_error = dg.make("UNMAPPED", reported_by="RR-RUNNER",
                                            params={"original_code": type(e).__name__}).to_dict()
        self.write_status()

    def run_forever(self, stop: threading.Event) -> None:
        self.recover()
        while not stop.is_set():
            self.tick()
            stop.wait(self.poll_s)

    def write_status(self) -> None:
        s = self.state
        _write_atomic(self.status_file, {"at_unix_ms": int(time.time() * 1000), "core_reachable": s.core_reachable,
                                         "session_state": s.session_state, "session_reason": s.session_reason,
                                         "job_id": s.job_id, "last_error": s.last_error, "runner": __version__})

    # ------------------------------------------------------------ job
    def begin(self, job: dict) -> None:
        jid, lease = job["job_id"], job["lease_id"]
        rec = self.records / f"{jid}.json"
        if rec.exists():  # executed here before: never again
            self._stage_result(jid, lease, to_result({"state": "refused", "code": "job_already_exists",
                                                      "detail": "registro local existente"}, job.get("correlation_id")))
            return
        _write_atomic(rec, {"job_id": jid, "lease_id": lease, "phase": "claimed", "correlation_id": job.get("correlation_id")})
        if job.get("schema") != "redrise.job/1":
            d = dg.contract_violation("RR-CORE", "RR-RUNNER", "redrise.job/1", f"schema {job.get('schema')!r}",
                                      reported_by="RR-RUNNER", correlation_id=job.get("correlation_id"))
            self._stage_result(jid, lease, {"schema": RESULT_SCHEMA, "state": "refused", "verified": False,
                                            "code": "contract", "diagnostic": d.to_dict(), "details": {}})
            return
        go = self.client.call("POST", f"/api/v1/runner/jobs/{jid}/start", {"lease_id": lease})
        if not go.get("proceed"):
            _write_atomic(rec, {"job_id": jid, "lease_id": lease, "phase": "reported"})
            return
        _write_atomic(rec, {"job_id": jid, "lease_id": lease, "phase": "running", "correlation_id": job.get("correlation_id")})
        self.state.job_id, self.state.lease_id = jid, lease
        self.state.cancel = threading.Event()
        self._worker = threading.Thread(target=self._execute, args=(job,), name=f"job-{jid[:8]}", daemon=True)
        self._worker.start()

    def _execute(self, job: dict) -> None:
        jid, lease, cid = job["job_id"], job["lease_id"], job.get("correlation_id")
        try:
            if job["kind"] == "browser_open":
                local = self._browser_open(job)
            elif job["kind"] == "notepad_step":
                local = self._notepad_step(job)
            elif job["kind"] == "template":
                local = templates.run_template(job["template_id"], self.layout, self.engine, dict(job.get("inputs") or {}),
                                               cancel=self.state.cancel)
                if job.get("template_version") and local.get("version") and local["version"] != job["template_version"]:
                    local.setdefault("notes", []).append(f"template {local['version']} != routine {job['template_version']}")
            else:
                work = self.layout.data_root / "agent" / "procedures"
                work.mkdir(parents=True, exist_ok=True)
                proc = work / f"{jid}.json"
                proc.write_text(json.dumps(job["procedure"], ensure_ascii=False), encoding="utf-8")
                inputs = dict(job.get("inputs") or {})
                names = {p.get("name") for p in job["procedure"].get("params", [])}
                if "output_path" in inputs and {"output_dir", "output_name"} <= names:
                    # Save As: folder in the navigation field, bare name in "Nome do arquivo".
                    out_p = Path(inputs["output_path"])
                    inputs.setdefault("output_dir", str(out_p.parent))
                    inputs.setdefault("output_name", out_p.name)
                local = run_job(JobSpec(f"core-{jid}", proc, {k: v for k, v in inputs.items() if k in names}),
                                self.layout, self.engine, self.state.cancel)
        except Exception as e:  # noqa: BLE001 - effects unknown once execution began
            local = {"state": "uncertain", "code": "runner_exception", "detail": type(e).__name__}
        self._stage_result(jid, lease, to_result(local, cid))
        self.state.job_id = self.state.lease_id = None
        try:
            self.flush_outbox()
        except CoreError as e:
            self.state.last_error = e.diagnostic.to_dict()

    def _stage_result(self, jid: str, lease: str, result: dict) -> None:
        _write_atomic(self.outbox / f"{jid}.json", {"job_id": jid, "lease_id": lease, "result": result})
        _write_atomic(self.records / f"{jid}.json", {"job_id": jid, "lease_id": lease, "phase": "result_staged"})

    def flush_outbox(self) -> None:
        with self._flush_lock:
            self._flush_outbox()

    def _flush_outbox(self) -> None:
        for f in sorted(self.outbox.glob("*.json")):
            item = json.loads(f.read_text(encoding="utf-8"))
            try:
                self.client.call("POST", f"/api/v1/runner/jobs/{item['job_id']}/result",
                                 {"lease_id": item["lease_id"], "result": item["result"]})
            except CoreError as e:
                if e.status in (0, 500, 502, 503):  # transport/server: keep and retry later
                    raise
                # Refused by the Core (e.g. 409 after lease loss): keep the evidence, stop resending.
                _write_atomic(f.with_suffix(".rejected"), {**item, "core_diagnostic": e.diagnostic.to_dict()})
            f.unlink()
            _write_atomic(self.records / f.name, {"job_id": item["job_id"], "lease_id": item["lease_id"], "phase": "reported"})
