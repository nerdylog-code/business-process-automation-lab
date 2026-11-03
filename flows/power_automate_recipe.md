# Receita Power Automate (equivalente ao fluxo n8n)

Power Automate é o caminho low-code dentro do Microsoft 365 — quando a empresa já tem licença,
não faz sentido pedir servidor. Esta receita replica o mesmo contrato do fluxo n8n
(`flows/n8n_process_automation.json`) usando conector nativo, com tratamento de erro explícito.

## Gatilho

**Quando um arquivo é criado na pasta** (SharePoint → `Documentos/Entrada`) **ou**
**Quando uma solicitação HTTP é recebida** (se o documento chega de outro sistema).
Use o gatilho de SharePoint quando o processo real é "alguém joga o PDF numa pasta".

## Passos

| # | Ação | Configuração | Por quê |
|---|---|---|---|
| 1 | Inicializar variável `request_id` | `guid()` | rastrear a execução ponta a ponta |
| 2 | Obter conteúdo do arquivo | dinâmico do gatilho | — |
| 3 | **HTTP** → API de regras | `POST {env}/automate/validate`, corpo `Parse JSON` abaixo, **Política de repetição: 4 tentativas, intervalo PT10S, exponencial** | rede falha; retry é obrigatório |
| 4 | **Parse JSON** | schema abaixo | sem schema, o passo seguinte vira adivinhação |
| 5 | **Condição** `needs_human_review` é igual a `true` | — | bifurcação principal |
| 6a | *Se sim* → **Adicionar linha** (Excel/SharePoint) na tabela `Exceções` + **Postar mensagem** no Teams com `@mention` do responsável | — | exceção vai para fila com dono |
| 6b | *Se não* → **Adicionar linha** em `Aprovados` | — | caminho feliz |
| 7 | **Responder** / **Atualizar status** | 202 em revisão, 200 aprovado | contrato de saída |
| 8 | **Escopo "Tratar erro"**: configurar *Executar após* = falhou/expirou/ignorado nos passos 3–6 | — | sem isso o erro é silencioso |
| 9 | Dentro do escopo: **Adicionar linha** na tabela `Erros` (`request_id`, `json`, `mensagem`) + **Postar no Teams** + **Responder 502** | `result('API de regras')` para o corpo do erro | DLQ + alerta + resposta coerente |

## Schema do `Parse JSON` (cole em "Usar payload de exemplo")

```json
{
  "document_number": "NF-20231",
  "amount": 1234.56,
  "cnpj": "11222333000181",
  "issued_at": "2026-06-01",
  "due_date": "2026-06-30",
  "status": "aprovado_automaticamente",
  "needs_human_review": false,
  "divergences": [],
  "request_id": "ab12cd34"
}
```

## Diferenças honestas vs. o fluxo n8n

| Aspecto | n8n | Power Automate |
|---|---|---|
| Tratamento de erro | saída 2 do nó (`continueErrorOutput`) | escopo com *Executar após* |
| Custo | self-hosted ou cloud própria | licença M365 já contratada |
| Limite prático | sem licença por ação | limites de ação/dia por plano |
| Melhor quando | integração com sistemas fora do M365 | processo vive dentro do M365 |

## Processamento em lote (Aplicar a cada)

Quando a pasta recebe vários documentos, o fluxo roda uma vez por arquivo com **Aplicar a cada**
(`Apply to each`) sobre a saída do gatilho de pasta:

| # | Ação | Configuração |
|---|---|---|
| 1 | Listar arquivos da pasta | `Obter arquivos (somente propriedades)` |
| 2 | **Aplicar a cada** arquivo | limite de concorrência: 1 (evita estourar limite de ações e mantém rastreio) |
| 3 | Dentro do laço: `request_id` = `guid()`, chamar a API, ramificar aprovação/exceção | igual aos passos 2–7 acima |
| 4 | Após o laço: consolidar contagem (aprovados / exceções / erros) e postar resumo no Teams | evidência diária do processo |

Cuidado real: sem limite de concorrência o fluxo estoura o limite de chamadas do plano e passa a
falhar em silêncio no fim do lote — por isso o passo 2 fixa concorrência 1 e o escopo de erro
registra em `Erros`.

## Limitações (honesto)

- **Sem tenant**: nenhuma destas ações foi executada em ambiente Microsoft real por este repositório.
  A receita descreve o desenho e o contrato; a validação executada aqui é a da API (`/automate/validate`).
- Sem licença Power Automate Premium, os conectores HTTP podem exigir plano e política de DLP.
- O conector de Excel/SharePoint é mais lento que a API; para volume alto, use Dataverse ou fila.
- `Parse JSON` exige schema explícito — sem ele o Power Automate trata tudo como string.

## Como testar sem licença

O contrato do passo 3 é o mesmo da API deste repo: `make api` sobe a API em `localhost:8080` e o
Power Automate pode chamá-la via gateway on-premises ou dev tunnel. O passo 4 usa exatamente o
schema acima — validado em `tests/test_flows.py` (mesma forma de payload).
