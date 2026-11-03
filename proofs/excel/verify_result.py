"""Independent read-only verifier for the P01 Excel/OpenAdapt proof.

Reads the template and the output workbooks produced through the Excel UI
(recording and replay) and checks the cells the proof defines. It never
writes to any workbook; openpyxl is used only to read.

Usage (from the dedicated verifier venv, not the OpenAdapt venv):

    python verify_result.py --base <proof dir> baseline
        Record the template's content digest (and, for information, its
        SHA-256) after it was created manually in Excel.

    python verify_result.py --base <proof dir> check [--json <report.json>]
        Verify T07 (template intact), T08 (recording output), T09 (replay
        output). Exit 0 only when every requested check passes.

T07 is judged by the template's cells, as in POC §9.2 (decision P01-D6):
labels exact and B2/B3 empty. The whole-file SHA-256 and a comparison of the
XLSX package parts against the baseline are reported as INFORMATION only; the
package comparison is custom proposal P01-X1, not an approved criterion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import load_workbook

EXPECTED_B2 = "Cliente Teste 01"
EXPECTED_B3 = 1500
TEMPLATE_LABELS = {"A1": "Campo", "B1": "Valor", "A2": "Cliente", "A3": "Valor do pedido"}

FILES = {
    "template": Path("entrada") / "template_redrise.xlsx",
    "gravacao": Path("saida") / "resultado_gravado.xlsx",
    "replay": Path("saida") / "resultado_teste.xlsx",
}
BASELINE = Path("logs") / "template_baseline.json"

# Save metadata Excel rewrites without any content change; removed before the
# package parts are digested for the informational comparison (P01-X1).
VOLATILE = {
    "docProps/core.xml": [
        re.compile(rb"<dcterms:modified\b[^>]*>[^<]*</dcterms:modified>"),
        re.compile(rb"<cp:lastModifiedBy>[^<]*</cp:lastModifiedBy>"),
    ],
    "xl/workbook.xml": [
        re.compile(rb"<x15ac:absPath\b[^>]*/>"),
    ],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_parts(path: Path) -> dict[str, str]:
    """SHA-256 of each package part, with volatile save metadata removed."""
    parts: dict[str, str] = {}
    with zipfile.ZipFile(path) as package:
        for name in sorted(package.namelist()):
            data = package.read(name)
            for pattern in VOLATILE.get(name, []):
                data = pattern.sub(b"", data)
            parts[name] = hashlib.sha256(data).hexdigest()
    return parts


def content_digest(parts: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode("ascii")).hexdigest()


def excel_lock_for(path: Path) -> Path:
    # Excel creates "~$<name>" next to a workbook while it is open.
    return path.with_name("~$" + path.name)


def read_cells(path: Path) -> dict:
    workbook = load_workbook(path, read_only=True, data_only=False)
    try:
        sheet = workbook.worksheets[0]
        cells = {ref: sheet[ref].value for ref in ("A1", "B1", "A2", "A3", "B2", "B3")}
        return {"sheet": sheet.title, "cells": cells}
    finally:
        workbook.close()


def describe(value: object) -> dict:
    return {"value": value, "type": type(value).__name__}


def check_file(label: str, path: Path, baseline: dict | None, allow_open: bool = False) -> dict:
    result: dict = {"label": label, "path": str(path), "checks": [], "passed": False}

    def add(name: str, ok: bool, detail: object = None) -> None:
        result["checks"].append({"name": name, "ok": bool(ok), "detail": detail})

    if not path.is_file():
        add("exists", False, "missing")
        return result
    add("exists", True)
    is_open = excel_lock_for(path).exists()
    result["open_in_excel"] = is_open
    if not allow_open:
        add("not_open_in_excel", not is_open, str(excel_lock_for(path)))

    file_hash = sha256(path)
    result["sha256"] = file_hash
    parts = content_parts(path)
    result["content_sha256"] = content_digest(parts)
    data = read_cells(path)
    result["sheet"] = data["sheet"]
    cells = data["cells"]
    result["cells"] = {ref: describe(value) for ref, value in cells.items()}

    for ref, expected in TEMPLATE_LABELS.items():
        add(f"label_{ref}", cells[ref] == expected, describe(cells[ref]))

    b2, b3 = cells["B2"], cells["B3"]
    if label == "template":
        add("B2_empty", b2 in (None, ""), describe(b2))
        add("B3_empty", b3 in (None, ""), describe(b3))
        result["file_hash_matches_baseline"] = baseline is not None and file_hash == baseline["sha256"]
        if baseline is not None and "content_parts" in baseline:
            expected = baseline["content_parts"]
            changed = sorted(n for n in set(expected) | set(parts) if expected.get(n) != parts.get(n))
            # Informational only (P01-X1): never part of the pass/fail checks.
            result["info_package_parts_changed"] = changed
    else:
        add("B2_exact_text", isinstance(b2, str) and b2 == EXPECTED_B2, describe(b2))
        # bool is a subclass of int; a boolean cell is not the expected number.
        numeric = isinstance(b3, (int, float)) and not isinstance(b3, bool)
        add("B3_numeric_1500", numeric and b3 == EXPECTED_B3, describe(b3))

    result["passed"] = all(check["ok"] for check in result["checks"])
    return result


def cmd_baseline(base: Path) -> int:
    template = base / FILES["template"]
    if not template.is_file():
        print(f"FAIL: template missing: {template}")
        return 1
    target = base / BASELINE
    if target.exists():
        print(f"FAIL: baseline already recorded at {target}; not overwriting.")
        return 1
    # Only the bytes on disk are baselined; an open Excel window is recorded,
    # since unsaved edits there are not part of the file.
    parts = content_parts(template)
    record = {
        "schema": 2,
        "content_sha256": content_digest(parts),
        "content_parts": parts,
        "sha256": sha256(template),
        "size": template.stat().st_size,
        "open_in_excel": excel_lock_for(template).exists(),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "cells": {k: describe(v) for k, v in read_cells(template)["cells"].items()},
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0


def cmd_check(base: Path, labels: list[str], report: Path | None, allow_open: bool = False) -> int:
    baseline_path = base / BASELINE
    baseline = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.is_file() else None
    results = [check_file(label, base / FILES[label], baseline, allow_open) for label in labels]
    criteria = {"template": "T07", "gravacao": "T08", "replay": "T09"}
    summary = {
        "verifier": "proofs/excel/verify_result.py",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "criteria": {criteria[r["label"]]: "OK" if r["passed"] else "FALHOU" for r in results},
        "passed": all(r["passed"] for r in results),
    }
    text = json.dumps(summary, indent=2, ensure_ascii=False)
    print(text)
    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(text, encoding="utf-8")
    return 0 if summary["passed"] else 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", type=Path, required=True, help="Proof directory (%%USERPROFILE%%\\RedRise-v2-dev\\proofs\\excel)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("baseline")
    check = sub.add_parser("check")
    check.add_argument("--only", choices=sorted(FILES), action="append", help="Limit to these files")
    check.add_argument("--json", type=Path, help="Also write the result to this file")
    check.add_argument(
        "--allow-open",
        action="store_true",
        help="Pre-recording check: do not fail because Excel has the file open",
    )
    args = parser.parse_args(argv)

    if args.command == "baseline":
        return cmd_baseline(args.base)
    return cmd_check(args.base, args.only or list(FILES), args.json, args.allow_open)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
