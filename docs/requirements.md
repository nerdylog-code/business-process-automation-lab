# Requisitos — automação da conferência documental

Documento de requisitos no formato que as vagas de "analista de processos / requisitos" pedem:
funcionais (RF), não funcionais (RNF), regras de negócio (RN) e critérios de aceite rastreáveis aos testes.

## Contexto

Processo de conferência de documentos fiscais/administrativos: recebimento → triagem → conferência
manual → correção (retrabalho) → aprovação → lançamento. Medido por process mining em `reports/mining.json`.

## Requisitos funcionais

| ID | Requisito | Rastreável em |
|---|---|---|
| RF-01 | Ingerir documento (número, CNPJ, valor, valor esperado, emissão, vencimento) | `src/rules.validate_document`, `tests/test_rules.py` |
| RF-02 | Normalizar formato de valor (pt-BR e numérico) | `src/rules.parse_amount` |
| RF-03 | Validar identificador (CNPJ com dígitos verificadores; número do documento) | `src/rules.cnpj_is_valid` |
| RF-04 | Detectar divergência de valor acima de tolerância de R$ 0,01 | `src/rules.validate_document` |
| RF-05 | Detectar inconsistência de datas (vencimento antes da emissão) | `src/rules.validate_document` |
| RF-06 | Encaminhar exceção para conferência humana, sem bloqueio automático | `status = revisao_humana` |
| RF-07 | Processar lote e reportar taxa de automação | `POST /automate/batch` |
| RF-08 | Orquestrar o fluxo sem código (n8n/Power Automate) registrando em planilha e notificando o responsável | `flows/` |
| RF-09 | Medir o processo: lead time, retrabalho, gargalo, variantes, conformidade | `src/mining.py` |
| RF-10 | Modelar AS-IS e TO-BE em BPMN 2.0 | `src/bpmn.py`, `bpmn/` |
| RF-11 | Estimar ganho com fórmula explícita e fator de trabalho residual | `src/impact.py` |
| RF-12 | Publicar relatório executivo legível por área de negócio | `src/report.py` |

## Requisitos não funcionais

| ID | Requisito | Como é atendido |
|---|---|---|
| RNF-01 | Determinismo (mesma entrada ⇒ mesma saída) | seed fixa em `generate_event_log`, ausência de aleatoriedade fora dela |
| RNF-02 | Núcleo sem dependências externas | stdlib apenas em `mining/bpmn/impact/rules/report` |
| RNF-03 | Testes automatizados e CI | `unittest` + GitHub Actions (matriz 3.11/3.12) |
| RNF-04 | Contrato HTTP versionado | `api/openapi.yaml` |
| RNF-05 | Portabilidade do serviço | `Dockerfile` + `make api` |
| RNF-06 | Sem dados reais | dados sintéticos; nenhuma Informação pessoal/fiscal de terceiros |
| RNF-07 | Observabilidade mínima no serviço | `/healthz` + KPIs expostos por endpoint |
| RNF-08 | Rastreabilidade requisito→teste | tabela acima + `make test` |

## Regras de negócio

- **RN-01** Divergência de valor > R$ 0,01 ⇒ conferência humana.
- **RN-02** CNPJ inválido ⇒ conferência humana (nunca lançar automaticamente).
- **RN-03** Vencimento anterior à emissão ⇒ conferência humana.
- **RN-04** Casos sem divergência seguem sem intervenção, mas a **aprovação continua sendo humana**.

## Critérios de aceite

1. `make all` produz `data/event_log.csv`, `reports/mining.json`, `bpmn/as_is.bpmn`, `bpmn/to_be.bpmn`,
   `reports/impact.json` e `dashboard/process_report.html`.
2. `make test` passa sem dependências externas (API é pulada se fastapi ausente, e roda quando presente).
3. O TO-BE em BPMN contém ≥ 3 `serviceTask` e mantém ≥ 1 `userTask` (aprovação humana).
4. O relatório declara explicitamente que os números de ganho são **simulação** sobre log sintético.

## Fora de escopo

- Integração com ERP real, eSocial/EFD reais, ou qualquer documento de cliente.
- Promessa de ROI corporativo: a medição é feita sobre o log sintético do próprio lab.
