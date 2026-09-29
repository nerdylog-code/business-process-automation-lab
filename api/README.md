O spec OpenAPI **não é escrito à mão**: ele é gerado pelo próprio FastAPI (fonte única).

```bash
make openapi   # escreve api/openapi.json a partir de src/automation_service.py
```

Teste que garante que as rotas documentadas existem de fato: `tests/test_flows.py`.
