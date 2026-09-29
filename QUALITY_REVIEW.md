# Revisão de qualidade (auditoria do próprio repositório)

Revisão feita depois da primeira versão, com uma pergunta só: **isso é projeto de verdade ou é fachada?**
Achados, o que foi corrigido e o que ficou de fora, sem maquiar.

## Achados que eram fachada (corrigidos)

| # | Achado | Gravidade | Correção | Evidência |
|---|---|---|---|---|
| 1 | README dizia "descobre o processo AS-IS", mas o BPMN era lista fixa no código (`AS_IS = [...]`) | **alta** — claim à frente da implementação | AS-IS agora é derivado do DFG descoberto no log; gateway inserido onde o log ramifica; arestas anotadas com a frequência real | `tests/test_bpmn.py::test_as_is_is_derived_from_the_log` e `::test_as_is_changes_when_log_changes` (log sem retrabalho ⇒ modelo sem `correcao`) |
| 2 | "Process mining" era média/percentil: zero descoberta (nenhum directly-follows) | **alta** | `src/mining.py` ganhou DFG (nós, arestas com contagem/casos/probabilidade), filtro por suporte mínimo, start/end activities, exportação `reports/dfg.json` | `tests/test_mining.py::test_dfg_is_derived_from_traces` |
| 3 | Nenhuma verificação de conformidade | média | Conformance DFG-based: fitness log→modelo, cobertura do modelo e trace fitness, com exemplos de desvio | `::test_conformance_is_perfect_on_same_log`, `::test_conformance_penalizes_deviation` |
| 4 | `impact.py` com números mágicos (`0.15`, `0.55`, `0.10`) inventados | **alta** — número não auditável | Residual **medido**: extração = fração de identificador inválido; validação = fração que precisa de humano (regras aplicadas a `data/documents.csv`); lançamento = fração de casos com divergência. Mais faixa de sensibilidade ±20% | `tests/test_impact.py::test_residuals_are_measured_not_hardcoded`, `::test_changing_documents_changes_residual` |
| 5 | BPMN sem diagrama (DI): não abria em bpmn.io/Camunda | média | `BPMNDiagram/BPMNPlane/BPMNShape/BPMNEdge` com layout em camadas; validação exige shape para cada nó e edge para cada fluxo | `tests/test_bpmn.py::test_models_written_and_valid` |
| 6 | Campo sem sentido `min_minutes_after_automation` no relatório | baixa | removido; ficaram cenário medido + faixa | `reports/impact.json` |
| 7 | Gateway gerado **sem fluxo de entrada** ⇒ parte do AS-IS inalcançável | **alta** (bug estrutural) | aresta atividade→gateway criada antes das saídas | `tests/test_bpmn.py::test_every_node_reachable_from_start` |
| 8 | `analyze()` quebrava com eventos não parseados (`str + timedelta`) | média | `normalize_events()` aceita CSV cru ou já carregado | `tests/test_mining.py` (usa `generate()` direto) |
| 9 | Fluxo n8n chamava `/work` — rota de **outro projeto** | **alta** | aponta para `POST /automate/validate` deste repo | `tests/test_flows.py::test_flow_contains_required_steps` |
| 10 | Fluxo n8n sem retry, sem caminho de erro, sem resposta de falha | **alta** — "brinquedo" | retry 3x com espera, saída de erro ⇒ DLQ no Excel, alerta no Teams e resposta 502 | `tests/test_flows.py::test_flow_handles_failure` |
| 11 | `api/openapi.yaml` escrito à mão (89 linhas) duplicando o FastAPI | média — duas fontes de verdade | arquivo deletado; `make openapi` gera o spec do próprio app | `tests/test_flows.py::test_service_app_exposes_documented_routes` |
| 12 | Runbook/docs citando ferramenta que não existe no repo | baixa | removido | — |

## Cortes deliberados (menos código, mesma prova)

| Deletado / não criado | Por quê |
|---|---|
| `tests/test_reproducibility.py` | o mesmo trabalho é feito por `scripts/check_reproducibility.py` (`make repro`) — uma fonte, não duas |
| `tests/test_n8n_flow.py` | sobreposto a `tests/test_flows.py`; assertions de erro/retry foram para o arquivo que já existia |
| `Dockerfile` + job de imagem no CI | o repositório `deploy-observability-lab` é o dono de empacotamento/deploy; aqui basta `pip install ".[api]"` |
| lint (ruff), tipos (mypy strict), coverage com piso, pip-audit, dependabot, pre-commit, SECURITY.md, CHANGELOG, ADRs | **o núcleo não tem nenhuma dependência de runtime** — auditar dependência inexistente é cerimônia; gates que eu não consigo rodar localmente viram claim não verificado |
| `deploy/kustomization.yaml` / PDB / NetworkPolicy / tracing OTel / teste de carga | YAGNI para o escopo; quando entra, entra com número que justifique |

## Como verificar (comandos reais)

```bash
make all       # pipeline: dados -> mineração -> BPMN -> impacto -> relatório
make test      # suíte unittest (núcleo stdlib; testes de API pulam sem fastapi)
make repro     # 2 execuções do pipeline, compara SHA-256 de 8 artefatos
make openapi   # spec gerado do FastAPI (fonte única)
```

Estado desta revisão: **57 testes passando (6 pulados sem os extras de API)**, reprodutibilidade byte a byte confirmada,
`make all` verde. Números medidos na última execução: 220 casos, lead time P50 2,39 h,
retrabalho 33%, gargalo `conferencia_manual`, fitness DFG 100%, residual de revisão humana 32,7%
(medido pelas regras, não estimado).

## Limites honestos (o que este repositório NÃO é)

- **Não é resultado corporativo**: log e documentos são sintéticos e determinísticos (seed 42). Não há empresa,
  cliente ou documento real, nem ganho comprovado em produção.
- **Descoberta é DFG**, não alinhamento ótimo nem minerador indutivo: não expressa concorrência com precisão
  e descarta arestas raras de propósito (exceção de 1 caso não aparece no modelo).
- **Low-code é desenho, não execução**: o fluxo n8n é importável e testado estruturalmente; a receita Power Automate
  não foi executada em tenant Microsoft (sem licença/ambiente aqui).
- A API de validação é de demonstração: sem autenticação, sem limite de taxa, sem auditoria.
