"""Gera um log de eventos sintético e determinístico de um processo administrativo/fiscal.

Processo modelado (AS-IS):
  recebimento -> triagem -> conferencia_manual -> [correcao -> conferencia_manual]
              -> aprovacao -> lancamento

Determinismo: seed fixa (42). Nenhum dado real.
Também emite os documentos sintéticos correspondentes (`data/documents.csv`), que a engine de
regras usa para MEDIR a fração de casos que continua exigindo humano — em vez de estimar.
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
BASE_MINUTES = {  # mediana do cenário sintético (minutos)
    "recebimento": 6,
    "triagem": 12,
    "conferencia_manual": 38,
    "correcao": 25,
    "aprovacao": 9,
    "lancamento": 14,
}
DIVERGENCE_KINDS = ("valor_divergente", "identificador_invalido", "data_divergente")
VALID_CNPJ = "11222333000181"
INVALID_CNPJ = "11222333000182"


def _duration_minutes(activity: str, rng: random.Random) -> int:
    base = BASE_MINUTES[activity]
    return max(1, int(rng.gauss(base, base * 0.35)))


def _document_for(case_index: int, divergence: str, rng: random.Random) -> dict:
    """Documento sintético coerente com o desfecho do caso no log.

    Sem divergência => documento limpo (deve ser aprovado pelas regras).
    Com divergência => o defeito indicado é injetado (deve cair em revisão humana).
    """
    expected = round(rng.uniform(120.0, 9000.0), 2)
    amount = expected
    cnpj = VALID_CNPJ
    issued = "2026-06-01"
    due = "2026-06-30"
    if divergence == "valor_divergente":
        amount = round(expected + rng.choice([-1, 1]) * rng.uniform(1.0, 400.0), 2)
    elif divergence == "identificador_invalido":
        cnpj = INVALID_CNPJ
    elif divergence == "data_divergente":
        due = "2026-05-01"
    return {
        "document_number": f"NF-{20000 + case_index}",
        "cnpj": cnpj,
        "amount": f"{amount:.2f}",
        "expected_amount": f"{expected:.2f}",
        "issued_at": issued,
        "due_date": due,
        "divergence": divergence,
    }


def generate(cases: int = 220, seed: int = 42, start: datetime | None = None, rework_rate: float = 0.32):
    """Gera (eventos, documentos). Ambos determinísticos para a mesma seed."""
    rng = random.Random(seed)
    start = start or datetime(2026, 6, 1, 8, 0, 0)
    rows: list[dict] = []
    documents: list[dict] = []
    for c in range(cases):
        case_id = f"DOC-{1000 + c}"
        rng.seed(seed + c)  # determinístico por caso
        clock = start + timedelta(minutes=int(rng.uniform(0, 60 * 24 * 45)))
        sequence = ["recebimento", "triagem", "conferencia_manual"]
        rework = rng.random() < rework_rate
        divergence = rng.choice(DIVERGENCE_KINDS) if rework else ""
        if rework:
            sequence += ["correcao", "conferencia_manual"]
        sequence += ["aprovacao", "lancamento"]

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

        documents.append(_document_for(1000 + c, divergence, rng))
    return rows, documents


def write_csv(rows: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fields = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=220)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rework-rate", type=float, default=0.32)
    parser.add_argument("--out", default="data/event_log.csv")
    parser.add_argument("--documents-out", default="data/documents.csv")
    args = parser.parse_args()
    rows, documents = generate(args.cases, args.seed, rework_rate=args.rework_rate)
    write_csv(rows, args.out)
    write_csv(documents, args.documents_out)
    print(f"event log: {len(rows)} eventos, {args.cases} casos -> {args.out}")
    print(f"documents: {len(documents)} documentos sintéticos -> {args.documents_out}")


if __name__ == "__main__":
    main()
