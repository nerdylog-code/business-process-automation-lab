"""Gera um log de eventos sintético e determinístico de um processo administrativo/fiscal.

Processo modelado (AS-IS):
  recebimento -> triagem -> conferencia_manual -> [correcao -> conferencia_manual]
              -> aprovacao -> lancamento

Determinismo: seed fixa (42). Nenhum dado real.
Uso: python -m src.generate_event_log [--cases N] [--out data/event_log.csv]
"""
from __future__ import annotations

import argparse
import csv
import os
import random
from datetime import datetime, timedelta

ACTIVITIES = [
    "recebimento",
    "triagem",
    "conferencia_manual",
    "correcao",
    "aprovacao",
    "lancamento",
]
ACTORS = {
    "recebimento": ["sistema_portal"],
    "triagem": ["ana.souza", "bruno.lima"],
    "conferencia_manual": ["carla.mendes", "diego.rocha", "elisa.prado"],
    "correcao": ["carla.mendes", "diego.rocha"],
    "aprovacao": ["gerente.fiscal"],
    "lancamento": ["ana.souza", "sistema_erp"],
}
BASE_MINUTES = {  # mediana observada no cenário sintético (minutos)
    "recebimento": 6,
    "triagem": 12,
    "conferencia_manual": 38,
    "correcao": 25,
    "aprovacao": 9,
    "lancamento": 14,
}


def _duration_minutes(activity: str, rng: random.Random) -> int:
    base = BASE_MINUTES[activity]
    return max(1, int(rng.gauss(base, base * 0.35)))


def generate(cases: int = 220, seed: int = 42, start: datetime | None = None):
    rng = random.Random(seed)
    start = start or datetime(2026, 6, 1, 8, 0, 0)
    rows = []
    for c in range(cases):
        case_id = f"DOC-{1000 + c}"
        rng.seed(seed + c)  # determinístico por caso
        clock = start + timedelta(minutes=int(rng.uniform(0, 60 * 24 * 45)))
        sequence = ["recebimento", "triagem", "conferencia_manual"]
        # 32% dos casos entram em retrabalho (divergência achada na conferência)
        rework = rng.random() < 0.32
        if rework:
            sequence += ["correcao", "conferencia_manual"]
        sequence += ["aprovacao", "lancamento"]

        divergence = ""
        if rework:
            divergence = rng.choice(["valor_divergente", "data_divergente", "identificador_invalido"])

        for activity in sequence:
            dur = _duration_minutes(activity, rng)
            wait = max(1, int(rng.gauss(dur * 0.6, dur * 0.4)))
            clock = clock + timedelta(minutes=wait)
            actor = rng.choice(ACTORS[activity])
            rows.append(
                {
                    "case_id": case_id,
                    "activity": activity,
                    "actor": actor,
                    "timestamp_start": clock.strftime("%Y-%m-%dT%H:%M:%S"),
                    "duration_minutes": dur,
                    "wait_minutes": wait,
                    "rework": int(activity == "correcao"),
                    "divergence": divergence if activity == "conferencia_manual" else "",
                    "automated": 0,
                }
            )
            clock = clock + timedelta(minutes=dur)
    return rows


def write_csv(rows, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fields = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=220)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="data/event_log.csv")
    args = parser.parse_args()
    rows = generate(args.cases, args.seed)
    write_csv(rows, args.out)
    print(f"event log: {len(rows)} eventos, {args.cases} casos -> {args.out}")


if __name__ == "__main__":
    main()
