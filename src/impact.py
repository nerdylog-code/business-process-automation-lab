"""Simulação de impacto da automação, com fórmula explícita.

fórmula:
  minutos_automatizados = soma(duration_minutes das atividades cobertas pela automação)
  horas_economizadas_mes = minutos_automatizados / 60 * (1 - fator_residual) * escala_para_1_mes
  fator_residual = fração do trabalho que continua manual (exceções e conferência humana)

Nada aqui é métrica corporativa: a base é o log sintético.
Uso: python -m src.impact [--log data/event_log.csv] [--out reports/impact.json]
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict

from src.mining import load_events

AUTOMATION_SCOPE = {
    "extracao_automatica": {"replaces": ["triagem"], "residual": 0.15},
    "validacao_por_regras": {"replaces": ["conferencia_manual"], "residual": 0.55},
    "lancamento_automatico": {"replaces": ["lancamento"], "residual": 0.10},
}
WORKDAYS_PER_MONTH = 21
HOURS_PER_WORKDAY = 8


def simulate(events: list[dict], cases_per_month: int | None = None) -> dict:
    cases = len({e["case_id"] for e in events})
    per_activity_minutes: dict[str, int] = defaultdict(int)
    for e in events:
        per_activity_minutes[e["activity"]] += e["duration_minutes"]

    if cases_per_month is None:
        cases_per_month = cases  # o log cobre ~1,5 mês; usamos o próprio volume como base mensal

    scale = cases_per_month / max(1, cases)
    items = []
    total_saved = 0.0
    for name, spec in AUTOMATION_SCOPE.items():
        base = sum(per_activity_minutes.get(a, 0) for a in spec["replaces"])
        saved = base / 60.0 * (1 - spec["residual"]) * scale
        total_saved += saved
        items.append(
            {
                "automation": name,
                "replaces_activities": spec["replaces"],
                "baseline_minutes": base,
                "residual_manual_fraction": spec["residual"],
                "hours_saved_per_month": round(saved, 1),
            }
        )

    return {
        "basis": {
            "cases_in_log": cases,
            "cases_per_month_assumed": cases_per_month,
            "workdays_per_month": WORKDAYS_PER_MONTH,
            "hours_per_workday": HOURS_PER_WORKDAY,
            "note": "simulação sobre log sintético; não é resultado de operação corporativa",
        },
        "automations": items,
        "consolidated": {
            "hours_saved_per_month": round(total_saved, 1),
            "workdays_saved_per_month": round(total_saved / HOURS_PER_WORKDAY, 1),
            "hours_saved_per_year": round(total_saved * 12, 1),
            "min_minutes_after_automation": round(
                sum(per_activity_minutes.values()) / 60.0 * scale - total_saved, 1
            ),
        },
        "formula": (
            "horas_economizadas = soma(minutos_das_atividades_cobertas)/60 * (1 - fator_residual) "
            "* (casos_por_mes / casos_no_log)"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", default="data/event_log.csv")
    parser.add_argument("--out", default="reports/impact.json")
    parser.add_argument("--cases-per-month", type=int, default=None)
    args = parser.parse_args()
    report = simulate(load_events(args.log), args.cases_per_month)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    c = report["consolidated"]
    print(f"impacto (simulado): {c['hours_saved_per_month']}h/mês ({c['workdays_saved_per_month']} dias úteis) -> {args.out}")


if __name__ == "__main__":
    main()
