"""Impacto da automação em que TODOS os parâmetros vêm de artefato medido.

Sem número mágico: para cada automação, o fator residual (o que continua manual) é **medido**
no próprio lab:

- `extracao_automatica` (substitui a triagem): residual = fração de documentos cujo identificador
  é inválido (esses não podem ser triados sem olho humano) — medido rodando `src.rules` sobre
  `data/documents.csv`.
- `validacao_por_regras` (substitui a conferência manual): residual = 1 - taxa de aprovação
  automática das regras sobre os mesmos documentos.
- `lancamento_automatico` (substitui o lançamento): residual = taxa de casos com divergência
  (casos corrigidos voltam a ser reconferidos após o lançamento) — medido no log.

Além do cenário base, o relatório traz **sensibilidade** (residual -20% / +20%) para mostrar o
intervalo em vez de um número de vitrine.

Uso: python -m src.impact [--log data/event_log.csv] [--documents data/documents.csv] [--out reports/impact.json]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict

from src.mining import load_events
from src.rules import RuleError, validate_document

WORKDAYS_PER_MONTH = 21
HOURS_PER_WORKDAY = 8
AUTOMATION_SCOPE = {
    "extracao_automatica": {"replaces": ["triagem"], "residual_source": "invalid_identifier_share"},
    "validacao_por_regras": {"replaces": ["conferencia_manual"], "residual_source": "human_review_share"},
    "lancamento_automatico": {"replaces": ["lancamento"], "residual_source": "divergence_share"},
}


def measure_residuals(documents_path: str, events: list[dict]) -> dict:
    """Mede no próprio lab as frações que viram fator residual."""
    with open(documents_path, newline="", encoding="utf-8") as fh:
        documents = list(csv.DictReader(fh))

    invalid_identifier = 0
    human_review = 0
    for document in documents:
        try:
            result = validate_document(document)
        except RuleError:
            human_review += 1
            invalid_identifier += 1
            continue
        rules = {d["rule"] for d in result["divergences"]}
        if result["needs_human_review"]:
            human_review += 1
        if "identificador_invalido" in rules or "identificador_ausente" in rules:
            invalid_identifier += 1

    cases = {e["case_id"] for e in events}
    diverging = {e["case_id"] for e in events if e["divergence"]}
    total_documents = max(1, len(documents))
    return {
        "invalid_identifier_share": round(invalid_identifier / total_documents, 4),
        "human_review_share": round(human_review / total_documents, 4),
        "divergence_share": round(len(diverging) / max(1, len(cases)), 4),
        "documents_measured": len(documents),
    }


def simulate(events: list[dict], residuals: dict, cases_per_month: int | None = None,
             sensitivity: float = 0.2) -> dict:
    cases = len({e["case_id"] for e in events})
    cases_per_month = cases if cases_per_month is None else cases_per_month
    scale = cases_per_month / max(1, cases)

    per_activity_minutes: dict[str, int] = defaultdict(int)
    for e in events:
        per_activity_minutes[e["activity"]] += e["duration_minutes"]

    items: list[dict] = []
    total_saved = 0.0
    for name, spec in AUTOMATION_SCOPE.items():
        base = sum(per_activity_minutes.get(a, 0) for a in spec["replaces"])
        measured = residuals[spec["residual_source"]]
        variants = {
            "optimistic": max(0.0, measured * (1 - sensitivity)),
            "measured": measured,
            "pessimistic": min(1.0, measured * (1 + sensitivity)),
        }
        hours = {k: round(base / 60.0 * (1 - v) * scale, 1) for k, v in variants.items()}
        total_saved += hours["measured"]
        items.append({
            "automation": name,
            "replaces_activities": spec["replaces"],
            "baseline_minutes": base,
            "residual_source": spec["residual_source"],
            "residual_measured": measured,
            "hours_saved_per_month": hours,
        })

    total_minutes = sum(per_activity_minutes.values())
    return {
        "basis": {
            "cases_in_log": cases,
            "cases_per_month_assumed": cases_per_month,
            "workdays_per_month": WORKDAYS_PER_MONTH,
            "hours_per_workday": HOURS_PER_WORKDAY,
            "note": "simulação sobre log e documentos sintéticos do próprio lab; não é resultado corporativo",
        },
        "residuals_measured": residuals,
        "automations": items,
        "consolidated": {
            "hours_saved_per_month": round(total_saved, 1),
            "hours_saved_per_month_optimistic": round(sum(i["hours_saved_per_month"]["optimistic"] for i in items), 1),
            "hours_saved_per_month_pessimistic": round(sum(i["hours_saved_per_month"]["pessimistic"] for i in items), 1),
            "workdays_saved_per_month": round(total_saved / HOURS_PER_WORKDAY, 1),
            "hours_saved_per_year": round(total_saved * 12, 1),
            "manual_hours_before": round(total_minutes / 60.0 * scale, 1),
            "manual_hours_after": round(total_minutes / 60.0 * scale - total_saved, 1),
        },
        "formula": ("horas_economizadas = soma(minutos das atividades cobertas)/60 * "
                    "(1 - residual medido) * (casos_por_mes / casos_no_log)"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", default="data/event_log.csv")
    parser.add_argument("--documents", default="data/documents.csv")
    parser.add_argument("--out", default="reports/impact.json")
    parser.add_argument("--cases-per-month", type=int, default=None)
    parser.add_argument("--sensitivity", type=float, default=0.2)
    args = parser.parse_args()
    events = load_events(args.log)
    residuals = measure_residuals(args.documents, events)
    report = simulate(events, residuals, args.cases_per_month, args.sensitivity)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    c = report["consolidated"]
    print(f"impacto: {c['hours_saved_per_month']}h/mês medidas "
          f"(faixa {c['hours_saved_per_month_optimistic']}–{c['hours_saved_per_month_pessimistic']}h) "
          f"| residuals medidos: {residuals} -> {args.out}")


if __name__ == "__main__":
    main()
