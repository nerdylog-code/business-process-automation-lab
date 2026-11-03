"""Valida os artefatos low-code (n8n importável + receita Power Automate)."""
import json
import os
import pathlib
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N8N = pathlib.Path(ROOT) / "flows" / "n8n_process_automation.json"
PA = pathlib.Path(ROOT) / "flows" / "power_automate_recipe.md"


class TestFlows(unittest.TestCase):
    def setUp(self):
        self.wf = json.loads(N8N.read_text(encoding="utf-8"))

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
        self.assertIn("/automate/validate", json.dumps(self.wf), "o fluxo precisa chamar a API deste repo")

    def test_flow_handles_failure(self):
        """Fluxo sem retry/DLQ é brinquedo: falha de integração precisa ter caminho próprio."""
        http_nodes = [n for n in self.wf["nodes"] if n["type"].endswith("httpRequest")]
        self.assertTrue(http_nodes)
        self.assertTrue(any(n.get("retryOnFail") for n in http_nodes), "chamada HTTP precisa de retry")
        self.assertTrue(any(n.get("onError") for n in http_nodes), "erro precisa de política explícita")
        error_targets = {
            link["node"]
            for source, outputs in self.wf["connections"].items()
            if "erro" in source.lower()
            for branch in outputs.get("main", [])
            for link in branch
        }
        self.assertTrue(error_targets, "o caminho de erro precisa terminar em alerta/registro")

    def test_flow_has_no_credential_placeholder(self):
        raw = json.dumps(self.wf)
        for forbidden in ("SEU_TOKEN", "CHANGE_ME", "TODO", "password"):
            self.assertNotIn(forbidden, raw)

    def test_power_automate_recipe_documents_the_contract(self):
        text = PA.read_text(encoding="utf-8")
        for expected in ("Parse JSON", "HTTP", "Aplicar a cada", "Excel", "needs_human_review", "Limitações"):
            self.assertIn(expected, text)
        self.assertIn("sem licença", text.lower())
        self.assertIn("executar após", text.lower(), "receita precisa documentar o tratamento de erro")

    def test_service_app_exposes_documented_routes(self):
        """Fonte única: as rotas vêm do FastAPI, não de um YAML mantido à mão."""
        try:
            from fastapi.testclient import TestClient  # noqa: PLC0415
            from src.automation_service import app  # noqa: PLC0415
        except Exception:
            self.skipTest("fastapi não instalado (extras .api)")
        documented = set(app.openapi()["paths"])
        for route in ("/automate/validate", "/automate/batch", "/process/kpis", "/healthz"):
            self.assertIn(route, documented)
        self.assertEqual(TestClient(app).get("/healthz").status_code, 200)

    def test_documented_http_route_exists_in_the_app(self):
        """A receita Power Automate não pode apontar para rota que não existe.

        Foi exatamente assim que o `/work` (rota de outro projeto) sobreviveu numa
        revisão anterior: o teste antigo só procurava palavras-chave no markdown.
        """
        try:
            from src.automation_service import app
        except Exception:  # fastapi ausente: o núcleo continua sem dependência
            self.skipTest("fastapi não instalado")
        paths = {route.path for route in app.routes if getattr(route, "path", None)}
        texto = PA.read_text(encoding="utf-8")
        citadas = set(re.findall(r"/(?:automate|process)/[a-z]+", texto))
        self.assertTrue(citadas, "a receita deveria citar ao menos uma rota da API")
        for rota in citadas:
            self.assertIn(rota, paths, f"a receita cita {rota}, que não existe no app")
        for proibida in ("/work", "make run", "test_n8n_flow"):
            self.assertNotIn(proibida, texto, f"referência a {proibida} (de outro projeto) voltou à receita")

    def test_openapi_spec_is_generated_from_the_app(self):
        spec = pathlib.Path(ROOT) / "api" / "openapi.json"
        if not spec.exists():
            self.skipTest("rode `make openapi` para gerar o spec")
        documentado = json.loads(spec.read_text(encoding="utf-8"))
        try:
            from src.automation_service import app
        except Exception:
            self.skipTest("fastapi não instalado")
        self.assertEqual(set(documentado["paths"]), set(app.openapi()["paths"]))

if __name__ == "__main__":
    unittest.main()

