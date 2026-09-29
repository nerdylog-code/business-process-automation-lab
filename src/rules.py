"""Regras de negócio determinísticas usadas pela automação e pela simulação.

São regras de conferência documental (valor, data, identificador) aplicadas sobre um
documento sintético. Servem tanto para o serviço HTTP quanto para o impacto estimado.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any


class RuleError(ValueError):
    """Erro de validação de entrada."""


def parse_amount(value: Any) -> float:
    """Converte '1.234,56' ou 1234.56 em float. Levanta RuleError em formato inválido."""
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    if not isinstance(value, str) or not value.strip():
        raise RuleError("valor ausente")
    cleaned = value.strip().replace("R$", "").replace(" ", "")
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return round(float(cleaned), 2)
    except ValueError as exc:  # pragma: no cover - caminho de erro
        raise RuleError(f"valor inválido: {value!r}") from exc


def cnpj_is_valid(cnpj: str) -> bool:
    """Validação de dígitos verificadores do CNPJ (usar apenas com números sintéticos)."""
    digits = "".join(ch for ch in (cnpj or "") if ch.isdigit())
    if len(digits) != 14 or len(set(digits)) == 1:
        return False
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights2 = [6] + weights1
    for weights, pos in ((weights1, 12), (weights2, 13)):
        total = sum(int(d) * w for d, w in zip(digits[:pos], weights))
        check = 11 - (total % 11)
        check = 0 if check >= 10 else check
        if check != int(digits[pos]):
            return False
    return True


def parse_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    raise RuleError(f"data inválida: {value!r}")


def validate_document(document: dict) -> dict:
    """Aplica o conjunto de regras e devolve resultado estruturado + divergências."""
    if not isinstance(document, dict):
        raise RuleError("documento deve ser um objeto")

    divergences: list[dict] = []
    normalized: dict[str, Any] = {}

    normalized["amount"] = parse_amount(document.get("amount", ""))
    normalized["document_number"] = str(document.get("document_number", "")).strip()
    normalized["cnpj"] = "".join(ch for ch in str(document.get("cnpj", "")) if ch.isdigit())
    normalized["issued_at"] = parse_date(document.get("issued_at", ""))
    normalized["due_date"] = parse_date(document.get("due_date", ""))

    expected = document.get("expected_amount")
    if expected not in (None, ""):
        expected_value = parse_amount(expected)
        delta = round(normalized["amount"] - expected_value, 2)
        if abs(delta) > 0.01:
            divergences.append({"rule": "valor_divergente", "delta": delta})

    if not normalized["document_number"]:
        divergences.append({"rule": "identificador_ausente"})
    elif not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/\-]{2,}", normalized["document_number"]):
        divergences.append({"rule": "identificador_invalido"})

    if not cnpj_is_valid(normalized["cnpj"]):
        divergences.append({"rule": "identificador_invalido"})

    if normalized["due_date"] < normalized["issued_at"]:
        divergences.append({"rule": "data_divergente"})

    needs_human = bool(divergences)
    return {
        "status": "revisao_humana" if needs_human else "aprovado_automaticamente",
        "needs_human_review": needs_human,
        "divergences": divergences,
        "normalized": {k: (v.isoformat() if isinstance(v, date) else v) for k, v in normalized.items()},
    }
