"""FILE: extras.py - NEW (v6) endpoints for the three app pages. app.py only calls install().
Chat history: GET /history, GET /history/{id}, DELETE /history/{id}.   Dashboard: GET /dashboard.
Fine-tuning: GET /tuning/status, POST /tuning/generate, POST /tuning/evaluate.
Recording of /ask is done by a middleware here, so the original /ask code is untouched."""
from __future__ import annotations

import json

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

import insights
import store
import tuning


class Gen(BaseModel):
    n: int = Field(400, ge=50, le=5000)
    seed: int = 1


class Ev(BaseModel):
    mode: str = "rules"
    limit: int = Field(20, ge=1, le=200)


def install(app: FastAPI, state: dict, get_llm) -> None:
    # ===== SECTION 1: record every /ask exchange (question + full answer) =====
    @app.middleware("http")
    async def record_asks(request: Request, call_next):
        if not (request.method == "POST" and request.url.path == "/ask"):
            return await call_next(request)
        raw = await request.body()
        resp = await call_next(request)
        body = b"".join([chunk async for chunk in resp.body_iterator])
        try:
            req = json.loads(raw)
            store.record(req.get("session_id"), str(req.get("question", "")).strip(), json.loads(body))
        except Exception:  # shortcut: history is a convenience, never let it break an answer
            pass
        return Response(content=body, status_code=resp.status_code, media_type=resp.media_type,
                        headers={k: v for k, v in resp.headers.items() if k.lower() != "content-length"})

    r = APIRouter()

    # ===== SECTION 2: history =====
    @r.get("/history")
    def history():
        return {"sessions": store.sessions()}

    @r.get("/history/{sid}")
    def history_one(sid: str):
        turns = store.session_turns(sid)
        if not turns:
            raise HTTPException(404, "no such conversation")
        return {"session_id": sid, "turns": turns}

    @r.delete("/history/{sid}")
    def history_delete(sid: str):
        return {"deleted": store.delete_session(sid)}

    # ===== SECTION 3: dashboard =====
    @r.get("/dashboard")
    def dash():
        return insights.dashboard(state["df"], store.all_turns())

    # ===== SECTION 4: fine-tuning page =====
    @r.get("/tuning/status")
    def t_status():
        return tuning.status()

    @r.post("/tuning/generate")
    def t_generate(b: Gen):
        try:
            return tuning.generate(b.n, b.seed)
        except Exception as e:
            raise HTTPException(500, str(e))

    @r.post("/tuning/evaluate")
    def t_eval(b: Ev):
        try:
            return tuning.evaluate(b.mode, b.limit, get_llm())
        except FileNotFoundError:
            raise HTTPException(400, "no validation file yet: press 'Generate training data' first")
        except ValueError as e:
            raise HTTPException(400, str(e))

    app.include_router(r)
