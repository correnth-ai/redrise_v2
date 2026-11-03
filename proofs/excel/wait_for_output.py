"""Probe for `openadapt-flow record --until-cmd`: exit 0 once the saved copy exists.

The recorder runs this on an interval. It succeeds only when the output
workbook exists and its size has been stable for two consecutive probes, so
recording stops after the save completed. Excel's "~$" lock is not used: it
stays while the saved copy remains open in Excel.
Stdlib only; it never opens or modifies the workbook.
"""

from __future__ import annotations

import sys
from pathlib import Path

target = Path(sys.argv[1])
marker = target.with_name(target.name + ".probe-size")

if not target.is_file():
    sys.exit(1)

size = target.stat().st_size
previous = marker.read_text(encoding="ascii") if marker.is_file() else ""
marker.write_text(str(size), encoding="ascii")
if size > 0 and previous == str(size):
    marker.unlink()
    sys.exit(0)
sys.exit(1)
