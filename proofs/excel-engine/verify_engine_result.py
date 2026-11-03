"""Independent, read-only verifier for the P01 Engine/Excel proof.

Reads the template and the two workbooks produced through the Excel UI
(Engine recording and Engine replay) and checks the cells the proof defines.
It never writes to any workbook; openpyxl is used only to read. It does not
import or call the Engine.

    python verify_engine_result.py --run <run dir> [--json <report.json>]

T07 (template intact) is judged by cells/labels (P01-D6); whole-file SHA-256
is informational. T08/T09 require B2 == "Cliente Teste 01" (text) and B3 ==
1500 (numeric) in two distinct files. Exit 0 only when every check passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from openpyxl import load_workbook

EXPECTED_B2 = "Cliente Teste 01"
EXPECTED_B3 = 1500
LABELS = {"A1": "Campo", "B1": "Valor", "A2": "Cliente", "A3": "Valor do pedido"}
FILES = {
    "template": Path("entrada") / "template_redrise.xlsx",
    "recorded": Path("saida") / "resultado_gravado.xlsx",
    "replayed": Path("saida") / "resultado_replay.xlsx",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cells(path: Path) -> dict[str, object]:
    wb = load_workbook(path, read_only=True, data_only=False)
    try:
        ws = wb.worksheets[0]
        return {ref: ws[ref].value for ref in ["A1", "B1", "A2", "A3", "B2", "B3"]}
    finally:
        wb.close()


def is_number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check(run: Path) -> dict:
    report: dict = {"run": str(run), "checks": [], "files": {}}

    def add(cid: str, ok: bool, detail: str) -> None:
        report["checks"].append({"id": cid, "result": "passed" if ok else "failed", "detail": detail})

    values = {}
    for key, rel in FILES.items():
        p = run / rel
        exists = p.is_file()
        report["files"][key] = {"path": str(p), "exists": exists, "sha256": sha256(p) if exists else None}
        add(f"{key}_exists", exists, str(p))
        if exists:
            values[key] = cells(p)
            report["files"][key]["cells"] = {k: v for k, v in values[key].items()}

    if "template" in values:
        t = values["template"]
        labels_ok = all(t[k] == v for k, v in LABELS.items())
        add("T07_template_labels", labels_ok, json.dumps({k: t[k] for k in LABELS}, ensure_ascii=False))
        add("T07_template_B2_B3_empty", t["B2"] is None and t["B3"] is None, f"B2={t['B2']!r} B3={t['B3']!r}")

    for key, tid in (("recorded", "T08"), ("replayed", "T09")):
        if key not in values:
            continue
        v = values[key]
        add(f"{tid}_{key}_labels", all(v[k] == lab for k, lab in LABELS.items()), "labels preserved")
        add(f"{tid}_{key}_B2", v["B2"] == EXPECTED_B2 and isinstance(v["B2"], str), f"B2={v['B2']!r}")
        add(f"{tid}_{key}_B3", is_number(v["B3"]) and v["B3"] == EXPECTED_B3, f"B3={v['B3']!r} ({type(v['B3']).__name__})")

    f = report["files"]
    if f.get("recorded", {}).get("exists") and f.get("replayed", {}).get("exists"):
        distinct = Path(f["recorded"]["path"]).resolve() != Path(f["replayed"]["path"]).resolve()
        add("outputs_distinct_files", distinct, "recording and replay outputs are separate files")

    report["verified"] = bool(report["checks"]) and all(c["result"] == "passed" for c in report["checks"])
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    report = check(args.run)
    text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.json:
        if args.json.exists():
            print(f"{args.json} exists; refusing to overwrite", file=sys.stderr)
            return 2
        args.json.write_text(text, encoding="utf-8")
    print(text)
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
