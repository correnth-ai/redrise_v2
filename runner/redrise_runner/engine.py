"""Engine client: drives `redrise-engine.exe` through its CLI contract
(docs/decisions/E01-engine-contracts.md). The Runner never injects input
itself; the Engine does."""

from __future__ import annotations

import json
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

# Engine CLI exit codes -> outcome names (E01 decision record).
OUTCOMES = {0: "completed_unverified", 2: "refused", 3: "failed", 4: "uncertain", 5: "cancelled"}


class EngineError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass
class EngineResult:
    exit_code: int
    outcome: str
    payload: dict


class EngineClient:
    def __init__(self, command: list[str], timeout_s: float = 30.0):
        """`command` is the argv prefix, normally `[<install>/engine/redrise-engine.exe]`."""
        self.command = command
        self.timeout_s = timeout_s

    @classmethod
    def at(cls, exe: Path) -> "EngineClient":
        if not exe.is_file():
            raise EngineError("engine_missing", str(exe))
        return cls([str(exe)])

    def _call(self, args: list[str], timeout_s: float | None = None) -> tuple[int, dict]:
        try:
            p = subprocess.run(
                self.command + args,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                timeout=timeout_s or self.timeout_s,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except FileNotFoundError as e:
            raise EngineError("engine_missing", str(e)) from e
        except subprocess.TimeoutExpired as e:
            raise EngineError("engine_timeout", " ".join(args[:1])) from e
        try:
            return p.returncode, json.loads(p.stdout.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            raise EngineError("engine_bad_output", f"exit {p.returncode}") from e

    def version(self) -> dict:
        code, out = self._call(["version"])
        if code != 0:
            raise EngineError("engine_unhealthy", json.dumps(out))
        return out

    def readiness(self, probe_hooks: bool = True) -> dict:
        _, out = self._call(["readiness"] + (["--probe-hooks"] if probe_hooks else []))
        return out

    def run(self, procedure: Path, report: Path, bindings: dict[str, str], cancel: threading.Event,
            stop_file: Path, timeout_s: float = 600.0, extra_args: list[str] | None = None) -> EngineResult:
        """Runs a procedure. Cancellation is cooperative through the Engine's
        stop file (it stops between steps/characters and releases modifiers);
        the Runner never kills the Engine mid-input."""
        args = ["run", "--procedure", str(procedure), "--report", str(report), "--stop-file", str(stop_file)]
        for k, v in sorted(bindings.items()):
            args += ["--bind", f"{k}={v}"]
        args += extra_args or []
        proc = subprocess.Popen(
            self.command + args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        done = threading.Event()

        def forward_cancel() -> None:
            while not done.is_set():
                if cancel.wait(0.1):
                    if proc.poll() is None:
                        stop_file.write_text("cancel", encoding="utf-8")
                    return

        threading.Thread(target=forward_cancel, daemon=True).start()
        try:
            stdout, _ = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            cancel.set()
            try:
                stdout, _ = proc.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                # The Engine ignored its stop file: effects of the step in
                # flight are unknown, so the outcome is uncertain, never failed.
                proc.kill()
                proc.communicate()
                done.set()
                return EngineResult(-1, "uncertain", {"report": {"code": "engine_unresponsive_after_cancel"}})
        finally:
            done.set()
        try:
            payload = json.loads(stdout.decode("utf-8")) if stdout.strip() else {}
        except ValueError:
            payload = {}
        outcome = OUTCOMES.get(proc.returncode, "error")
        return EngineResult(proc.returncode, outcome, payload)
