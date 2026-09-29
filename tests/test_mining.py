import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.generate_event_log import generate, write_csv  # noqa: E402
from src.mining import EXPECTED_SEQUENCE, _percentile, analyze, load_events  # noqa: E402


class TestMining(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.log = os.path.join(cls.tmp.name, "event_log.csv")
        write_csv(generate(cases=80, seed=42), cls.log)
        cls.events = load_events(cls.log)
        cls.report = analyze(cls.events)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_counts(self):
        self.assertEqual(self.report["cases"], 80)
        self.assertGreater(self.report["events"], 80)
        self.assertGreaterEqual(self.report["variants"]["count"], 2)

    def test_lead_time_ordering(self):
        lt = self.report["lead_time_minutes"]
        self.assertLessEqual(lt["p50"], lt["p90"])
        self.assertLessEqual(lt["p90"], lt["max"])
        self.assertGreater(lt["p50"], 0)

    def test_rework_rate_range(self):
        rate = self.report["rework"]["rework_rate"]
        self.assertGreater(rate, 0.15)
        self.assertLess(rate, 0.6)

    def test_bottleneck_is_an_activity(self):
        self.assertIn(self.report["bottleneck_activity"], self.report["per_activity"])
        worst = max(self.report["per_activity"].values(), key=lambda v: v["avg_wait_minutes"])
        self.assertEqual(worst["avg_wait_minutes"], self.report["per_activity"][self.report["bottleneck_activity"]]["avg_wait_minutes"])

    def test_conformance_and_sequence(self):
        self.assertGreater(self.report["conformance_rate"], 0.5)
        self.assertEqual(EXPECTED_SEQUENCE[0], "recebimento")
        self.assertEqual(self.report["per_activity"]["conferencia_manual"]["cases"], 80)

    def test_manual_minutes_dominates(self):
        self.assertGreater(self.report["manual_minutes"], 0)
        self.assertEqual(self.report["automated_minutes"], 0)

    def test_percentile_helper(self):
        self.assertEqual(_percentile([1, 2, 3, 4], 0.5), 2.5)
        self.assertEqual(_percentile([], 0.9), 0.0)


if __name__ == "__main__":
    unittest.main()
