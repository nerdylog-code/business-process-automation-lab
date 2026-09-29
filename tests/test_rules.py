import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rules import RuleError, cnpj_is_valid, parse_amount, validate_document  # noqa: E402


def doc(**overrides):
    base = {
        "document_number": "NF-10231",
        "cnpj": "11222333000181",
        "amount": "1.234,56",
        "expected_amount": "1.234,56",
        "issued_at": "2026-06-01",
        "due_date": "2026-06-30",
    }
    base.update(overrides)
    return base


class TestRules(unittest.TestCase):
    def test_amount_formats(self):
        self.assertEqual(parse_amount("1.234,56"), 1234.56)
        self.assertEqual(parse_amount("R$ 2.000,00"), 2000.0)
        self.assertEqual(parse_amount(42), 42.0)

    def test_amount_invalid(self):
        with self.assertRaises(RuleError):
            parse_amount("")
        with self.assertRaises(RuleError):
            parse_amount("abc")

    def test_cnpj_checksum(self):
        self.assertTrue(cnpj_is_valid("11.222.333/0001-81"))
        self.assertFalse(cnpj_is_valid("11.222.333/0001-82"))
        self.assertFalse(cnpj_is_valid("11111111111111"))

    def test_clean_document_is_auto_approved(self):
        result = validate_document(doc())
        self.assertEqual(result["status"], "aprovado_automaticamente")
        self.assertFalse(result["needs_human_review"])
        self.assertEqual(result["divergences"], [])

    def test_amount_divergence_goes_to_human(self):
        result = validate_document(doc(expected_amount="1.000,00"))
        self.assertTrue(result["needs_human_review"])
        self.assertIn("valor_divergente", [d["rule"] for d in result["divergences"]])
        self.assertAlmostEqual(result["divergences"][0]["delta"], 234.56, places=2)

    def test_date_and_identifier_rules(self):
        result = validate_document(doc(due_date="2026-05-01", document_number=""))
        rules = {d["rule"] for d in result["divergences"]}
        self.assertIn("data_divergente", rules)
        self.assertIn("identificador_ausente", rules)

    def test_invalid_input_type(self):
        with self.assertRaises(RuleError):
            validate_document(["não é documento"])


if __name__ == "__main__":
    unittest.main()
