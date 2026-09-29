"""Teste ponta a ponta: log -> mining -> bpmn -> impacto -> relatório."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


class TestPipeline(unittest.TestCase):
    def test_make_all_via_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ)
            env["PYTHONPATH"] = ROOT
            steps = [
                [sys.executable, "-m", "src.generate_event_log", "--cases", "40", "--out", os.path.join(tmp, "data/event_log.csv")],
                [sys.executable, "-m", "src.mining", "--log", os.path.join(tmp, "data/event_log.csv"), "--out", os.path.join(tmp, "reports/mining.json")],
                [sys.executable, "-m", "src.bpmn", "--outdir", os.path.join(tmp, "bpmn"), "--mining", os.path.join(tmp, "reports/mining.json")],
                [sys.executable, "-m", "src.impact", "--log", os.path.join(tmp, "data/event_log.csv"), "--out", os.path.join(tmp, "reports/impact.json")],
                [sys.executable, "-m", "src.report", "--mining", os.path.join(tmp, "reports/mining.json"),
                 "--impact", os.path.join(tmp, "reports/impact.json"), "--out", os.path.join(tmp, "dashboard/process_report.html")],
            ]
            for cmd in steps:
                proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, f"{cmd}: {proc.stderr}")
            for rel in ("data/event_log.csv", "reports/mining.json", "bpmn/as_is.bpmn",
                        "bpmn/to_be.bpmn", "reports/impact.json", "dashboard/process_report.html"):
                self.assertTrue(os.path.exists(os.path.join(tmp, rel)), f"faltou {rel}")
            with open(os.path.join(tmp, "reports/mining.json"), encoding="utf-8") as fh:
                mining = json.load(fh)
            self.assertEqual(mining["cases"], 40)
            with open(os.path.join(tmp, "dashboard/process_report.html"), encoding="utf-8") as fh:
                html = fh.read()
            self.assertIn("simulação", html.lower())
            self.assertIn("lead time P50", html)


if __name__ == "__main__":
    unittest.main()
