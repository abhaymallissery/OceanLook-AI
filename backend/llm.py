"""FILE: llm.py - Stage 1 (question -> validated Query) and Stage 3 (verified Result -> plain English).
The LLM never computes or recalls science. v2 CHANGES are marked 'CHANGED (v2)'."""
from __future__ import annotations

import json
import os
import time
from datetime import date
from typing import Callable

from pydantic import ValidationError

import config  # NEW (v4): loads backend/.env before any key is read
from engine import REGIONS, Query, Result
from errors import Unsupported  # CHANGED (v2): moved to errors.py (re-exported here so llm.Unsupported still works)
from rules import parse_rules, parse_smart

LLM = Callable[[str, str, bool], str]  # (system, user, json_mode) -> text


# ===== SECTION 1: Gemini client - the only place that talks to the model =====
def gemini(system: str, user: str, json_mode: bool) -> str:
    from google import genai
    from google.genai import types
    cfg = types.GenerateContentConfig(system_instruction=system, temperature=0,
                                      response_mime_type="application/json" if json_mode else "text/plain",
                                      http_options=types.HttpOptions(timeout=int(_timeout() * 1000)))  # CHANGED (v4): fail fast
    r = genai.Client().models.generate_content(  # reads GEMINI_API_KEY
        model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"), contents=user, config=cfg)  # GEMINI_MODEL may name a tuned model
    return r.text


# ===== NEW (v4) SECTION 1b: Groq client (OpenAI-compatible HTTP, uses httpx which is already installed) + fallback router =====
def _timeout() -> float:
    return float(os.environ.get("LLM_TIMEOUT", "6"))


def groq(system: str, user: str, json_mode: bool) -> str:
    import httpx
    body = {"model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"), "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = httpx.post("https://api.groq.com/openai/v1/chat/completions", json=body, timeout=_timeout(),
                   headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def ollama(system: str, user: str, json_mode: bool) -> str:
    """NEW (v4b): local model through Ollama (no key, no internet). Needs `ollama serve` and `ollama pull <OLLAMA_MODEL>`."""
    import httpx
    body = {"model": os.environ["OLLAMA_MODEL"], "stream": False, "options": {"temperature": 0},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if json_mode:
        body["format"] = "json"
    r = httpx.post(os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/") + "/api/chat", json=body,
                   timeout=float(os.environ.get("OLLAMA_TIMEOUT", "15")))  # longer than cloud: the first call loads the model
    r.raise_for_status()
    return r.json()["message"]["content"]


def _providers() -> list[tuple[str, LLM]]:
    """Providers that are configured, in priority order: Ollama (local), Gemini, Groq."""
    out = []
    if os.getenv("OLLAMA_MODEL"):  # CHANGED (v4b): Ollama is the first option
        out.append(("ollama", ollama))
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        out.append(("gemini", gemini))
    if os.getenv("GROQ_API_KEY"):
        out.append(("groq", groq))
    return out


_DOWN: dict[str, float] = {}  # provider -> time until which it is skipped after a failure
COOLDOWN_S = 60  # shortcut: fixed 60 s pause after a failure; upgrade to exponential back-off if needed.


def has_llm() -> bool:
    return bool(_providers())


def chat(system: str, user: str, json_mode: bool) -> str:
    """Gemini first, Groq second. A failed provider is skipped for COOLDOWN_S so later questions stay fast.
    If all fail this raises, and parse_auto / explain fall back to the offline rules and the deterministic text."""
    err: Exception = RuntimeError("no LLM key set")
    for name, fn in _providers():
        if _DOWN.get(name, 0) > time.time():
            continue
        try:
            return fn(system, user, json_mode)
        except Exception as e:  # network, quota, bad key, timeout
            _DOWN[name] = time.time() + COOLDOWN_S
            err = e
    raise err


# ===== SECTION 2: prompts - zero-shot instructions plus optional few-shot examples (Unit II) =====
PARSE_SYSTEM = """You convert a scientist's question about ARGO ocean float data into JSON. Return ONLY JSON, never an answer.
Today is {today}. Known regions: {regions}.
Schema: {{"intent": "mean_at_depth"|"compare_depths"|"depth_profile"|"count_profiles",
 "variable": "temperature"|"salinity", "stat": "mean"|"median"|"min"|"max",
 "region": <one known region name, or null>, "bbox": [lat_min, lat_max, lon_min, lon_max] or null,
 "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "depths_m": [numbers in metres]}}
Rules: mean_at_depth has exactly 1 depth; compare_depths exactly 2 (in the order mentioned); depth_profile and count_profiles have none.
Use "region" only for a known region. Use "bbox" only if the user gave coordinates. Never invent coordinates.
A year means Jan 1 to Dec 31. Default stat is mean, default variable is temperature.
If the question needs anything else (other variables, floats' trajectories, forecasts, opinions, regions not listed with no coordinates),
return {{"unsupported": "<short reason>"}}."""

# CHANGED (v2): few-shot examples (Unit II). Switch off with FEWSHOT=0 to measure the difference with eval_run.py.
FEWSHOT = """
Examples:
Q: Average temperature at 500 m in the Arabian Sea in 2024?
A: {"intent":"mean_at_depth","variable":"temperature","stat":"mean","region":"arabian sea","bbox":null,"start":"2024-01-01","end":"2024-12-31","depths_m":[500]}
Q: How many profiles in the Bay of Bengal in March 2024?
A: {"intent":"count_profiles","variable":"temperature","stat":"mean","region":"bay of bengal","bbox":null,"start":"2024-03-01","end":"2024-03-31","depths_m":[]}
Q: Will the Arabian Sea be warmer next year?
A: {"unsupported":"forecasts are not supported"}"""

HISTORY = """
Earlier queries in this conversation (oldest first). If the new question is a follow-up such as "and for salinity?" or "what about 1000 m?",
copy these and change ONLY what the user changes:
{history}"""

EXPLAIN_SYSTEM = """You explain verified ARGO results to a scientist in 2-4 plain sentences. Use ONLY the numbers in the JSON given.
Quote the headline numbers exactly as written in deterministic_summary. Mention the number of profiles and floats and any caveat.
Do not add outside facts, comparisons to climatology, causes, or trends."""


# ===== SECTION 3: Stage 1 parsing - LLM first, offline rules as fallback =====
def parse_question(question: str, llm: LLM = gemini, history: list[dict] | None = None, fewshot: bool = True) -> Query:
    system = PARSE_SYSTEM.format(today=date.today().isoformat(), regions=", ".join(sorted(REGIONS)))
    if fewshot:
        system += FEWSHOT
    if history:  # CHANGED (v2): conversation memory (Unit II/V)
        system += HISTORY.format(history="\n".join(json.dumps(h) for h in history))
    raw = json.loads(llm(system, question, True))
    if "unsupported" in raw:
        raise Unsupported(raw["unsupported"])
    return Query.model_validate(raw)  # ValidationError = the LLM produced something the engine cannot run


def parse_auto(question: str, llm: LLM | None, history=None, mode: str = "auto", fewshot: bool = True) -> tuple[Query, str]:
    """CHANGED (v2): returns (query, which_parser_was_used). mode: auto | llm | rules | fast.
    NEW (v5) fast = rules first (milliseconds, no model call); the LLM is used only when the rules cannot read the question."""
    if mode == "fast":
        try:
            return parse_rules(question), "rules"
        except Unsupported:
            if llm is not None:
                try:
                    return parse_question(question, llm, history, fewshot), "llm"
                except Exception:
                    pass
            return parse_smart(question, history), "rules"
    if mode == "rules" or (mode == "auto" and llm is None):
        try:
            return parse_rules(question), "rules"
        except Unsupported:
            return parse_smart(question, history), "rules"
    if mode == "llm" and llm is None:
        raise RuntimeError("PARSER=llm but no OLLAMA_MODEL, GEMINI_API_KEY or GROQ_API_KEY is set")
    try:
        return parse_question(question, llm, history, fewshot), "llm"
    except Unsupported:
        raise  # the LLM understood the question and said it cannot be answered
    except Exception:
        if mode == "llm":
            raise
        try:
            return parse_rules(question), "rules"
        except Unsupported:
            return parse_smart(question, history), "rules"


# ===== SECTION 4: deterministic summary - the answer text built only from verified numbers =====
def _f(v: float) -> str:
    return f"{v:.2f}"


def summarize(r: Result, q: Query) -> str:
    where = q.region.title() if q.region else "the requested area"
    when = f"between {q.start} and {q.end}"
    tag = " [Synthetic demo data, not real measurements.]" if "SYNTHETIC" in r.source.upper() else ""  # CHANGED (v2)
    if r.status == "unverified":  # CHANGED (v2)
        return "The computed result failed its verification checks, so it is not shown. " + " ".join(r.caveats[-1:]) + tag
    if r.status == "no_data":
        return f"No usable observations were found for {where} {when} in the loaded ARGO subset." + tag
    n = f"{r.n_profiles_in_scope} profiles from {r.n_floats_in_scope} floats"
    if q.intent == "count_profiles":
        return f"There are {n} in {where} {when}." + tag
    if q.intent == "depth_profile":
        good = [s for s in r.series if s.value is not None]
        a, b = good[0], good[-1]
        return (f"The {q.stat} {q.variable} profile for {where} {when} ({n}) runs from {_f(a.value)} {r.unit} at "
                f"{a.depth_m:g} m to {_f(b.value)} {r.unit} at {b.depth_m:g} m." + tag)
    s = r.series[0]
    sd = f", standard deviation {_f(s.std)} {r.unit}" if s.std is not None else ""
    if q.intent == "mean_at_depth":
        return (f"The {q.stat} {q.variable} at {s.depth_m:g} m in {where} {when} was {_f(s.value)} {r.unit}{sd}, "
                f"from {s.n_profiles} usable profiles ({s.n_floats} floats) out of {r.n_profiles_in_scope} in scope." + tag)
    s2 = r.series[1]
    return (f"The {q.stat} {q.variable} in {where} {when} was {_f(s.value)} {r.unit} at {s.depth_m:g} m and "
            f"{_f(s2.value)} {r.unit} at {s2.depth_m:g} m, a difference of {r.difference:+.2f} {r.unit} "
            f"({s2.depth_m:g} m minus {s.depth_m:g} m). Based on {s.n_profiles} and {s2.n_profiles} usable profiles." + tag)


# ===== SECTION 5: Stage 3 explanation - LLM may rephrase, but only if it keeps every verified number =====
def _must_contain(r: Result) -> list[str]:
    if r.intent in ("mean_at_depth", "compare_depths"):
        return [_f(s.value) for s in r.series] + ([f"{r.difference:+.2f}"] if r.difference is not None else [])
    return [str(r.n_profiles_in_scope)]


def explain(q: Query, r: Result, llm: LLM | None = gemini) -> str:
    base = summarize(r, q)
    if llm is None or r.status != "ok":
        return base
    try:
        payload = r.model_dump(exclude={"observations", "curve"})
        text = llm(EXPLAIN_SYSTEM, json.dumps({"result": payload, "deterministic_summary": base}, default=str), False).strip()
    except Exception:
        return base
    # shortcut: only the headline numbers are checked; upgrade to checking every number in the text.
    if not (text and all(m in text for m in _must_contain(r))):
        return base
    if "SYNTHETIC" in r.source.upper() and "synthetic" not in text.lower():  # CHANGED (v2): the label can never be dropped
        text += " [Synthetic demo data, not real measurements.]"
    return text
