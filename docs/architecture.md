# Arquitetura

```
event log sintético ──► process mining ──► BPMN AS-IS / TO-BE
        │                    │                     │
        │                    ▼                     ▼
        └──────────► simulação de impacto ──► relatório HTML executivo
                             ▲
   sistema de origem ──► API de validação ──► fluxo n8n / receita Power Automate ──► Excel/SharePoint + Teams
```

## Componentes

| Camada | Módulo | Responsabilidade |
|---|---|---|
| Ingestão simulada | `src/generate_event_log.py` | log determinístico de eventos (cases/atividades/atores/tempos) |
| Medição | `src/mining.py` | KPIs de processo e gargalo |
| Modelagem | `src/bpmn.py` | BPMN 2.0 AS-IS/TO-BE + validação estrutural |
| Regras | `src/rules.py` | normalização e regras de conferência (núcleo compartilhado) |
| Estimativa | `src/impact.py` | ganho simulado com fator residual |
| Interface | `src/automation_service.py` | contrato HTTP consumido pelo low-code |
| Orquestração | `flows/` | n8n importável + receita Power Automate |
| Comunicação | `src/report.py` | relatório executivo auto-contido |

## Decisões

1. **Medir antes de automatizar** — sem baseline (lead time, retrabalho, gargalo) não há priorização defensável.
2. **BPMN como contrato** — o mesmo modelo serve para negociar com a área e para orientar a implementação.
3. **Núcleo stdlib + serviço fino** — as regras são testáveis sem instalar nada; a API é uma casca.
4. **Low-code consumindo API, não substituindo-a** — quem não programa opera o fluxo; a lógica fica versionada em código.
5. **Humano como exceção explícita** — `needs_human_review` é parte do contrato, não um detalhe de UI.

## Trade-offs assumidos

- Log sintético ⇒ números internamente coerentes, mas **não** representam nenhuma empresa real.
- Sem tenant Microsoft ⇒ a receita Power Automate é documentação técnica, não execução validada.
- Sem banco: os relatórios são arquivos JSON/HTML versionáveis; suficiente para o escopo do lab.

## Limites

- Não há claims de produção, SLA, volume real ou ROI corporativo.
- Não há dados de cliente, documento real, credencial ou caminho pessoal no repositório.
