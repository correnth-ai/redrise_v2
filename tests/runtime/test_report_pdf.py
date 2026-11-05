"""Report of an execution (runner/redrise_runner/report_pdf.py): content from the real
execution, labels, free name without overwriting, read back. No app is opened.

    cd tests/runtime && <lab python> -B -m unittest test_report_pdf
"""

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runner"))
sys.path.insert(0, str(ROOT / "contracts" / "python"))

from redrise_runner import agent, report_pdf  # noqa: E402

LOGO = ROOT / "assets" / "brand" / "redrise" / "redrise-icon-128x128.png"
PT = {"title": "Relat\xf3rio de execu\xe7\xe3o", "this_report": "Este relat\xf3rio", "not_run": "N\xe3o executada", "state_verified": "Verificada"}


def execution(**over):
    return {"process_name": "Pedidos (dia)", "station_name": "estacao", "requested_by": "pessoa", "created_at": "2026-11-04T10:00:00+00:00", "correlation_id": "abc123",
            "context": {"steps": {"1": {"output_path": r"C:\Exemplos\a.txt"}}},
            "steps": [{"position": 1, "name": "Abrir", "state": "verified", "verified": True, "finished_at": "2026-11-04T10:01:00+00:00"},
                      {"position": 2, "name": "Conferir", "state": "verified", "verified": True, "review": {"decided_by_name": "Bia"}, "finished_at": "2026-11-04T10:02:00+00:00"},
                      {"position": 3, "name": "Gerar relat\xf3rio", "state": "running", "verified": False},
                      {"position": 4, "name": "Depois", "state": None, "verified": False}], **over}


def text_of(raw: bytes) -> str:
    """The page text as written: strings of the uncompressed content streams, in WinAnsi."""
    parts = re.findall(rb"\(((?:\\.|[^\\)])*)\) Tj", raw)
    return "\n".join(re.sub(rb"\\(.)", rb"\1", p).decode("cp1252") for p in parts)


class BuildTest(unittest.TestCase):
    def test_contents_come_from_the_execution(self):
        raw = report_pdf.build(execution(), PT, this_position=3, generated_at=datetime(2026, 11, 4, tzinfo=timezone.utc))
        t = text_of(raw)
        for piece in ("Relat\xf3rio de execu\xe7\xe3o", "Pedidos (dia)", "estacao", "1. Abrir", "Approved by Bia", "3. Gerar relat\xf3rio", "Este relat\xf3rio",
                      "4. Depois", "N\xe3o executada", r"C:\Exemplos\a.txt", "abc123", "2 of 2 steps verified"):
            self.assertIn(piece, t)
        self.assertIn("All the previous steps were verified.", t)
        self.assertEqual(report_pdf.well_formed(raw), 1)

    def test_a_step_without_verification_shows_in_the_result_and_pending(self):
        ex = execution()
        ex["steps"][1].update(verified=False, state="uncertain", review=None)
        t = text_of(report_pdf.build(ex, this_position=3))
        self.assertIn("There are steps without a verified result", t)
        self.assertIn("2. Conferir", t)
        self.assertIn("Uncertain", t)

    def test_a_prepared_message_never_reads_as_sent(self):
        ex = execution()
        ex["context"]["steps"]["2"] = {"message": {"status": "prepared"}}
        t = text_of(report_pdf.build(ex, this_position=3))
        self.assertIn("Message prepared, not sent", " ".join(t.split()))

    def test_a_long_approver_name_is_not_cut(self):
        ex = execution()
        ex["steps"][1]["review"]["decided_by_name"] = "Pessoa Com Um Nome Bastante Comprido Silva"
        t = " ".join(text_of(report_pdf.build(ex, this_position=3)).split())
        self.assertIn("Comprido Silva", t)

    def test_continuation_off_ends_what_is_pending(self):
        ex = execution()
        ex["steps"][2]["continue_next"] = False
        t = text_of(report_pdf.build(ex, this_position=3))
        self.assertIn("Nothing is pending after this report.", t)
        self.assertNotIn("4. Depois\n4. Depois", t)

    def test_nothing_pending(self):
        ex = execution()
        ex["steps"] = ex["steps"][:3]
        ex["context"] = {}
        t = text_of(report_pdf.build(ex, this_position=3))
        self.assertIn("Nothing is pending after this report.", t)
        self.assertIn("No file was recorded.", t)

    def test_long_execution_breaks_pages_and_keeps_every_step(self):
        ex = execution()
        ex["steps"] = [{"position": i, "name": f"Etapa {i}", "state": "verified", "verified": True} for i in range(1, 121)]
        raw = report_pdf.build(ex, this_position=120)
        self.assertGreater(report_pdf.well_formed(raw), 2)
        t = text_of(raw)
        self.assertIn("1. Etapa 1", t)
        self.assertIn("120. Etapa 120", t)
        self.assertRegex(t, r"Page 3 of \d")

    def test_logo_is_embedded_with_its_transparency(self):
        raw = report_pdf.build(execution(), logo=LOGO.read_bytes(), this_position=3)
        self.assertIn(b"/XObject << /Logo", raw)
        self.assertIn(b"/SMask", raw)
        self.assertIn(b"/Logo Do", raw)
        report_pdf.well_formed(raw)
        w, h, rgb, alpha = report_pdf.read_png(LOGO.read_bytes())
        self.assertEqual((w, h, len(rgb), len(alpha)), (128, 128, 128 * 128 * 3, 128 * 128))

    def test_a_damaged_logo_does_not_stop_the_report(self):
        raw = report_pdf.build(execution(), logo=b"not a png", this_position=3)
        self.assertNotIn(b"/Logo Do", raw)
        self.assertEqual(report_pdf.well_formed(raw), 1)

    def test_outside_reader_when_available(self):
        tool = shutil.which("pdftotext")
        if not tool:
            self.skipTest("pdftotext not available")
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.pdf"
            f.write_bytes(report_pdf.build(execution(), PT, LOGO.read_bytes(), this_position=3))
            out = subprocess.run([tool, "-enc", "UTF-8", str(f), "-"], capture_output=True, check=True).stdout.decode("utf-8", "replace")
        self.assertIn("Relat\xf3rio de execu\xe7\xe3o", out)
        self.assertIn("1. Abrir", out)

    def test_damage_is_detected(self):
        raw = report_pdf.build(execution(), this_position=3)
        with self.assertRaises(ValueError):
            report_pdf.well_formed(raw[:-20])
        with self.assertRaises(ValueError):
            report_pdf.well_formed(raw.replace(b"4 0 obj", b"4 0 xxx"))
        self.assertTrue(zlib)


class RunTest(unittest.TestCase):
    def job(self, **over):
        return {"config": {"action": "report", "labels": PT}, "position": 3, "execution": execution(), **over}

    def test_saves_verifies_and_reports(self):
        with tempfile.TemporaryDirectory() as d:
            out = report_pdf.run(self.job(), Path(d) / "novo", LOGO)
            self.assertEqual((out["state"], out["verified"]), ("verified", True))
            r = out["context"]["report"]
            self.assertRegex(r["file"], r"^Relatorio_Pedidos_dia_\d{8}-\d{4}\.pdf$")
            self.assertEqual((Path(d) / "novo" / r["file"]).stat().st_size, r["bytes"])

    def test_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            first = report_pdf.run(self.job(), Path(d))["context"]["report"]["file"]
            (Path(d) / first).write_bytes(b"do usuario")
            names = []
            for _ in range(2):
                names.append(report_pdf.run(self.job(), Path(d))["context"]["report"]["file"])
            self.assertEqual((Path(d) / first).read_bytes(), b"do usuario")
            self.assertEqual(len(set(names)), 2)
            self.assertTrue(all("[" in n and n != first for n in names if n[:-4].split("[")[0] == first[:-4]))

    def test_failure_leaves_nothing_and_reports(self):
        with tempfile.TemporaryDirectory() as d:
            blocked = Path(d) / "arquivo"
            blocked.write_text("x")
            out = report_pdf.run(self.job(), blocked)  # a file where the folder should be
            self.assertEqual((out["state"], out["code"]), ("failed", "report_write_failed"))
            r = agent.to_result(out, "cid")
            self.assertEqual(r["diagnostic"]["error_code"], "REPORT-WRITE-FAILED")
            self.assertEqual(r["diagnostic"]["module_hints"], ["RR-REPORT"])

    def test_without_the_execution_it_refuses(self):
        self.assertEqual(report_pdf.run({"config": {}})["code"], "invalid_job")


if __name__ == "__main__":
    unittest.main()
