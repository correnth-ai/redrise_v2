"""Verifier self-tests: the verifier must refute false success.

Fixture workbooks are written with openpyxl here ONLY to test the reader;
they never stand in for Engine output in the proof.
"""

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

import verify_engine_result as v


def make(path: Path, b2=None, b3=None, labels=True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    if labels:
        for ref, val in v.LABELS.items():
            ws[ref] = val
    ws["B2"], ws["B3"] = b2, b3
    wb.save(path)


class VerifierTests(unittest.TestCase):
    def run_case(self, rec=("Cliente Teste 01", 1500), rep=("Cliente Teste 01", 1500), tpl=(None, None)):
        d = Path(tempfile.mkdtemp())
        make(d / v.FILES["template"], *tpl)
        if rec:
            make(d / v.FILES["recorded"], *rec)
        if rep:
            make(d / v.FILES["replayed"], *rep)
        return v.check(d)

    def test_all_good(self):
        self.assertTrue(self.run_case()["verified"])

    def test_number_as_text_is_refuted(self):
        self.assertFalse(self.run_case(rep=("Cliente Teste 01", "1500"))["verified"])

    def test_wrong_text_is_refuted(self):
        self.assertFalse(self.run_case(rec=("Cliente Teste 1", 1500))["verified"])

    def test_missing_replay_is_refuted(self):
        self.assertFalse(self.run_case(rep=None)["verified"])

    def test_dirty_template_is_refuted(self):
        self.assertFalse(self.run_case(tpl=("x", None))["verified"])

    def test_empty_output_is_refuted(self):
        self.assertFalse(self.run_case(rec=(None, None))["verified"])


if __name__ == "__main__":
    unittest.main()
