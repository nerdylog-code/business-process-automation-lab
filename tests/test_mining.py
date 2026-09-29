"""Discovery/conformance: os números têm de vir do log, não de constante."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.generate_event_log import generate  # noqa: E402
from src.mining import (  # noqa: E402
    _percentile,
    accept_edges,
    analyze,
    conformance,
    discover_dfg,
    traces_by_case,
)


class TestMining(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        events, _ = generate(cases=120, seed=42)
        cls.events = events
        cls.report = analyze(events)
        cls.traces = traces_by_case(events)

    def test_counts(self):
        self.assertEqual(self.report["cases"], 120)
        self.assertGreater(self.report["events"], 120)
        self.assertGreaterEqual(self.report["variants"]["count"], 2)

    def test_lead_time_ordering(self):
        lt = self.report["lead_time_minutes"]
        self.assertLessEqual(lt["p50"], lt["p90"])
        self.assertLessEqual(lt["p90"], lt["max"])
        self.assertGreater(lt["p50"], 0)

    def test_rework_rate_matches_log(self):
        expected = len({e["case_id"] for e in self.events if e["rework"]}) / 120
        self.assertAlmostEqual(self.report["rework"]["rework_rate"], expected, places=3)

    def test_bottleneck_comes_from_the_log(self):
        waits = {name: data["avg_wait_minutes"] for name, data in self.report["per_activity"].items()}
        self.assertEqual(self.report["bottleneck_activity"], max(waits, key=waits.get))

    def test_variant_shares_sum_to_one(self):
        trace_counts = {}
        for trace in self.traces.values():
            trace_counts[" -> ".join(trace)] = trace_counts.get(" -> ".join(trace), 0) + 1
        self.assertEqual(sum(trace_counts.values()), 120)
        top = self.report["variants"]["top"]
        self.assertTrue(all(0 < v["share"] <= 1 for v in top))
        self.assertAlmostEqual(sum(v["share"] for v in top), sum(v["cases"] for v in top) / 120, places=3)

    def test_dfg_is_derived_from_traces(self):
        dfg = discover_dfg(self.traces)
        expected_edges = set()
        for trace in self.traces.values():
            expected_edges |= set(zip(trace, trace[1:]))
        self.assertEqual({(e["source"], e["target"]) for e in dfg["edges"]}, expected_edges)
        self.assertEqual(sum(e["count"] for e in dfg["edges"]), sum(len(t) - 1 for t in self.traces.values()))
        self.assertEqual(dfg["start_activities"][0]["activity"], "recebimento")
        self.assertEqual(dfg["end_activities"][0]["activity"], "lancamento")

    def test_edge_filter_drops_rare_edges(self):
        dfg = discover_dfg(self.traces)
        noisy = {"nodes": dfg["nodes"], "edges": dfg["edges"] + [
            {"source": "a", "target": "b", "count": 1, "cases": 1, "probability": 0.0001}],
            "start_activities": dfg["start_activities"], "end_activities": dfg["end_activities"]}
        model = accept_edges(noisy, min_support=3, min_probability=0.05)
        self.assertNotIn(("a", "b"), {(e["source"], e["target"]) for e in model["edges"]})

    def test_conformance_is_perfect_on_same_log(self):
        dfg = discover_dfg(self.traces)
        model = accept_edges(dfg)
        conf = conformance(self.traces, model)
        self.assertEqual(conf["fitness_log_to_model"], 1.0, "modelo descoberto do próprio log deve cobrir 100% das arestas")
        self.assertEqual(conf["trace_fitness"], 1.0)
        self.assertEqual(conf["deviating_cases"], 0)

    def test_conformance_penalizes_deviation(self):
        """Log com uma aresta nova (fora do modelo) derruba fitness e aponta o caso."""
        dfg = discover_dfg(self.traces)
        model = accept_edges(dfg)
        deviating = dict(self.traces)
        deviating["DOC-9999"] = ["recebimento", "lancamento"]  # aresta inexistente no processo
        conf = conformance(deviating, model)
        self.assertLess(conf["fitness_log_to_model"], 1.0)
        self.assertLess(conf["trace_fitness"], 1.0)
        self.assertEqual(conf["deviating_examples"][0]["case_id"], "DOC-9999")
        self.assertIn("recebimento->lancamento", conf["deviating_examples"][0]["missing_edges"])

    def test_no_hardcoded_expected_sequence(self):
        """A descoberta não pode depender de constante: log sem retrabalho => modelo sem `correcao`."""
        events, _ = generate(cases=60, seed=3, rework_rate=0.0)
        report = analyze(events)
        discovered = set(report["discovered_model"]["nodes"])
        self.assertNotIn("correcao", discovered, "modelo descoberto seguiu o log (sem correcao)")

    def test_percentile_edge_cases(self):
        self.assertEqual(_percentile([], 0.5), 0.0)
        self.assertEqual(_percentile([5.0], 0.9), 5.0)
        self.assertEqual(_percentile([1.0, 2.0], 0.5), 1.5)

    def test_hours_and_minutes_consistent(self):
        self.assertAlmostEqual(self.report["lead_time_hours_p50"], round(self.report["lead_time_minutes"]["p50"] / 60, 2), places=2)


if __name__ == "__main__":
    unittest.main()
