"""FILE: tuning.py - NEW (v6) FINE-TUNING PAGE LOGIC (Unit III).
Fine-tuning only improves how well the model READS a question. It cannot change the science, which engine.py already computes exactly.
This file does four things: (1) report what is in data/finetune, (2) make the training data, (3) score a parser on held-out questions,
(4) remember every score so the page can show base model vs tuned model."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import llm
from engine import Query
from errors import Unsupported

DIR = Path("data/finetune")
RUNS = DIR / "eval_runs.json"
MODES = ("rules", "fast", "llm")


# ===== SECTION 1: what exists now =====
def _lines(p: Path) -> int:
    return sum(1 for _ in p.open(encoding="utf-8")) if p.is_file() else 0


def runs() -> list[dict]:
    return json.loads(RUNS.read_text()) if RUNS.is_file() else []


def model_name() -> str:
    """The model that would answer in 'llm' mode: the first configured provider."""
    if os.getenv("OLLAMA_MODEL"):
        return "ollama:" + os.environ["OLLAMA_MODEL"]
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return "gemini:" + os.getenv("GEMINI_MODEL", "default")
    return "groq:" + os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile") if os.getenv("GROQ_API_KEY") else "none"


def status() -> dict:
    return {"train_rows": _lines(DIR / "train.jsonl"), "val_rows": _lines(DIR / "val.jsonl"), "ready": (DIR / "val_cases.json").is_file(),
            "model": model_name(), "llm_available": llm.has_llm(), "runs": runs()[-8:][::-1]}


# ===== SECTION 2: make the training data (runs make_finetune_data.py exactly as on the command line) =====
def generate(n: int, seed: int = 1) -> dict:
    p = subprocess.run([sys.executable, "make_finetune_data.py", "--n", str(n), "--seed", str(seed), "--out", str(DIR)],
                       capture_output=True, text=True, timeout=120)
    if p.returncode:
        raise RuntimeError(p.stderr.strip()[-300:] or "make_finetune_data.py failed")
    return {"message": p.stdout.strip(), **status()}


# ===== SECTION 3: score a parser on the held-out questions (phrasings that are NOT in the training file) =====
def _same(a: Query, want: dict) -> bool:
    drop = {"max_gap_m"}
    return a.model_dump(mode="json", exclude=drop) == Query(**want).model_dump(mode="json", exclude=drop)


def evaluate(mode: str, limit: int, llm_fn) -> dict:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if mode == "llm" and llm_fn is None:
        raise ValueError("no language model is configured (set OLLAMA_MODEL, GEMINI_API_KEY or GROQ_API_KEY in backend/.env)")
    cases = json.loads((DIR / "val_cases.json").read_text())[:limit]
    ok, bad, t0 = 0, [], time.perf_counter()
    for c in cases:
        want = c["expected"]
        try:
            q, _ = llm.parse_auto(c["question"], llm_fn, None, mode)
            good = "unsupported" not in want and _same(q, want)
            got = q.model_dump(mode="json", exclude={"max_gap_m"})
        except Unsupported:
            good, got = "unsupported" in want, "unsupported"
        except Exception as e:  # model down, bad JSON ...
            good, got = False, f"{type(e).__name__}"
        ok += good
        if not good and len(bad) < 5:
            bad.append({"question": c["question"], "expected": want, "got": got})
    n = len(cases)
    run = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mode": mode, "model": model_name() if mode != "rules" else "rules",
           "n": n, "correct": ok, "accuracy": round(ok / n, 3) if n else 0.0, "avg_ms": round((time.perf_counter() - t0) * 1000 / max(n, 1), 1)}
    DIR.mkdir(parents=True, exist_ok=True)
    RUNS.write_text(json.dumps((runs() + [run])[-50:], indent=1))
    return {**run, "failures": bad, **status()}
