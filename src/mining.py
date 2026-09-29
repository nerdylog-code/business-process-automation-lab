"""Process mining de verdade sobre o log de eventos: descoberta por DFG + conformance.

O que este módulo faz (e o que NÃO faz, para não vender fumaça):

Faz
- **Descoberta (discovery)**: grafo de directly-follows (DFG) com contagem e probabilidade por aresta,
  atividades de início/fim, variantes ordenadas, retrabalho, lead time e throughput.
- **Conformance**: fitness DFG-based (cobertura de arestas log↔modelo) e *trace fitness*
  (fração de casos cuja trajetória é um caminho válido no DFG, começando e terminando nas atividades certas).

Não faz
- Alinhamento ótimo (A* / token replay em rede de Petri) nem descoberta indutiva (Inductive Miner,
  Split Miner). O DFG é um modelo de *ordem direta*: bom para gargalo, variante e fitness; não
  substitui uma rede com semântica de concorrência. Dito isso, todo número aqui vem do log — nada é fixado a priori.

Uso: python -m src.mining [--log data/event_log.csv] [--out reports/mining.json] [--dfg-out reports/dfg.json]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta

MIN_EDGE_SUPPORT = 3          # aresta precisa aparecer em >= 3 casos para entrar no modelo descoberto
MIN_EDGE_PROBABILITY = 0.05   # ... e em >= 5% dos casos (corta ruído de exceção)


def load_events(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["duration_minutes"] = int(r["duration_minutes"])
        r["wait_minutes"] = int(r["wait_minutes"])
        r["rework"] = int(r["rework"])
        r["automated"] = int(r.get("automated") or 0)
        r["timestamp_start"] = datetime.fromisoformat(r["timestamp_start"])
    return rows


def normalize_events(events: list[dict]) -> list[dict]:
    """Aceita eventos crus (CSV: strings) ou já carregados (datetime) — sem quebrar quem chama."""
    normalized: list[dict] = []
    for event in events:
        item = dict(event)
        if isinstance(item.get("timestamp_start"), str):
            item["timestamp_start"] = datetime.fromisoformat(item["timestamp_start"])
        for field in ("duration_minutes", "wait_minutes", "rework", "automated"):
            if field in item and item[field] is not None and not isinstance(item[field], int):
                item[field] = int(item[field])
        normalized.append(item)
    return normalized


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    lower, upper = int(k), min(int(k) + 1, len(ordered) - 1)
    if lower == upper:
        return float(ordered[lower])
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * (k - lower))


def traces_by_case(events: list[dict]) -> dict[str, list[str]]:
    events = normalize_events(events)
    by_case: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        by_case[e["case_id"]].append(e)
    return {cid: [e["activity"] for e in sorted(evs, key=lambda x: x["timestamp_start"])] for cid, evs in by_case.items()}


def discover_dfg(traces: dict[str, list[str]]) -> dict:
    """Grafo de directly-follows + extremos. Base do modelo descoberto."""
    edges: Counter = Counter()
    edge_cases: dict[tuple[str, str], set[str]] = defaultdict(set)
    starts: Counter = Counter()
    ends: Counter = Counter()
    for case_id, trace in traces.items():
        if not trace:
            continue
        starts[trace[0]] += 1
        ends[trace[-1]] += 1
        for a, b in zip(trace, trace[1:]):
            edges[(a, b)] += 1
            edge_cases[(a, b)].add(case_id)
    total = sum(edges.values())
    nodes = sorted({a for a, _ in edges} | {b for _, b in edges} | set(starts) | set(ends))
    return {
        "nodes": nodes,
        "edges": [
            {
                "source": a,
                "target": b,
                "count": count,
                "cases": len(edge_cases[(a, b)]),
                "probability": round(count / total, 4) if total else 0.0,
            }
            for (a, b), count in sorted(edges.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "start_activities": [{"activity": a, "count": c, "probability": round(c / max(1, len(traces)), 4)}
                             for a, c in starts.most_common()],
        "end_activities": [{"activity": a, "count": c, "probability": round(c / max(1, len(traces)), 4)}
                           for a, c in ends.most_common()],
    }


def accept_edges(dfg: dict, min_support: int = MIN_EDGE_SUPPORT, min_probability: float = MIN_EDGE_PROBABILITY) -> dict:
    """Filtra arestas para o modelo descoberto (corta ruído sem inventar processo)."""
    kept = [e for e in dfg["edges"] if e["cases"] >= min_support and e["probability"] >= min_probability]
    if not kept:  # fallback: mantém a espinha dorsal (as mais frequentes)
        kept = dfg["edges"][: max(3, len(dfg["edges"]) // 4)]
    return {
        "nodes": sorted({e["source"] for e in kept} | {e["target"] for e in kept}),
        "edges": kept,
        "start_activities": dfg["start_activities"],
        "end_activities": dfg["end_activities"],
        "filter": {"min_support_cases": min_support, "min_probability": min_probability},
    }


def conformance(traces: dict[str, list[str]], model: dict) -> dict:
    """Fitness DFG-based + trace fitness (caminho válido no modelo)."""
    model_edges = {(e["source"], e["target"]) for e in model["edges"]}
    log_edges: set[tuple[str, str]] = set()
    for trace in traces.values():
        log_edges |= set(zip(trace, trace[1:]))
    starts = {s["activity"] for s in model["start_activities"][:1]} or {s["activity"] for s in model["start_activities"]}
    ends = {e["activity"] for e in model["end_activities"][:1]} or {e["activity"] for e in model["end_activities"]}

    covered = log_edges & model_edges
    valid_cases = 0
    deviating: list[dict] = []
    for case_id, trace in traces.items():
        if not trace:
            continue
        ok = all((a, b) in model_edges for a, b in zip(trace, trace[1:]))
        ok = ok and trace[0] in starts and trace[-1] in ends
        if ok:
            valid_cases += 1
        else:
            missing = [f"{a}->{b}" for a, b in zip(trace, trace[1:]) if (a, b) not in model_edges]
            deviating.append({"case_id": case_id, "missing_edges": missing[:4]})

    return {
        "fitness_log_to_model": round(len(covered) / max(1, len(log_edges)), 4),
        "model_edge_coverage": round(len(covered) / max(1, len(model_edges)), 4),
        "trace_fitness": round(valid_cases / max(1, len(traces)), 4),
        "deviating_cases": len(deviating),
        "deviating_examples": deviating[:5],
        "method": "DFG-based (cobertura de arestas + caminho válido). Não é alinhamento ótimo.",
    }


def analyze(events: list[dict]) -> dict:
    events = normalize_events(events)
    traces = traces_by_case(events)
    by_case: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        by_case[e["case_id"]].append(e)

    lead_times: list[float] = []
    variant_counter: Counter = Counter()
    rework_cases = 0
    weeks: Counter = Counter()
    for case_id, evs in by_case.items():
        evs.sort(key=lambda x: x["timestamp_start"])
        start = evs[0]["timestamp_start"]
        end = evs[-1]["timestamp_start"] + timedelta(minutes=evs[-1]["duration_minutes"])
        lead_times.append((end - start).total_seconds() / 60.0)
        variant_counter[" -> ".join(e["activity"] for e in evs)] += 1
        if any(e["rework"] for e in evs):
            rework_cases += 1
        iso = end.isocalendar()
        weeks[f"{iso.year}-W{iso.week:02d}"] += 1

    per_activity: dict[str, dict] = {}
    for activity in sorted({e["activity"] for e in events}):
        items = [e for e in events if e["activity"] == activity]
        per_activity[activity] = {
            "events": len(items),
            "cases": len({i["case_id"] for i in items}),
            "avg_duration_minutes": round(statistics.fmean(i["duration_minutes"] for i in items), 2),
            "avg_wait_minutes": round(statistics.fmean(i["wait_minutes"] for i in items), 2),
            "total_minutes": sum(i["duration_minutes"] for i in items),
        }

    dfg = discover_dfg(traces)
    model = accept_edges(dfg)
    conf = conformance(traces, model)
    bottleneck = max(per_activity.items(), key=lambda kv: kv[1]["avg_wait_minutes"])[0]

    return {
        "cases": len(by_case),
        "events": len(events),
        "lead_time_minutes": {
            "mean": round(statistics.fmean(lead_times), 2),
            "p50": round(_percentile(lead_times, 0.5), 2),
            "p90": round(_percentile(lead_times, 0.9), 2),
            "max": round(max(lead_times), 2),
        },
        "lead_time_hours_p50": round(_percentile(lead_times, 0.5) / 60.0, 2),
        "throughput_cases_per_week": dict(sorted(weeks.items())[-6:]),
        "rework": {"cases_with_rework": rework_cases, "rework_rate": round(rework_cases / max(1, len(by_case)), 4)},
        "variants": {
            "count": len(variant_counter),
            "top": [{"path": k, "cases": v, "share": round(v / max(1, len(by_case)), 4)}
                    for k, v in variant_counter.most_common(5)],
        },
        "conformance": conf,
        "bottleneck_activity": bottleneck,
        "per_activity": per_activity,
        "manual_minutes": sum(e["duration_minutes"] for e in events if not e["automated"]),
        "automated_minutes": sum(e["duration_minutes"] for e in events if e["automated"]),
        "discovered_model": {k: model[k] for k in ("nodes", "start_activities", "end_activities")},
        "discovered_model_edges": model["edges"],
        "discovery_filter": model["filter"],
        "generated_from": "synthetic event log (deterministic seed)",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", default="data/event_log.csv")
    parser.add_argument("--out", default="reports/mining.json")
    parser.add_argument("--dfg-out", default="reports/dfg.json")
    args = parser.parse_args()
    events = load_events(args.log)
    report = analyze(events)
    traces = traces_by_case(events)
    dfg = discover_dfg(traces)
    for path, payload in ((args.out, report), (args.dfg_out, dfg)):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
    conf = report["conformance"]
    print(
        f"mining: {report['cases']} casos | lead P50 {report['lead_time_hours_p50']}h | "
        f"retrabalho {report['rework']['rework_rate']:.0%} | gargalo {report['bottleneck_activity']} | "
        f"fitness {conf['fitness_log_to_model']:.0%} (trace {conf['trace_fitness']:.0%}) | "
        f"modelo descoberto: {len(report['discovered_model']['nodes'])} atividades, "
        f"{len(report['discovered_model_edges'])} arestas -> {args.out}"
    )


if __name__ == "__main__":
    main()
