# FILE: guardrails.py - NEW (v2). Unit VI: input safety / prompt filtering. Runs BEFORE any text reaches an LLM.
import re

from errors import Blocked

MAX_CHARS = 500
# shortcut: pattern list, not a classifier. It catches common override phrases, not every possible attack.
INJECTION = re.compile(
    r"ignore (all|any|the|your|previous|above)|disregard (all|the|your|previous)|system prompt|you are now|"
    r"act as|reveal .{0,30}(prompt|key|instruction)|jailbreak|developer mode", re.I)


# ===== SECTION: check_input - clean and validate one user question =====
def check_input(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", text or "").strip()  # drop control characters
    if not text:
        raise Blocked("Please type a question.")
    if len(text) > MAX_CHARS:
        raise Blocked(f"Question is too long ({len(text)} characters; limit {MAX_CHARS}).")
    if INJECTION.search(text):
        raise Blocked("That looks like an attempt to change the assistant's instructions. Ask an ocean-data question instead.")
    return text
