"""Independent read-only verifier for the P03 browser proof.

Reads the synthetic server's store (the system of record), never the page.
    python verify_browser_result.py --store <file> --expect-records N
Each record must have cliente == "Cliente Teste 01" and valor == "1500".
Exit 0 only if the store holds exactly N matching records.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXPECTED = {"cliente": "Cliente Teste 01", "valor": "1500"}


def check(store: Path, n: int) -> dict:
    records = []
    if store.is_file():
        records = [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines() if line.strip()]
    matching = [r for r in records if all(r.get(k) == v for k, v in EXPECTED.items())]
    ok = len(records) == n and len(matching) == n
    return {"store": str(store), "exists": store.is_file(), "records": len(records), "matching": len(matching),
            "expected_records": n, "verified": ok, "values": [{k: r.get(k) for k in EXPECTED} for r in records]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", type=Path, required=True)
    ap.add_argument("--expect-records", type=int, required=True)
    a = ap.parse_args()
    r = check(a.store, a.expect_records)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
