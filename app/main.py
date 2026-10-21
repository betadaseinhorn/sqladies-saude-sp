"""SQLadies — adaptação demonstrativa da aplicação entregue à Oracle.

API FastAPI + front-end estático do chatbot de dashboards.

Uso:  uvicorn app.main:app --reload    →  http://localhost:8000
"""
from __future__ import annotations

import logging
import math
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import dashboards, db
from app.matcher import match
from app.questions import CATALOGO, CATEGORIAS, POR_ID

STATIC = Path(__file__).resolve().parents[1] / "static"
log = logging.getLogger("sqladies")

app = FastAPI(title="SQLadies · Saúde SP", docs_url="/api/docs")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class Pergunta(BaseModel):
    text: str = Field(..., max_length=300)
    question_id: str | None = None


def _clean(o):
    """NaN/Infinity não são JSON válido."""
    if isinstance(o, float):
        return None if math.isnan(o) or math.isinf(o) else o
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if hasattr(o, "item"):  # numpy scalar
        return _clean(o.item())
    return o


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/questions")
def questions():
    return {"categorias": [
        {"nome": c, "perguntas": [{"id": q.id, "texto": q.texto, "categoria": c} for q in CATALOGO if q.categoria == c]}
        for c in CATEGORIAS]}


@app.get("/api/filters")
def filters():
    return {"anos": db.anos(),
            "drs": db.drs().to_dict("records"),
            "municipios": db.municipios()[["cod_mun", "nome", "drs_num"]].to_dict("records"),
            "capitulos": db.capitulos().to_dict("records")}


@app.post("/api/ask")
def ask(p: Pergunta):
    texto = p.text.strip()
    if not texto and not p.question_id:
        raise HTTPException(400, "Pergunta vazia")
    m = match(texto, p.question_id)
    if m.question is None:
        return {"matched": False, "params": m.params,
                "sugestoes": [{"id": q.id, "texto": q.texto} for q in m.sugestoes]}
    try:
        dash = dashboards.build(m.question.id, m.params, texto or m.question.texto)
    except Exception:  # noqa: BLE001 - devolve erro amigável ao chat
        log.exception("erro no dashboard %s %s", m.question.id, m.params)
        return JSONResponse({"matched": True, "erro": "Não consegui montar esse dashboard com os filtros "
                                                       "informados. Tente sem filtros ou com outro município."},
                            status_code=200)
    return _clean({"matched": True, "question_id": m.question.id, "pergunta": m.question.texto,
                   "score": round(m.score, 1), "params": m.params, "dashboard": dash,
                   "sugestoes": [{"id": q.id, "texto": q.texto} for q in m.sugestoes]})


@app.get("/api/health")
def health():
    return {"ok": True, "perguntas": len(POR_ID)}
