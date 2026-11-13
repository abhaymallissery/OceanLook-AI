"""FILE: app.py - FastAPI backend that wires every stage together.
POST /ask = full pipeline; POST /query = run a structured Query (no LLM); GET /health.
v2 CHANGES are marked 'CHANGED (v2)'."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError

import config  # noqa: F401  NEW (v4): loads backend/.env first
import agent
import guardrails
import llm
import memory
import rag
import verify
from config import cfg
from engine import REGIONS, Query, Result, load_table, run
from errors import Blocked, Unsupported
from synthetic_demo import make_demo_data

STATE: dict = {"df": None, "error": None, "note": ""}
# CHANGED (v2): no key -> no LLM object at all, so PARSER=auto goes straight to the offline rule parser instead of failing per request.
llm_fn: llm.LLM | None = llm.chat if llm.has_llm() else None  # CHANGED (v4): Gemini, then Groq; tests replace this


# ===== SECTION 1: start-up - load real data; CHANGED (v2): fall back to labelled SYNTHETIC data if it cannot be loaded =====
@asynccontextmanager
async def lifespan(_):
    path = os.environ.get("ARGO_DATA", "data/argo_subset.csv.gz")
    try:
        STATE["df"], STATE["error"], STATE["note"] = load_table(path), None, ""
    except Exception as e:
        if cfg().allow_synthetic:
            STATE["df"], STATE["error"] = make_demo_data(), None
            STATE["note"] = f"Real data not loaded ({e}). Running on SYNTHETIC demo data."
        else:
            STATE["df"], STATE["error"] = None, f"Could not load {path}: {e}"
    yield


app = FastAPI(title="OceanLook", lifespan=lifespan)
# shortcut: open CORS for local development; restrict origins before deploying.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ===== SECTION 2: request/response schema =====
class Ask(BaseModel):
    question: str
    session_id: Optional[str] = None  # CHANGED (v2): enables conversation memory


class Answer(BaseModel):
    status: str  # ok | no_data | unverified | docs | unsupported | blocked | error
    message: str = ""
    interpretation: Optional[Query] = None
    result: Optional[Result] = None
    explanation: str = ""
    # CHANGED (v2): fields below support the optional modules
    synthetic: bool = False
    parser_used: str = ""
    docs: list[dict] = []     # RAG passages (Unit IV)
    steps: list[str] = []     # agent trace (Unit V/VI)
    extra: list[dict] = []    # further queries run by the agent


# ===== SECTION 3: helpers - finish a Query (run -> verify -> explain), and the docs path =====
def _finish(q: Query) -> Answer:
    r = verify.verify(q, run(STATE["df"], q))  # CHANGED (v2): verification stage added
    return Answer(status=r.status, interpretation=q, result=r, explanation=llm.explain(q, r, llm_fn),
                  synthetic="SYNTHETIC" in r.source.upper())


def _docs_answer(text: str) -> Answer:
    hits = rag.search(text)
    if not hits:
        return Answer(status="unsupported", message="No relevant note found. Try asking about QC flags, data modes, units or the method.")
    return Answer(status="docs", explanation=hits[0]["text"], docs=hits)


def _agent_answer(text: str) -> Answer:
    out = agent.run_agent(text, STATE["df"], llm_fn)
    if out.results:
        (q, r), rest = out.results[0], out.results[1:]
        status = "ok" if any(x.status == "ok" for _, x in out.results) else r.status
        return Answer(status=status, interpretation=q, result=r, explanation=out.answer, steps=out.trace, docs=out.docs,
                      extra=[{"interpretation": a.model_dump(mode="json"), "result": b.model_dump()} for a, b in rest],
                      synthetic="SYNTHETIC" in r.source.upper(), parser_used="agent")
    return Answer(status="docs" if out.docs else "unsupported", explanation=out.answer, steps=out.trace, docs=out.docs, parser_used="agent")


# ===== SECTION 4: endpoints =====
@app.get("/health")
def health():
    df, c = STATE["df"], cfg()
    options = {"parser": c.parser, "fewshot": c.fewshot, "memory": c.memory, "rag": c.rag, "agent": c.agent,
               "guardrails": c.guard, "llm_available": llm_fn is not None}  # CHANGED (v2)
    if df is None:
        return {"loaded": False, "error": STATE["error"], "regions": sorted(REGIONS), "options": options}
    src = ", ".join(sorted(df["source"].unique()))
    return {"loaded": True, "rows": len(df), "profiles": int(df.groupby(["platform_number", "cycle_number"]).ngroups),
            "floats": int(df["platform_number"].nunique()), "time_min": df["time"].min().isoformat(),
            "time_max": df["time"].max().isoformat(), "source": src, "synthetic": "SYNTHETIC" in src.upper(),
            "note": STATE["note"], "regions": sorted(REGIONS), "options": options}


@app.post("/query", response_model=Answer)
def query(q: Query):
    if STATE["df"] is None:
        return Answer(status="error", message=STATE["error"])
    return _finish(q)


@app.post("/ask", response_model=Answer)
def ask(body: Ask):
    c = cfg()
    if STATE["df"] is None:
        return Answer(status="error", message=STATE["error"])
    try:  # CHANGED (v2): guardrail runs first
        text = guardrails.check_input(body.question) if c.guard else body.question.strip()
    except Blocked as e:
        return Answer(status="blocked", message=str(e))
    if c.agent == "react" and llm_fn is not None:  # CHANGED (v2): optional agent route
        return _agent_answer(text)
    if c.rag and rag.is_concept_question(text):  # CHANGED (v2): optional RAG route
        return _docs_answer(text)
    try:
        history = memory.recall(body.session_id) if c.memory else []
        q, used = llm.parse_auto(text, llm_fn, history, c.parser, c.fewshot)
    except Unsupported as e:
        return Answer(status="unsupported", message=f"This question is outside what OceanLook can answer: {e}")
    except ValidationError as e:
        return Answer(status="unsupported", message="Could not turn the question into a runnable query: "
                      + "; ".join(x["msg"] for x in e.errors()))
    except Exception as e:
        return Answer(status="error", message=f"Language model unavailable: {type(e).__name__}: {e}")
    a = _finish(q)
    a.parser_used = used
    if c.memory and a.status in ("ok", "no_data"):
        memory.remember(body.session_id, q.model_dump(mode="json"))
    return a


# ===== NEW (v6): history, dashboard and fine-tuning endpoints are in extras.py (the code above is unchanged) =====
import extras  # noqa: E402

extras.install(app, STATE, lambda: llm_fn)
