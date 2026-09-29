"""Valida os artefatos low-code (n8n importável + receita Power Automate)."""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N8N = os.path.join(ROOT, "flows/n8n_process_automation.json")
PA = os.path.join(ROOT, "flows/power_automate_recipe.md")
OPENAPI = os.path.join(ROOT, "api/openapi.yaml")


class TestFlows(unittest.TestCase):
    def setUp(self):
        with open(N8N, encoding="utf-8") as fh:
            self.wf = json.load(fh)

    def test_n8n_importable_shape(self):
        self.assertIn("nodes", self.wf)
        self.assertIn("connections", self.wf)
        self.assertTrue(self.wf["nodes"])
        names = []
        for node in self.wf["nodes"]:
            for key in ("parameters", "id", "name", "type", "typeVersion", "position"):
                self.assertIn(key, node, f"nó sem {key}: {node.get('name')}")
            self.assertTrue(node["type"].startswith("n8n-nodes-base."))
            self.assertEqual(len(node["position"]), 2)
            names.append(node["name"])
        self.assertEqual(len(names), len(set(names)), "nomes de nós duplicados")

    def test_connections_reference_existing_nodes(self):
        names = {n["name"] for n in self.wf["nodes"]}
        for source, outputs in self.wf["connections"].items():
            self.assertIn(source, names)
            for branch in outputs.get("main", []):
                for link in branch:
                    self.assertIn(link["node"], names)

    def test_flow_contains_required_steps(self):
        types = [n["type"] for n in self.wf["nodes"]]
        for required in ("n8n-nodes-base.webhook", "n8n-nodes-base.httpRequest", "n8n-nodes-base.if"):
            self.assertIn(required, types)
        urls = json.dumps(self.wf)
        self.assertIn("/automate/validate", urls, "o fluxo precisa chamar a API do lab")

    def test_power_automate_recipe_documents_the_contract(self):
        with open(PA, encoding="utf-8") as fh:
            text = fh.read()
        for expected in ("Parse JSON", "HTTP", "Apply to each", "Excel", "needs_human_review", "Limitações"):
            self.assertIn(expected, text)
        self.assertIn("sem tenant", text.lower())

    def test_openapi_matches_service_routes(self):
        with open(OPENAPI, encoding="utf-8") as fh:
            spec = fh.read()
        for route in ("/automate/validate", "/automate/batch", "/process/kpis", "/healthz"):
            self.assertIn(route, spec)


if __name__ == "__main__":
    unittest.main()
