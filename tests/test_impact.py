"""Impacto: o residual tem de ser MEDIDO (mudar o insumo muda o número) — nada de constante mágica."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.generate_event_log import generate, write_csv  # noqa: E402
from src.impact import measure_residuals, simulate  # noqa: E402
from src.rules import validate_document  # noqa: E402


class TestImpact(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.events, cls.documents = generate(cases=70, seed=42)
        cls.docs_path = os.path.join(cls.tmp.name, "documents.csv")
        write_csv(cls.documents, cls.docs_path)
        cls.residuals = measure_residuals(cls.docs_path, cls.events)
        cls.report = simulate(cls.events, cls.residuals)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_residuals_are_measured_not_hardcoded(self):
        """Recalcula independentemente a partir dos documentos: tem de bater exatamente."""
        human_review = 0
        invalid_id = 0
        for document in self.documents:
            result = validate_document(document)
            if result["needs_human_review"]:
                human_review += 1
            if any(d["rule"] == "identificador_invalido" for d in result["divergences"]):
                invalid_id += 1
        self.assertAlmostEqual(self.residuals["human_review_share"], human_review / len(self.documents), places=4)
        self.assertAlmostEqual(self.residuals["invalid_identifier_share"], invalid_id / len(self.documents), places=4)

    def test_changing_documents_changes_residual(self):
        """Prova de ausência de número mágico: mais documentos limpos => residual menor."""
        clean = [dict(d, divergence="", cnpj="11222333000181", amount=d["expected_amount"], due_date="2026-06-30")
                 for d in self.documents]
        clean_path = os.path.join(self.tmp.name, "clean.csv")
        write_csv(clean, clean_path)
        clean_residuals = measure_residuals(clean_path, self.events)
        self.assertLess(clean_residuals["human_review_share"], self.residuals["human_review_share"])

    def test_every_automation_has_a_measured_source(self):
        for automation in self.report["automations"]:
            self.assertIn(automation["residual_source"], self.residuals)
            self.assertEqual(automation["residual_measured"], self.residuals[automation["residual_source"]])

    def test_sensitivity_band_is_ordered(self):
        for automation in self.report["automations"]:
            hours = automation["hours_saved_per_month"]
            self.assertLessEqual(hours["pessimistic"], hours["measured"])
            self.assertLessEqual(hours["measured"], hours["optimistic"])

    def test_savings_positive_bounded_and_consistent(self):
        c = self.report["consolidated"]
        self.assertGreater(c["hours_saved_per_month"], 0)
        self.assertLess(c["manual_hours_after"], c["manual_hours_before"])
        manual = sum(e["duration_minutes"] for e in self.events) / 60.0
        self.assertAlmostEqual(c["manual_hours_before"], manual, places=1)
        self.assertAlmostEqual(c["hours_saved_per_year"], round(c["hours_saved_per_month"] * 12, 1), places=1)

    def test_basis_is_declared_synthetic(self):
        self.assertIn("sintétic", self.report["basis"]["note"])
        self.assertIn("não é resultado corporativo", self.report["basis"]["note"])
        self.assertEqual(self.report["basis"]["cases_in_log"], 70)

    def test_scale_parameter_scales_linearly(self):
        doubled = simulate(self.events, self.residuals, cases_per_month=140)
        self.assertAlmostEqual(doubled["consolidated"]["hours_saved_per_month"],
                               self.report["consolidated"]["hours_saved_per_month"] * 2, delta=0.3)


if __name__ == "__main__":
    unittest.main()
