"""Gera um relatório executivo HTML auto-contido (AS-IS vs TO-BE simulado)."""
from __future__ import annotations

import argparse
import html
import json
import os


def _bar(value: float, maximum: float, color: str = "#38bdf8") -> str:
    pct = 0 if not maximum else max(2, min(100, round(value / maximum * 100)))
    return f"<div style='background:#1e293b;border-radius:6px;height:10px;width:160px;display:inline-block;overflow:hidden'><div style='width:{pct}%;height:100%;background:{color}'></div></div>"


def render(mining: dict, impact: dict) -> str:
    lt = mining["lead_time_minutes"]
    acts = mining["per_activity"]
    max_wait = max(a["avg_wait_minutes"] for a in acts.values()) or 1
    rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{data['events']}</td><td>{data['avg_duration_minutes']} min</td>"
        f"<td>{data['avg_wait_minutes']} min {_bar(data['avg_wait_minutes'], max_wait)}</td></tr>"
        for name, data in sorted(acts.items(), key=lambda kv: -kv[1]["avg_wait_minutes"])
    )
    autos = "".join(
        f"<tr><td>{html.escape(a['automation'])}</td><td>{', '.join(a['replaces_activities'])}</td>"
        f"<td>{a['baseline_minutes']} min</td><td>{int(a['residual_manual_fraction']*100)}%</td>"
        f"<td>{a['hours_saved_per_month']} h/mês</td></tr>"
        for a in impact["automations"]
    )
    c = impact["consolidated"]
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Automação de processos — relatório executivo</title>
<style>body{{font-family:system-ui,Segoe UI,Roboto,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:28px}}
h1{{font-size:22px;margin:0 0 4px}}h2{{font-size:16px;margin:26px 0 8px;color:#93c5fd}}
.sub{{color:#94a3b8;font-size:13px;margin-bottom:18px}}
.kpis{{display:flex;gap:12px;flex-wrap:wrap}}.kpi{{background:#111c33;border:1px solid #22304d;border-radius:12px;padding:12px 16px;min-width:170px}}
.kpi b{{display:block;font-size:22px;color:#f8fafc}}.kpi span{{font-size:12px;color:#94a3b8}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}}th,td{{text-align:left;padding:7px 8px;border-bottom:1px solid #22304d}}
th{{color:#94a3b8;font-weight:600}}.note{{font-size:12px;color:#fbbf24;margin-top:10px}}</style></head><body>
<h1>Conferência documental — AS-IS vs TO-BE</h1>
<div class="sub">Log sintético determinístico (seed 42) · {mining['cases']} casos · {mining['events']} eventos · gerado pelo Business Process Automation Lab</div>
<div class="kpis">
<div class="kpi"><b>{lt['p50']/60:.1f} h</b><span>lead time P50</span></div>
<div class="kpi"><b>{lt['p90']/60:.1f} h</b><span>lead time P90</span></div>
<div class="kpi"><b>{mining['rework']['rework_rate']:.0%}</b><span>casos com retrabalho</span></div>
<div class="kpi"><b>{mining['conformance_rate']:.0%}</b><span>conformidade com o fluxo esperado</span></div>
<div class="kpi"><b>{mining['bottleneck_activity']}</b><span>gargalo (maior espera)</span></div>
<div class="kpi"><b>{c['hours_saved_per_month']} h</b><span>economia simulada / mês</span></div>
<div class="kpi"><b>{c['workdays_saved_per_month']}</b><span>dias úteis / mês (simulado)</span></div>
</div>
<h2>Espera média por atividade (AS-IS)</h2>
<table><tr><th>atividade</th><th>eventos</th><th>duração média</th><th>espera média</th></tr>{rows}</table>
<h2>Automações propostas no TO-BE</h2>
<table><tr><th>automação</th><th>substitui</th><th>base medida</th><th>residual manual</th><th>ganho simulado</th></tr>{autos}</table>
<div class="note">Todos os números vêm de um log <b>sintético</b>. A economia é uma <b>simulação</b> ({html.escape(impact['formula'])}), não um resultado corporativo medido.</div>
</body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mining", default="reports/mining.json")
    parser.add_argument("--impact", default="reports/impact.json")
    parser.add_argument("--out", default="dashboard/process_report.html")
    args = parser.parse_args()
    with open(args.mining, encoding="utf-8") as fh:
        mining = json.load(fh)
    with open(args.impact, encoding="utf-8") as fh:
        impact = json.load(fh)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(render(mining, impact))
    print(f"report: {args.out}")


if __name__ == "__main__":
    main()
