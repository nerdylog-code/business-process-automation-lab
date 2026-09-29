import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.generate_event_log import generate, write_csv  # noqa: E402
from src.impact import AUTOMATION_SCOPE, simulate  # noqa: E402
from src.mining import load_events  # noqa: E402


class TestImpact(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.log = os.path.join(cls.tmp.name, "event_log.csv")
        write_csv(generate(cases=70, seed=42), cls.log)
        cls.events = load_events(cls.log)
        cls.report = simulate(cls.events)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_formula_is_exposed(self):
        self.assertIn("horas_economizadas", self.report["formula"])
        self.assertIn("sintético", self.report["basis"]["note"])

    def test_savings_are_positive_and_bounded(self):
        c = self.report["consolidated"]
        self.assertGreater(c["hours_saved_per_month"], 0)
        total_manual_hours = sum(e["duration_minutes"] for e in self.events) / 60.0
        self.assertLess(c["hours_saved_per_month"], total_manual_hours,
                        "não é possível economizar mais do que o total manual")

    def test_automations_cover_expected_activities(self):
        replaced = {a for spec in AUTOMATION_SCOPE.values() for a in spec["replaces"]}
        self.assertEqual(replaced, {"triagem", "conferencia_manual", "lancamento"})

    def test_scale_parameter_changes_result(self):
        bigger = simulate(self.events, cases_per_month=140)
        base = simulate(self.events, cases_per_month=70)
        self.assertGreater(bigger["consolidated"]["hours_saved_per_month"],
                           base["consolidated"]["hours_saved_per_month"])

    def test_residual_manual_kept(self):
        for item in self.report["automations"]:
            self.assertGreater(item["residual_manual_fraction"], 0,
                               "automação real sempre mantém fração manual (exceções/humano)")


if __name__ == "__main__":
    unittest.main()
