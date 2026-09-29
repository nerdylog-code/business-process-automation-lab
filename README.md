# Business Process Automation Lab

Laboratório **reprodutível** de automação de processos de negócio: parte de um log de eventos
sintético de um processo administrativo/fiscal, descobre o processo **AS-IS**, propõe o **TO-BE**
com automação, mede o impacto em simulação auditável e entrega os artefatos que uma área de
operações realmente usa — **BPMN 2.0**, requisitos documentados, KPIs, API de automação e fluxos
low-code (n8n importável + receita Power Automate).

> Todos os dados são **sintéticos e determinísticos** (seed fixa). Nenhum dado de empresa, cliente
> ou documento real. Os números de impacto são **simulações** calculadas a partir do log sintético,
> com a fórmula exposta — não são resultados de operação corporativa.

## Problema

Processos de conferência documental (fiscal/contábil/backoffice) costumam ter:
- etapas manuais repetitivas de leitura/conferência;
- retrabalho por divergência encontrada tarde;
- fila em uma etapa específica (gargalo);
- nenhuma medição de lead time, então melhoria vira opinião.

## O que este repositório entrega

| Artefato | Arquivo | Para que serve |
|---|---|---|
| Log de eventos sintético | `data/event_log.csv` | insumo do process mining (cases, atividades, timestamps, atores) |
| Process mining | `src/mining.py` → `reports/mining.json` | lead time P50/P90, retrabalho, variantes, gargalo, throughput |
| Modelo AS-IS em BPMN 2.0 | `bpmn/as_is.bpmn` | linguagem que a área de processos entende |
| Modelo TO-BE em BPMN 2.0 | `bpmn/to_be.bpmn` | onde a automação entra e o que permanece humano |
| Simulação de impacto | `src/impact.py` → `reports/impact.json` | horas economizadas estimadas, com fórmula explícita |
| API de automação | `src/automation_service.py` + `api/openapi.yaml` | contrato HTTP que o low-code consome |
| Fluxo n8n importável | `flows/n8n_process_automation.json` | orquestração sem código do fluxo |
| Receita Power Automate | `flows/power_automate_recipe.md` | HTTP + Parse JSON + Excel/SharePoint/Teams |
| Requisitos | `docs/requirements.md` | funcionais e não funcionais, rastreáveis |
| Relatório executivo | `dashboard/process_report.html` | painel auto-contido (AS-IS vs TO-BE) |

## Quickstart

```bash
make all        # gera log → minera → BPMN → impacto → relatório
make test       # unittest (stdlib, sem dependências)
make api        # serviço FastAPI (requer fastapi/uvicorn)
```

## Fluxo medido (AS-IS, do log sintético)

1. Recebimento do documento → 2. Triagem → 3. Conferência manual → 4. Correção (retrabalho, quando há divergência)
→ 5. Aprovação → 6. Lançamento. O gargalo e a taxa de retrabalho saem de `reports/mining.json`.

## TO-BE proposto

- **Extração automática** (substitui a leitura manual na triagem e na conferência de campos).
- **Validação por regras** (divergência de valor/data/identificador) — decide se vai para conferência humana.
- **Conferência humana** permanece como etapa de exceção (aprovação continua humana).
- **Lançamento automatizado** por API/planilha.

## Decisões e trade-offs

- **Process mining antes de automatizar**: sem medir, não há como priorizar o que automatizar.
- **BPMN como contrato** entre TI e área de negócio (mesmo vocabulário do AS-IS/TO-BE).
- **API + low-code em vez de só script**: o processo fica operável por quem não programa.
- **Simulação explícita** em vez de métrica inventada: a fórmula está em `src/impact.py`.

## Limitações honestas

- Log, documentos e regras são sintéticos; não há operação real de cliente.
- Os ganhos são **estimativas** derivadas das durações medidas no log sintético.
- A receita Power Automate é documentada (sem tenant); a automação executável aqui é o serviço + n8n.
- Não há claims de produção corporativa, SLA ou volume real.
