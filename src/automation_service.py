"""API de automação do processo (FastAPI).

- POST /automate/validate  -> aplica as regras de conferência em um documento sintético
- POST /automate/batch     -> valida uma lista de documentos e resume o resultado
- GET  /process/kpis       -> KPIs do process mining (arquivo gerado por src.mining)
- GET  /healthz            -> liveness
Requer fastapi/uvicorn (ver requirements.txt). O núcleo de regras/mineração roda só com stdlib.
"""
from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.rules import RuleError, validate_document

app = FastAPI(
    title="Business Process Automation Lab API",
    version="1.0.0",
    description="Contrato HTTP consumido pelos fluxos low-code (n8n / Power Automate).",
)


class Document(BaseModel):
    document_number: str = Field(..., examples=["NF-10231"])
    cnpj: str = Field(..., examples=["11222333000181"])
    amount: str | float = Field(..., examples=["1.234,56"])
    expected_amount: str | float | None = Field(default=None, examples=["1.200,00"])
    issued_at: str = Field(..., examples=["2026-06-01"])
    due_date: str = Field(..., examples=["2026-06-30"])


class BatchRequest(BaseModel):
    documents: list[Document]


def _validate_payload(payload: dict) -> dict[str, Any]:
    try:
        return validate_document(payload)
    except RuleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/automate/validate")
def validate(document: Document) -> dict:
    return _validate_payload(document.model_dump())


@app.post("/automate/batch")
def batch(request: BatchRequest) -> dict:
    results = []
    for doc in request.documents:
        result = _validate_payload(doc.model_dump())
        results.append({"document_number": doc.document_number, **{k: result[k] for k in ("status", "needs_human_review", "divergences")}})
    approved = sum(1 for r in results if not r["needs_human_review"])
    return {
        "total": len(results),
        "approved_automatically": approved,
        "sent_to_human_review": len(results) - approved,
        "automation_rate": round(approved / max(1, len(results)), 4),
        "results": results,
    }


@app.get("/process/kpis")
def kpis() -> dict:
    path = os.environ.get("MINING_REPORT", "reports/mining.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"rode `make mining` primeiro ({path} não existe)")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
