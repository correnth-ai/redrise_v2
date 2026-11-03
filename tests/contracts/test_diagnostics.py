"""Diagnostic convention (docs/ERROR-DIAGNOSTICS.md) and module registry.
    cd tests/contracts && <python> -B -m unittest test_diagnostics
"""

import ast
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "contracts" / "python"))
sys.path.insert(0, str(ROOT / "runner"))

from redrise_contracts import diagnostics as dg  # noqa: E402

FOOTER_PREFIX = "Code: "


class Rendering(unittest.TestCase):
    def test_four_topics_and_footer_last(self):
        d = dg.make("EXCEL-NOT-FOUND", reported_by="RR-EXCEL-DISC", correlation_id="c1")
        lines = d.render().splitlines()
        self.assertTrue(lines[0].startswith("What happened: Excel desktop was not found"))
        self.assertTrue(lines[1].startswith("Result: The check finished."))
        self.assertTrue(lines[2].startswith("Next action: "))
        self.assertTrue(lines[3].startswith("Diagnostic details: ") and "c1" in lines[3])
        self.assertEqual(lines[-1], "Code: EXCEL-NOT-FOUND | Modules: RR-EXCEL-DISC")
        self.assertTrue(d.render().isascii(), "backend text is English ASCII")

    def test_copy_includes_technical_and_footer_stays_last(self):
        d = dg.make("STEP-UNCERTAIN", reported_by="RR-ENGINE-EXEC", params={"failed_step": "step 4", "engine_code": "x"},
                    technical_details={"code": "x"})
        text = dg.render(d, include_technical=True)
        self.assertIn('"effect_state": "unknown"', text)
        self.assertTrue(text.splitlines()[-1].startswith(FOOTER_PREFIX))
        self.assertIn("An effect with unknown result exists", text)
        self.assertEqual(d.params, {"failed_step": "step 4", "engine_code": "x"})

    def test_multiple_modules(self):
        d = dg.make("CONTRACT-EXCEL-DESCRIPTOR", reported_by="RR-EXCEL-START", params={"reason": "schema"})
        self.assertEqual(dg.footer(d), "Code: CONTRACT-EXCEL-DESCRIPTOR | Modules: "
                                       "RR-EXCEL-DISC, RR-EXCEL-START, RR-CONTRACT, RR-FLOW")
        self.assertEqual(d.category, "contract")

    def test_categories_are_distinguished(self):
        cats = {c: dg.make(c, reported_by="RR-RUNNER").category for c in
                ("CONTRACT-PAYLOAD", "ENGINE-NO-RESPONSE", "EXCEL-DISCOVERY-FAILED", "EXCEL-NOT-FOUND", "STEP-UNCERTAIN")}
        self.assertEqual(cats, {"CONTRACT-PAYLOAD": "contract", "ENGINE-NO-RESPONSE": "communication",
                                "EXCEL-DISCOVERY-FAILED": "environment", "EXCEL-NOT-FOUND": "precondition",
                                "STEP-UNCERTAIN": "unknown"})

    def test_unknown_code_falls_back_to_rr_diag_without_inventing(self):
        d = dg.make("something_new", reported_by="RR-RUNNER")
        self.assertEqual(d.error_code, "UNMAPPED")
        self.assertEqual(d.module_hints, ["RR-DIAG"])
        self.assertEqual(d.technical_details["original_code"], "something_new")
        self.assertIn("something_new", d.render())

    def test_precondition_is_not_a_confirmed_defect(self):
        d = dg.make("EXCEL-NOT-FOUND", reported_by="RR-EXCEL-DISC")
        self.assertEqual(d.diagnosis_status, "unconfirmed")
        self.assertIn("module defect not confirmed", d.details_summary)

    def test_uncertain_effect_never_suggests_blind_retry(self):
        for code, e in dg.catalog().items():
            if e["effect_state"] in ("unknown", "partial"):
                self.assertEqual(e["retry"], "check_first", code)


class Propagation(unittest.TestCase):
    def test_wrap_preserves_cause_correlation_and_effect(self):
        inner = dg.make("STEP-UNCERTAIN", reported_by="RR-ENGINE-EXEC", correlation_id="abc")
        outer = dg.wrap(inner, "EXCEL-START-SCREEN-UNRESOLVED", reported_by="RR-EXCEL-START",
                        boundary={"producer": "RR-ENGINE-EXEC", "consumer": "RR-EXCEL-START", "contract": "run report"})
        self.assertEqual(outer.correlation_id, "abc")
        self.assertEqual(outer.cause.error_code, "STEP-UNCERTAIN")
        self.assertEqual(outer.effect_state, "unknown")  # most uncertain effect wins
        self.assertEqual(outer.module_hints[:2], ["RR-EXCEL-START", "RR-ENGINE-EXEC"])
        self.assertEqual(len(outer.module_hints), len(set(outer.module_hints)))
        round_trip = dg.from_dict(json.loads(json.dumps(outer.to_dict())))
        self.assertEqual(round_trip.cause.error_code, "STEP-UNCERTAIN")

    def test_validate_rejects_bad_payloads(self):
        good = dg.make("SESSION-BUSY", reported_by="RR-RUNNER").to_dict()
        self.assertEqual(dg.validate(good), [])
        for mutate, frag in ((lambda d: d.update(schema="redrise.diagnostic/0"), "schema"),
                             (lambda d: d.update(category="bug"), "category"),
                             (lambda d: d.update(module_hints=[]), "module_hints"),
                             (lambda d: d.update(module_hints=["RR-NOPE"]), "unknown module"),
                             (lambda d: d.update(effect_state="maybe"), "effect_state"),
                             (lambda d: d.pop("what_happened"), "what_happened")):
            bad = json.loads(json.dumps(good))
            mutate(bad)
            self.assertTrue(any(frag in e for e in dg.validate(bad)), frag)
        self.assertEqual(dg.validate("x"), ["not an object"])

    def test_contract_violation_names_the_boundary(self):
        d = dg.contract_violation("RR-RUNNER", "RR-CORE", "redrise.job-result/1", "missing state", reported_by="RR-CORE")
        self.assertEqual(d.boundary["contract"], "redrise.job-result/1")
        self.assertEqual(d.module_hints, ["RR-CONTRACT", "RR-RUNNER", "RR-CORE"])


class Sanitizing(unittest.TestCase):
    def test_secrets_argv_and_profile_paths(self):
        d = dg.make("UNMAPPED", reported_by="RR-RUNNER", technical_details={
            "password": "p4ss", "Authorization": "Bearer x", "argv": ["a", "b"], "env": {"A": "1"},
            "path": r"C:\Users\someone\Desktop\x.txt", "nested": {"api_key": "k", "ok": 1},
            "long": "y" * 5000})
        t = d.technical_details
        self.assertEqual(t["password"], "[redacted]")
        self.assertEqual(t["Authorization"], "[redacted]")
        self.assertEqual(t["argv"], "[omitted]")
        self.assertEqual(t["env"], "[omitted]")
        self.assertEqual(t["path"], r"%USERPROFILE%\Desktop\x.txt")
        self.assertEqual(t["nested"], {"api_key": "[redacted]", "ok": 1})
        self.assertLess(len(t["long"]), 2100)
        self.assertNotIn("p4ss", dg.render(d, include_technical=True))

    def test_missing_placeholder_does_not_break_rendering(self):
        d = dg.make("EXCEL-DISCOVERY-FAILED", reported_by="RR-EXCEL-DISC")  # no {reason}
        self.assertIn("{reason}", d.details_summary)
        self.assertTrue(d.render().splitlines()[-1].startswith(FOOTER_PREFIX))


class Language(unittest.TestCase):
    """Backend codes/messages are English ASCII; pt-BR lives only in the UI mask."""
    ROOT = Path(__file__).resolve().parents[2]

    def test_catalog_is_ascii_and_ui_mask_covers_every_code_with_same_placeholders(self):
        mask = json.loads((self.ROOT / "desktop/locale/pt-BR.json").read_text(encoding="utf-8"))
        ph = lambda s: sorted(re.findall(r"\{(\w+)\}", s))  # noqa: E731
        for code, e in dg.catalog().items():
            for f in ("what", "completed", "pending", "next", "details"):
                self.assertTrue(e[f].isascii(), (code, f))
                self.assertIn(code, mask["errors"])
                self.assertEqual(ph(mask["errors"][code][f]), ph(e[f]), (code, f))
        self.assertEqual(set(mask["errors"]), set(dg.catalog()))

    def test_backend_sources_have_no_non_ascii_string_literals(self):
        lit = re.compile(r"""(["'])(?:(?!\1).)*[^\x00-\x7F](?:(?!\1).)*\1""")
        bad = []
        for sub, pat in (("runner", "*.py"), ("core", "*.py"), ("contracts/python", "*.py"), ("browser", "*.py"),
                         ("desktop/src-tauri/src", "*.rs"), ("engine/crates", "*.rs")):
            for f in (self.ROOT / sub).rglob(pat):
                for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                    code = line.split("#")[0] if f.suffix == ".py" else line.split("//")[0]
                    if lit.search(code):
                        bad.append(f"{f.relative_to(self.ROOT)}:{n}")
        self.assertEqual(bad, [])


class Registry(unittest.TestCase):
    """Every module code maps to existing paths and symbols; every catalog
    code names registered modules."""

    def setUp(self):
        self.reg = json.loads((ROOT / "contracts" / "modules.json").read_text(encoding="utf-8"))["modules"]

    def test_catalog_modules_registered(self):
        for code, e in dg.catalog().items():
            self.assertTrue(set(e["modules"]) <= set(self.reg), code)
            for k in ("what", "completed", "pending", "next", "details"):
                self.assertTrue(e[k].strip(), (code, k))

    def test_paths_and_python_symbols_exist(self):
        for code, m in self.reg.items():
            if m.get("status", "").startswith("planned"):
                self.assertEqual(m["paths"], [], code)
                continue
            self.assertTrue(m["paths"], code)
            for p in m["paths"]:
                self.assertTrue((ROOT / p).exists(), (code, p))
            for sym in m["symbols"]:
                if "::" in sym:  # Rust module: file exists (checked via paths)
                    continue
                pkg = sym.split(".")[0]
                base = ROOT / {"redrise_runner": "runner", "redrise_core": "core"}.get(pkg, "contracts/python")
                parts = sym.split(".")
                # resolve the longest module path that exists, then check the names in its AST
                for i in range(len(parts), 1, -1):
                    f = base.joinpath(*parts[:i]).with_suffix(".py")
                    if f.is_file():
                        names = {n.name for n in ast.walk(ast.parse(f.read_text(encoding="utf-8")))
                                 if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
                        for n in parts[i:]:
                            self.assertIn(n, names, sym)
                        break
                else:
                    self.fail(f"module for {sym} not found")

    def test_conditions_exist_in_catalog(self):
        for code, m in self.reg.items():
            for c in m["conditions"]:
                self.assertIn(c, dg.catalog(), (code, c))


if __name__ == "__main__":
    unittest.main()
