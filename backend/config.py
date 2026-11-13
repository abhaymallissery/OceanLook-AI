# FILE: config.py - NEW (v2). One place for every optional feature switch. Set as environment variables; read on each call.
#
#   PARSER=auto|llm|rules|fast   auto = LLM first, rules as fallback (default); fast = rules first, LLM only if rules cannot read it (v5, quickest)       [Unit II / III]
#   FEWSHOT=1|0             few-shot examples inside the parsing prompt                              [Unit II]
#   MEMORY=1|0              remember earlier questions per session so follow-ups work                [Unit II / V]
#   RAG=1|0                 answer concept questions ("what is QC flag 1?") from the notes           [Unit IV]
#   AGENT=off|react         ReAct tool-using agent that can run several queries and compare them     [Unit V]
#   GUARDRAILS=1|0          input filtering (length, control chars, prompt-injection patterns)       [Unit VI]
#   OLLAMA_MODEL (v4b, first choice, local) / GEMINI_API_KEY / GROQ_API_KEY   (v4) put them in backend/.env; order: Ollama (local) -> Gemini -> Groq -> offline rules
#   LLM_TIMEOUT=6           (v4) seconds before a slow provider is skipped
#   ALLOW_SYNTHETIC=1|0     if the real data file cannot load, start on labelled SYNTHETIC demo data
import os
from pathlib import Path
from types import SimpleNamespace


# ===== NEW (v4): .env loader - keeps API keys in a private file instead of in code or in the shell =====
def load_env(path: Path = Path(__file__).with_name(".env")) -> None:
    """Read KEY=VALUE lines from backend/.env. Real environment variables win. No extra dependency."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


load_env()  # runs once, the first time anything imports config


def _on(name: str, default: bool) -> bool:
    return os.getenv(name, "1" if default else "0").strip().lower() in ("1", "true", "yes", "on")


def cfg():
    return SimpleNamespace(
        parser=os.getenv("PARSER", "auto").lower(), fewshot=_on("FEWSHOT", True), memory=_on("MEMORY", True),
        rag=_on("RAG", True), agent=os.getenv("AGENT", "off").lower(), guard=_on("GUARDRAILS", True),
        allow_synthetic=_on("ALLOW_SYNTHETIC", True))
