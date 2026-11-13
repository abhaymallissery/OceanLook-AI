"""FILE: agent.py - NEW (v2). Unit V: ReAct-style tool-using agent (Thought -> Action -> Observation, repeated), enabled with AGENT=react.
Why: one question may need several queries ("compare the Arabian Sea and the Bay of Bengal at 500 m"). The agent plans the queries,
the ENGINE answers each one, and the final text may only contain numbers that appeared in an observation (otherwise a deterministic
summary of every result is returned). The step trace is returned to the user (Unit VI explainability)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import rag
import verify
from engine import REGIONS, Query, Result, run
from llm import LLM, summarize

MAX_STEPS = 4

AGENT_SYSTEM = """You are OceanLook's analyst agent for ARGO ocean float data. You answer ONLY by calling tools. Never state a number that
no tool returned. Known regions: {regions}. Depths are in metres, dates are YYYY-MM-DD.
Tools (reply with exactly ONE JSON object per turn: {{"thought": "...", "action": "<tool>", "args": {{...}}}}):
 query_argo  args = {{"intent": "mean_at_depth"|"compare_depths"|"depth_profile"|"count_profiles", "variable": "temperature"|"salinity",
               "stat": "mean"|"median"|"min"|"max", "region": "<known region>", "start": "...", "end": "...", "depths_m": [...]}}
 search_docs args = {{"q": "<concept question>"}}
 finish      args = {{"answer": "<2-4 sentences using only numbers from observations>"}}
Use at most {steps} tool calls. If the request cannot be answered with these tools, call finish and say so."""


@dataclass
class Outcome:
    answer: str = ""
    results: list = field(default_factory=list)  # [(Query, Result)]
    docs: list = field(default_factory=list)
    trace: list = field(default_factory=list)


# ===== SECTION 1: observation text - compact, rounded JSON of a verified result (what the agent is allowed to quote) =====
def _observe(q: Query, r: Result) -> str:
    return json.dumps({"query": q.model_dump(mode="json", exclude={"bbox", "max_gap_m"}), "status": r.status, "unit": r.unit,
                       "values": [{"depth_m": s.depth_m, "value": None if s.value is None else f"{s.value:.2f}",  # strings so "18.00" stays "18.00"
                                   "profiles": s.n_profiles} for s in r.series[:6]],
                       "difference": None if r.difference is None else f"{r.difference:+.2f}",
                       "profiles_in_scope": r.n_profiles_in_scope, "floats_in_scope": r.n_floats_in_scope, "caveats": r.caveats[-2:]})


# ===== SECTION 2: number guard - the final answer may only contain numbers found in observations =====
def _numbers_ok(answer: str, seen: str) -> bool:
    return all(n in seen for n in re.findall(r"\d+(?:\.\d+)?", re.sub(r"(?<=\d),(?=\d{3})", "", answer)))


# ===== SECTION 3: the loop =====
def run_agent(question: str, df, llm: LLM) -> Outcome:
    out, seen = Outcome(), question
    system = AGENT_SYSTEM.format(regions=", ".join(sorted(REGIONS)), steps=MAX_STEPS)
    transcript = f"Question: {question}"
    for step in range(1, MAX_STEPS + 2):
        try:
            msg = json.loads(llm(system, transcript, True))
            action, args = msg["action"], msg.get("args", {})
        except Exception as e:
            out.trace.append(f"step {step}: could not read the agent's reply ({type(e).__name__})")
            break
        out.trace.append(f"step {step}: {msg.get('thought', '')} -> {action}")
        if action == "finish":
            ans = str(args.get("answer", ""))
            if ans and _numbers_ok(ans, seen):
                out.answer = ans
            else:
                out.trace.append("final answer contained a number no tool returned; using deterministic summaries instead")
            break
        if step > MAX_STEPS:
            break
        if action == "query_argo":
            try:
                q = Query.model_validate(args)
                r = verify.verify(q, run(df, q))
                out.results.append((q, r))
                obs = _observe(q, r)
            except Exception as e:
                obs = f"error: {str(e)[:300]}"  # the agent sees validation errors and can correct itself
        elif action == "search_docs":
            hits = rag.search(str(args.get("q", "")))
            out.docs += hits
            obs = json.dumps([{"title": h["title"], "text": h["text"][:500]} for h in hits]) or "no match"
        else:
            obs = f"error: unknown tool '{action}'"
        seen += " " + obs
        transcript += f"\nAction: {json.dumps(msg)}\nObservation: {obs}"
    if not out.answer:
        out.answer = " ".join(summarize(r, q) for q, r in out.results) or (out.docs[0]["text"] if out.docs else
                                                                          "The agent could not answer this question with the available tools.")
    return out
