"""Testes da API. Pulados quando fastapi/pydantic não estão instalados."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:  # noqa: SIM105
    from fastapi.testclient import TestClient  # type: ignore
    HAVE_FASTAPI = True
except Exception:  # pragma: no cover
    HAVE_FASTAPI = False


@unittest.skipUnless(HAVE_FASTAPI, "fastapi não instalado (pip install -r requirements.txt)")
class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.automation_service import app  # noqa: PLC0415

        cls.client = TestClient(app)

    def test_healthz(self):
        self.assertEqual(self.client.get("/healthz").json(), {"status": "ok"})

    def test_validate_ok(self):
        payload = {
            "document_number": "NF-1", "cnpj": "11222333000181", "amount": "1.234,56",
            "expected_amount": "1.234,56", "issued_at": "2026-06-01", "due_date": "2026-06-30",
        }
        body = self.client.post("/automate/validate", json=payload).json()
        self.assertEqual(body["status"], "aprovado_automaticamente")

    def test_validate_divergence(self):
        payload = {
            "document_number": "NF-2", "cnpj": "11222333000181", "amount": "1.300,00",
            "expected_amount": "1.234,56", "issued_at": "2026-06-01", "due_date": "2026-06-30",
        }
        body = self.client.post("/automate/validate", json=payload).json()
        self.assertTrue(body["needs_human_review"])

    def test_batch_summary(self):
        docs = [{
            "document_number": f"NF-{i}", "cnpj": "11222333000181", "amount": "1.234,56",
            "expected_amount": "1.234,56", "issued_at": "2026-06-01", "due_date": "2026-06-30",
        } for i in range(4)]
        body = self.client.post("/automate/batch", json={"documents": docs}).json()
        self.assertEqual(body["total"], 4)
        self.assertEqual(body["approved_automatically"], 4)
        self.assertEqual(body["automation_rate"], 1.0)

    def test_kpis_requires_pipeline(self):
        response = self.client.get("/process/kpis")
        self.assertIn(response.status_code, (200, 404))


if __name__ == "__main__":
    unittest.main()
