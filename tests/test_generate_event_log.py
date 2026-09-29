import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.generate_event_log import generate, write_csv  # noqa: E402


class TestEventLog(unittest.TestCase):
    def test_determinism(self):
        a = generate(cases=12, seed=42)
        b = generate(cases=12, seed=42)
        self.assertEqual(a, b, "o log precisa ser determinístico com a mesma seed")

    def test_structure(self):
        rows = generate(cases=20, seed=7)
        self.assertTrue(rows)
        for row in rows:
            self.assertIn(row["activity"], {
                "recebimento", "triagem", "conferencia_manual", "correcao", "aprovacao", "lancamento"
            })
            self.assertGreater(row["duration_minutes"], 0)
            self.assertTrue(row["case_id"].startswith("DOC-"))

    def test_rework_creates_correction(self):
        rows = generate(cases=60, seed=3)
        cases_with_correction = {r["case_id"] for r in rows if r["activity"] == "correcao"}
        self.assertTrue(cases_with_correction, "esperado pelo menos um caso com retrabalho")
        for case_id in cases_with_correction:
            acts = [r["activity"] for r in rows if r["case_id"] == case_id]
            self.assertIn("conferencia_manual", acts[acts.index("correcao") + 1:],
                          "após a correção o caso deve voltar para conferência")

    def test_write_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "nested", "event_log.csv")
            write_csv(generate(cases=5, seed=1), path)
            self.assertTrue(os.path.exists(path))
            with open(path, encoding="utf-8") as fh:
                self.assertIn("case_id,activity", fh.readline())


if __name__ == "__main__":
    unittest.main()
