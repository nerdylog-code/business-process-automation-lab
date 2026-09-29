"""Process mining determinístico sobre o log de eventos sintético.

Métricas: lead time (P50/P90), throughput semanal, retrabalho, variantes do processo,
gargalo (maior tempo médio de espera) e taxa de conformidade com a sequência esperada.
Uso: python -m src.mining [--log data/event_log.csv] [--out reports/mining.json]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime

EXPECTED_SEQUENCE = ["recebimento", "triagem", "conferencia_manual", "aprovacao", "lancamento"]


def load_events(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["duration_minutes"] = int(r["duration_minutes"])
        r["wait_minutes"] = int(r["wait_minutes"])
        r["rework"] = int(r["rework"])
        r["automated"] = int(r.get("automated", 0))
        r["timestamp_start"] = datetime.fromisoformat(r["timestamp_start"])
    return rows


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    lower, upper = int(k), min(int(k) + 1, len(ordered) - 1)
    if lower == upper:
        return float(ordered[lower])
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * (k - lower))


def analyze(events: list[dict]) -> dict:
    by_case: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        by_case[e["case_id"]].append(e)

    lead_times = []
    rework_cases = 0
    variants: Counter = Counter()
    case_start: dict[str, datetime] = {}
    case_end: dict[str, datetime] = {}

    for case_id, evs in by_case.items():
        evs.sort(key=lambda x: x["timestamp_start"])
        start = evs[0]["timestamp_start"]
        end = evs[-1]["timestamp_start"] + _minutes(evs[-1]["duration_minutes"])
        case_start[case_id] = start
        case_end[case_id] = end
        lead_times.append((end - start).total_seconds() / 60.0)
        variants[" -> ".join(e["activity"] for e in evs)] += 1
        if any(e["rework"] for e in evs):
            rework_cases += 1

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

    bottleneck = max(per_activity.items(), key=lambda kv: kv[1]["avg_wait_minutes"])[0]

    manual_minutes = sum(e["duration_minutes"] for e in events if not e["automated"])
    automated_minutes = sum(e["duration_minutes"] for e in events if e["automated"])

    weeks = Counter()
    for case_id, end in case_end.items():
        weeks[f"{end.isocalendar().year}-W{end.isocalendar().week:02d}"] += 1

    conforming = 0
    for case_id, evs in by_case.items():
        seen = [e["activity"] for e in evs]
        filtered = [a for a in seen if a != "correcao"]
        if filtered == EXPECTED_SEQUENCE:
            conforming += 1

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
        "rework": {
            "cases_with_rework": rework_cases,
            "rework_rate": round(rework_cases / max(1, len(by_case)), 4),
        },
        "variants": {
            "count": len(variants),
            "top": [{"path": k, "cases": v} for k, v in variants.most_common(5)],
        },
        "conformance_rate": round(conforming / max(1, len(by_case)), 4),
        "bottleneck_activity": bottleneck,
        "per_activity": per_activity,
        "manual_minutes": manual_minutes,
        "automated_minutes": automated_minutes,
        "generated_from": "synthetic event log (seed 42)",
    }


def _minutes(value: int):
    from datetime import timedelta

    return timedelta(minutes=value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", default="data/event_log.csv")
    parser.add_argument("--out", default="reports/mining.json")
    args = parser.parse_args()
    report = analyze(load_events(args.log))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(
        f"mining: {report['cases']} casos | lead time P50 {report['lead_time_hours_p50']}h | "
        f"retrabalho {report['rework']['rework_rate']:.0%} | gargalo: {report['bottleneck_activity']} -> {args.out}"
    )


if __name__ == "__main__":
    main()
