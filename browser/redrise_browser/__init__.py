"""RedRise Engine browser adapter (P03).

A platform adapter process owned by the Engine: it never decides what to
do. `record` streams trusted DOM events; `serve` executes one command per
JSON line and answers with one JSON line. Uses the packaged Playwright and
Chromium only (PLAYWRIGHT_BROWSERS_PATH is forced to the package path).
"""

__version__ = "0.1.0"
