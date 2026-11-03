"""Self-test of verify_result.py against synthetic workbooks in a temp dir.

These fixtures test the verifier only; they are never proof outputs.
Run with the verifier venv: python -m unittest test_verify_result
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from openpyxl import Workbook

import verify_result as vr


def make_book(path: Path, b2=None, b3=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    sheet = book.active
    for ref, value in vr.TEMPLATE_LABELS.items():
        sheet[ref] = value
    if b2 is not None:
        sheet["B2"] = b2
    if b3 is not None:
        sheet["B3"] = b3
    book.save(path)


def rewrite_part(path: Path, name: str, edit) -> None:
    """Re-zip the workbook with one package part transformed by `edit`."""
    with zipfile.ZipFile(path) as source:
        items = [(info, source.read(info.filename)) for info in source.infolist()]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as target:
        for info, data in items:
            target.writestr(info, edit(data) if info.filename == name else data)


class VerifyResultTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        make_book(self.base / vr.FILES["template"])
        self.assertEqual(vr.cmd_baseline(self.base), 0)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def check(self, label: str) -> dict:
        baseline = json.loads((self.base / vr.BASELINE).read_text(encoding="utf-8"))
        return vr.check_file(label, self.base / vr.FILES[label], baseline)

    def test_valid_outputs_pass(self) -> None:
        make_book(self.base / vr.FILES["gravacao"], "Cliente Teste 01", 1500)
        make_book(self.base / vr.FILES["replay"], "Cliente Teste 01", 1500.0)
        self.assertEqual(vr.cmd_check(self.base, list(vr.FILES), None), 0)

    def test_number_saved_as_text_fails(self) -> None:
        make_book(self.base / vr.FILES["replay"], "Cliente Teste 01", "1500")
        self.assertFalse(self.check("replay")["passed"])

    def test_wrong_text_fails(self) -> None:
        make_book(self.base / vr.FILES["replay"], "Cliente Teste 1", 1500)
        self.assertFalse(self.check("replay")["passed"])

    def test_boolean_is_not_number(self) -> None:
        make_book(self.base / vr.FILES["replay"], "Cliente Teste 01", True)
        self.assertFalse(self.check("replay")["passed"])

    def test_missing_output_fails(self) -> None:
        self.assertNotEqual(vr.cmd_check(self.base, ["replay"], None), 0)

    def test_modified_template_fails(self) -> None:
        make_book(self.base / vr.FILES["template"], "x", None)
        self.assertFalse(self.check("template")["passed"])

    def test_save_metadata_only_change_passes(self) -> None:
        # What Excel does on a plain re-save: new timestamp and stored folder.
        path = self.base / vr.FILES["template"]
        rewrite_part(
            path,
            "docProps/core.xml",
            lambda d: re.sub(rb"(<dcterms:modified\b[^>]*>)[^<]*", rb"\g<1>2030-01-01T00:00:00Z", d),
        )
        rewrite_part(
            path,
            "xl/workbook.xml",
            lambda d: d.replace(b"<workbookPr", b'<x15ac:absPath url="C:\\x\\" xmlns:x15ac="urn:x"/><workbookPr', 1),
        )
        result = self.check("template")
        self.assertFalse(result["file_hash_matches_baseline"])
        self.assertEqual(result["info_package_parts_changed"], [])
        self.assertTrue(result["passed"], result["checks"])

    def test_other_package_change_is_reported_not_failed(self) -> None:
        # Same cells, another part changed: T07 follows the cells (P01-D6);
        # the package comparison (P01-X1) only reports it.
        path = self.base / vr.FILES["template"]
        rewrite_part(path, "xl/styles.xml", lambda d: d + b"\n")
        result = self.check("template")
        self.assertTrue(result["passed"], result["checks"])
        self.assertEqual(result["info_package_parts_changed"], ["xl/styles.xml"])

    def test_open_template_allowed_before_recording(self) -> None:
        path = self.base / vr.FILES["template"]
        vr.excel_lock_for(path).write_bytes(b"")
        baseline = json.loads((self.base / vr.BASELINE).read_text(encoding="utf-8"))
        self.assertFalse(vr.check_file("template", path, baseline)["passed"])
        self.assertTrue(vr.check_file("template", path, baseline, allow_open=True)["passed"])

    def test_open_lock_fails(self) -> None:
        path = self.base / vr.FILES["replay"]
        make_book(path, "Cliente Teste 01", 1500)
        vr.excel_lock_for(path).write_bytes(b"")
        self.assertFalse(self.check("replay")["passed"])

    def test_baseline_not_overwritten(self) -> None:
        self.assertEqual(vr.cmd_baseline(self.base), 1)


if __name__ == "__main__":
    unittest.main()
