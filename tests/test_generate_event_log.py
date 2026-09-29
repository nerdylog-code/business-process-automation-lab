import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.generate_event_log import ACTIVITIES, generate, write_csv  # noqa: E402


class TestEventLog(unittest.TestCase):
    def test_determinism_same_seed(self):
        a_events, a_docs = generate(cases=12, seed=42)
        b_events, b_docs = generate(cases=12, seed=42)
        self.assertEqual(a_events, b_events)
        self.assertEqual(a_docs, b_docs)

    def test_different_seed_changes_data(self):
        a, _ = generate(cases=12, seed=42)
        b, _ = generate(cases=12, seed=43)
        self.assertNotEqual(a, b, "seed diferente deve produzir log diferente")

    def test_structure_and_invariants(self):
        events, documents = generate(cases=20, seed=7)
        self.assertEqual(len({e["case_id"] for e in events}), 20)
        self.assertEqual(len(documents), 20)
        for row in events:
            self.assertIn(row["activity"], ACTIVITIES)
            self.assertGreater(row["duration_minutes"], 0)
            self.assertGreater(row["wait_minutes"], 0)
            self.assertTrue(row["actor"])
        for row in events:
            self.assertIn(row["divergence"], ("", "valor_divergente", "identificador_invalido", "data_divergente"))

    def test_rework_path_present_but_not_in_every_case(self):
        events, _ = generate(cases=80, seed=42)
        cases_with_rework = {e["case_id"] for e in events if e["rework"]}
        cases = {e["case_id"] for e in events}
        self.assertTrue(cases_with_rework, "o processo sintético precisa ter retrabalho")
        self.assertLess(len(cases_with_rework), len(cases), "retrabalho não pode ser 100% dos casos")

    def test_every_case_has_lancamento(self):
        events, _ = generate(cases=30, seed=11)
        ended = {e["case_id"] for e in events if e["activity"] == "lancamento"}
        self.assertEqual(len(ended), 30)

    def test_documents_match_divergence_flags(self):
        """Documento limpo no log => documento limpo no CSV (coerência entre as duas saídas)."""
        events, documents = generate(cases=40, seed=5)
        diverging = {e["case_id"] for e in events if e["divergence"]}
        for index, document in enumerate(documents):
            case_id = f"DOC-{1000 + index}"
            if case_id in diverging:
                self.assertTrue(document["divergence"], f"{case_id} deveria ter divergência")
            else:
                self.assertFalse(document["divergence"], f"{case_id} deveria ser limpo")

    def test_write_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            events, documents = generate(cases=5, seed=1)
            path = os.path.join(tmp, "log.csv")
            docs_path = os.path.join(tmp, "docs.csv")
            write_csv(events, path)
            write_csv(documents, docs_path)
            self.assertTrue(os.path.getsize(path) > 0)
            with open(path, encoding="utf-8") as fh:
                header = fh.readline().strip()
            self.assertIn("case_id", header)
            self.assertIn("duration_minutes", header)


if __name__ == "__main__":
    unittest.main()
