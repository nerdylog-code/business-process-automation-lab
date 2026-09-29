# Receita Power Automate (conferência documental)

Receita **documentada** (sem tenant) equivalente ao fluxo n8n importável deste repositório.
Ela conecta o Microsoft 365 ao serviço de automação do lab e mantém a decisão humana como etapa
obrigatória quando há divergência.

> Limitações: este arquivo é uma receita técnica. **Sem tenant**, não há validação de execução real
> nem claim de produção corporativa. O contrato HTTP é o mesmo validado por `api/openapi.yaml`.

## Gatilho

`Quando um novo e-mail chega em uma pasta compartilhada` (Outlook) **ou**
`Quando um arquivo é criado na pasta do SharePoint` (SharePoint → `Quando um arquivo é criado (apenas propriedades)`).

## Passos

1. **Obter o conteúdo do documento** — ação `Obter anexo`/`Obter conteúdo do arquivo` (Outlook/SharePoint).
2. **HTTP** — `POST https://<host>/automate/validate`
   - Cabeçalho: `Content-Type: application/json`
   - Corpo: o JSON do passo 3.
3. **Parse JSON** — schema do documento (campos que o serviço espera):

```json
{
  "type": "object",
  "required": ["document_number", "cnpj", "amount", "issued_at", "due_date"],
  "properties": {
    "document_number": { "type": "string" },
    "cnpj": { "type": "string" },
    "amount": { "type": ["string", "number"] },
    "expected_amount": { "type": ["string", "number", "null"] },
    "issued_at": { "type": "string" },
    "due_date": { "type": "string" }
  }
}
```

4. **Condição** — `needs_human_review` **é igual a** `true`
   - **Sim** → `Adicionar linha em tabela` (Excel Online/SharePoint, aba `Divergencias`) com
     `document_number`, `amount`, `divergences`; depois `Postar mensagem no chat ou canal` (Teams)
     mencionando o responsável pela conferência.
   - **Não** → `Adicionar linha em tabela` (aba `Aprovados`) e **seguir para o lançamento**.
5. **Apply to each** — quando o webhook receber lote (`/automate/batch`), itere `results` e registre
   linha por linha, mantendo `automation_rate` no corpo da notificação.
6. **Resposta** — `Responder ao Power Apps/aplicativo` ou `Enviar mensagem` com
   `status`, `divergences` e o link da linha criada.

## Resposta do serviço (contrato)

```json
{
  "status": "revisao_humana",
  "needs_human_review": true,
  "divergences": [{ "rule": "valor_divergente", "delta": 234.56 }],
  "normalized": {
    "amount": 1234.56,
    "document_number": "NF-10231",
    "cnpj": "11222333000181",
    "issued_at": "2026-06-01",
    "due_date": "2026-06-30"
  }
}
```

## Por que isto fecha o ciclo

- A **aprovação continua humana** (`needs_human_review`), então a automação não decide sozinha em exceção.
- O **registro** (Excel/SharePoint) é o mesmo artefato que a equipe já usava → adoção sem trocar ferramenta.
- O **Teams** entrega a exceção para quem resolve, em vez de criar fila invisível.

## Testes relacionados

`tests/test_flows.py` valida o contrato HTTP, o fluxo n8n importável e a presença destas etapas.
