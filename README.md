# Business Process Automation Lab

Laboratório reprodutível de automação de um processo administrativo/fiscal: parte de um log de eventos
sintético, **descobre** o processo AS-IS (directly-follows graph), propõe o TO-BE com automação,
**mede** o impacto com parâmetros tirados dos próprios artefatos e entrega o que uma área de operações usa:
BPMN 2.0, requisitos, API, fluxos low-code e relatório executivo.

> Dados **sintéticos e determinísticos** (seed 42). Nenhuma empresa, cliente ou documento real.
> Os números de impacto são **simulação** sobre esse log, com residual **medido** — não são resultado corporativo.

## Resultado da última execução (220 casos)

| Métrica | Valor | De onde sai |
|---|---|---|
| Lead time P50 / P90 | 2,39 h / 3,90 h | `reports/mining.json` |
| Casos com retrabalho | 33% | idem |
| Gargalo (maior espera média) | `conferencia_manual` | idem |
| Variantes do processo | 2 | idem |
| Fitness do modelo descoberto | 100% (trace 100%) | `reports/mining.json` → `conformance` |
| Residual de revisão humana | 32,7% | regras aplicadas a `data/documents.csv` |
| Ganho simulado | 202 h/mês (faixa 185–219 h) | `reports/impact.json` |

## O que tem aqui

| Artefato | Arquivo | Para que serve |
|---|---|---|
| Log de eventos + documentos sintéticos | `data/event_log.csv`, `data/documents.csv` | insumo da descoberta e da medição |
| Descoberta (DFG) + conformance | `src/mining.py` → `reports/mining.json`, `reports/dfg.json` | o que o log mostra, com fitness e desvios |
| AS-IS em BPMN 2.0 **derivado do log** | `bpmn/as_is.bpmn` | abre em bpmn.io/Camunda (tem diagrama) |
| TO-BE em BPMN 2.0 (desenhado) | `bpmn/to_be.bpmn` | onde a automação entra; aprovação segue humana |
| Impacto com residual medido | `src/impact.py` → `reports/impact.json` | ganho + faixa de sensibilidade ±20% |
| API de validação | `src/automation_service.py` (`make openapi` gera o spec) | contrato HTTP que o low-code consome |
| Fluxo n8n importável | `flows/n8n_process_automation.json` | retry 3x, DLQ, alerta no Teams, resposta 502 |
| Receita Power Automate | `flows/power_automate_recipe.md` | HTTP + Parse JSON + Excel/Teams + escopo de erro |
| Requisitos | `docs/requirements.md` | funcionais e não funcionais, rastreáveis a teste |
| Relatório executivo | `dashboard/process_report.html` | DFG, variantes, desvios e sensibilidade |
| Revisão de qualidade | `QUALITY_REVIEW.md` | os achados da auditoria e os cortes deliberados |

## Como verificar

```bash
make all      # dados -> mineração -> BPMN -> impacto -> relatório
make test     # 57 testes unittest (núcleo é só stdlib; testes de API pulam sem fastapi)
make repro    # roda o pipeline 2x e compara SHA-256 dos 8 artefatos
make openapi  # spec OpenAPI gerado do FastAPI (fonte única, não escrito à mão)
```

## Descoberta e conformidade (o miolo)

`src/mining.py` monta o **DFG**: nós = atividades observadas, arestas = relações directly-follows com
contagem/casos/probabilidade, filtradas por suporte mínimo (≥3 casos e ≥5%) para cortar ruído de exceção.
O AS-IS é construído a partir desse grafo — inclusive o `exclusiveGateway`, que só aparece onde o log
mostra mais de uma saída. Conformance é DFG-based: cobertura de arestas log↔modelo e *trace fitness*
(fração de casos cujo caminho é válido no modelo).

Custo disso, dito com clareza: DFG não expressa concorrência com precisão e descarta arestas raras de
propósito. Alinhamento ótimo exigiria rede de Petri + minerador indutivo — não é o escopo aqui.

## Impacto sem número mágico

Cada residual vem de um artefato do lab: extração = fração de identificador inválido; validação =
fração que ainda precisa de humano (`needs_human_review` sobre os documentos); lançamento = fração de
casos com divergência no log. Mudar o insumo muda o número — há teste que prova isso.

## Simplificações deliberadas

| Decisão | Motivo |
|---|---|
| Núcleo em **stdlib** (zero dependências de runtime) | roda em qualquer Python 3.11+ sem instalar nada; dependências só nos extras `.api` |
| Sem `Dockerfile` aqui | o repo `deploy-observability-lab` é o dono de empacotamento/deploy |
| Sem lint/tipos/cobertura/pip-audit no CI | auditar dependência inexistente é cerimônia; o gate real é teste + reprodutibilidade |
| `api/openapi.yaml` deletado | o FastAPI gera o spec: uma fonte de verdade, não duas |
| Sem tracing OTel, sem kustomize, sem teste de carga | YAGNI; entram quando houver número/pergunta que justifique |

## Limitações honestas

- Log, documentos e regras são sintéticos; não há operação real de cliente nem ganho comprovado em produção.
- A receita Power Automate é desenho documentado, **não executado em tenant** (sem licença/ambiente aqui).
- A API é de demonstração: sem autenticação, rate limit ou auditoria.
- Descoberta por DFG, não alinhamento ótimo; exceção de 1 caso não entra no modelo.
