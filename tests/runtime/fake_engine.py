"""Scriptable stand-in for redrise-engine.exe's CLI contract (tests only).

Behaviour comes from FAKE_ENGINE_MODE: ready | locked | uncertain | slow.
`run` records its argv to FAKE_ENGINE_LOG so tests can prove whether the
Engine was invoked at all.
"""

import json
import os
import sys
import time
from pathlib import Path

mode = os.environ.get("FAKE_ENGINE_MODE", "ready")
log = os.environ.get("FAKE_ENGINE_LOG")
cmd = sys.argv[1]
args = sys.argv[2:]


def flag(name):
    return args[args.index(name) + 1] if name in args else None


if cmd == "version":
    print(json.dumps({"engine": "0.0.0-fake", "platform": "windows-x86_64"}))
    sys.exit(0)
if cmd == "readiness":
    ready = mode != "locked"
    print(json.dumps({"ready": ready, "readiness": {"interactive_desktop": ready, "detail": [] if ready else ["locked (fake)"]}}))
    sys.exit(0 if ready else 2)
if cmd == "run":
    if log:
        Path(log).write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
    stop = Path(flag("--stop-file"))
    if mode == "slow":
        for _ in range(100):
            if stop.exists():
                print(json.dumps({"report": {"outcome": "cancelled", "code": "cancelled", "failed_step": 1}}))
                sys.exit(5)
            time.sleep(0.05)
    if mode == "uncertain":
        print(json.dumps({"report": {"outcome": "uncertain", "code": "focus_timeout", "failed_step": 9}}))
        sys.exit(4)
    print(json.dumps({"report": {"outcome": "completed_unverified", "observed_outputs": []}}))
    sys.exit(0)
sys.exit(1)
