"""Relatório executivo HTML auto-contido: KPIs, DFG, variantes, fitness e sensibilidade."""
from __future__ import annotations

import argparse
import html
import json
import os


def _bar(value: float, maximum: float, color: str = "#38bdf8") -> str:
    pct = 0 if not maximum else max(2, min(100, round(value / maximum * 100)))
    return (f"<div style='background:#1e293b;border-radius:6px;height:10px;width:150px;display:inline-block;"
            f"overflow:hidden;vertical-align:middle'><div style='width:{pct}%;height:100%;background:{color}'></div></div>")


def _mermaid(dfg: dict, limit: int = 12) -> str:
    """DFG em Mermaid: o leitor vê o processo descoberto, não só números."""
    edges = dfg["edges"][:limit]
    lines = ["flowchart LR"]
    for edge in edges:
        lines.append(f'    {edge["source"]}["{edge["source"]}"] -->|{edge["cases"]}| {edge["target"]}["{edge["target"]}"]')
    return "\n".join(lines)


def render(mining: dict, impact: dict, dfg: dict) -> str:
    lt = mining["lead_time_minutes"]
    conf = mining["conformance"]
    acts = mining["per_activity"]
    max_wait = max(a["avg_wait_minutes"] for a in acts.values()) or 1

    activity_rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{data['events']}</td><td>{data['avg_duration_minutes']} min</td>"
        f"<td>{data['avg_wait_minutes']} min {_bar(data['avg_wait_minutes'], max_wait, '#f97316')}</td></tr>"
        for name, data in sorted(acts.items(), key=lambda kv: -kv[1]["avg_wait_minutes"])
    )
    variant_rows = "".join(
        f"<tr><td>{html.escape(v['path'])}</td><td>{v['cases']}</td><td>{v['share']:.0%}</td></tr>"
        for v in mining["variants"]["top"]
    )
    automation_rows = "".join(
        f"<tr><td>{html.escape(a['automation'])}</td><td>{', '.join(a['replaces_activities'])}</td>"
        f"<td>{a['baseline_minutes']} min</td>"
        f"<td>{a['residual_measured']:.0%} <span style='color:#94a3b8'>({html.escape(a['residual_source'])})</span></td>"
        f"<td><b>{a['hours_saved_per_month']['measured']} h</b>"
        f" <span style='color:#94a3b8'>({a['hours_saved_per_month']['optimistic']}–{a['hours_saved_per_month']['pessimistic']})</span></td></tr>"
        for a in impact["automations"]
    )
    deviation_rows = "".join(
        f"<tr><td>{html.escape(d['case_id'])}</td><td>{html.escape(', '.join(d['missing_edges']) or '—')}</td></tr>"
        for d in conf["deviating_examples"]
    )
    c = impact["consolidated"]
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Automação de processos — relatório executivo</title>
<style>
body{{font-family:system-ui,Segoe UI,Roboto,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:28px}}
h1{{font-size:22px;margin:0 0 4px}}h2{{font-size:15px;margin:26px 0 8px;color:#93c5fd}}
.sub{{color:#94a3b8;font-size:13px;margin-bottom:18px}}
.kpis{{display:flex;gap:12px;flex-wrap:wrap}}
.kpi{{background:#111c33;border:1px solid #22304d;border-radius:12px;padding:12px 16px;min-width:168px}}
.kpi b{{display:block;font-size:21px;color:#f8fafc}}.kpi span{{font-size:12px;color:#94a3b8}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}}
th,td{{text-align:left;padding:7px 8px;border-bottom:1px solid #22304d}}th{{color:#94a3b8;font-weight:600}}
pre.mermaid{{background:#111c33;border:1px solid #22304d;border-radius:10px;padding:12px;font-size:11px;overflow:auto}}
.note{{font-size:12px;color:#fbbf24;margin-top:12px}}
.tag{{font-size:11px;color:#0f172a;background:#38bdf8;border-radius:6px;padding:1px 6px;margin-left:6px}}</style></head><body>
<h1>Conferência documental — AS-IS descoberto vs TO-BE proposto</h1>
<div class="sub">{mining['cases']} casos · {mining['events']} eventos · log sintético determinístico ·
 modelo AS-IS <b>descoberto por directly-follows</b> (não hardcoded) · fitness {conf['fitness_log_to_model']:.0%}</div>
<div class="kpis">
<div class="kpi"><b>{lt['p50']/60:.1f} h</b><span>lead time P50</span></div>
<div class="kpi"><b>{lt['p90']/60:.1f} h</b><span>lead time P90</span></div>
<div class="kpi"><b>{mining['rework']['rework_rate']:.0%}</b><span>casos com retrabalho</span></div>
<div class="kpi"><b>{conf['trace_fitness']:.0%}</b><span>trace fitness (DFG)</span></div>
<div class="kpi"><b>{mining['variants']['count']}</b><span>variantes observadas</span></div>
<div class="kpi"><b>{mining['bottleneck_activity']}</b><span>gargalo (maior espera)</span></div>
<div class="kpi"><b>{c['hours_saved_per_month']} h</b><span>economia medida/mês</span></div>
<div class="kpi"><b>{c['manual_hours_after']} h</b><span>manual depois (de {c['manual_hours_before']} h)</span></div>
</div>
<h2>Processo descoberto (DFG — arestas = nº de casos)</h2>
<pre class="mermaid">{html.escape(_mermaid(dfg))}</pre>
<h2>Espera média por atividade (AS-IS)</h2>
<table><tr><th>atividade</th><th>eventos</th><th>duração média</th><th>espera média</th></tr>{activity_rows}</table>
<h2>Variantes do processo</h2>
<table><tr><th>trajetória</th><th>casos</th><th>share</th></tr>{variant_rows}</table>
<h2>Desvios de conformidade (exemplos)</h2>
<table><tr><th>caso</th><th>arestas não observadas no modelo</th></tr>{deviation_rows}</table>
<h2>Automações do TO-BE — residual medido e sensibilidade</h2>
<table><tr><th>automação</th><th>substitui</th><th>base medida</th><th>residual (medido no lab)</th><th>ganho/mês</th></tr>{automation_rows}</table>
<div class="note"><b>Simulação</b> sobre log sintético determinístico: todo número vem do log de eventos e da engine de regras deste lab.
O residual não é estimativa: é medido ({html.escape(impact['formula'])}). A faixa mostra ±20% sobre o residual.</div>
</body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mining", default="reports/mining.json")
    parser.add_argument("--impact", default="reports/impact.json")
    parser.add_argument("--dfg", default="reports/dfg.json")
    parser.add_argument("--out", default="dashboard/process_report.html")
    args = parser.parse_args()
    with open(args.mining, encoding="utf-8") as fh:
        mining = json.load(fh)
    with open(args.impact, encoding="utf-8") as fh:
        impact = json.load(fh)
    with open(args.dfg, encoding="utf-8") as fh:
        dfg = json.load(fh)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(render(mining, impact, dfg))
    print(f"report: {args.out}")


if __name__ == "__main__":
    main()
