# FILE: rag.py - NEW (v2). Unit IV: retrieval-augmented generation over a small knowledge base (chunking -> index -> retrieval).
# Sparse BM25 scoring instead of dense embeddings: no model download, fully offline, easy to inspect.
# shortcut: upgrade to dense embeddings (e.g. Gemini embeddings + a vector DB such as Chroma/FAISS) if the notes grow large.
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from engine import REGIONS

NOTES = Path(__file__).parent / "knowledge" / "argo_notes.md"
STOP = set("the a an of in on at to is are was what does do how why and or for with by it its this that be as from".split())


def _tok(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP]


# ===== SECTION: chunking + index - one chunk per "## heading" section of the notes file =====
@lru_cache(maxsize=1)
def _index(path: str = str(NOTES)):
    chunks = []
    for block in Path(path).read_text(encoding="utf8").split("\n## ")[1:]:
        title, _, body = block.partition("\n")
        chunks.append({"title": title.strip(), "text": body.strip()})
    docs = [Counter(_tok(c["title"] + " " + c["title"] + " " + c["text"])) for c in chunks]  # title counted twice = small boost
    df = Counter(w for d in docs for w in d)
    return chunks, docs, df, sum(sum(d.values()) for d in docs) / len(docs)


# ===== SECTION: search - BM25 ranking, returns the best chunks with scores =====
def search(query: str, k: int = 2, k1: float = 1.5, b: float = 0.75) -> list[dict]:
    chunks, docs, df, avg = _index()
    q, n, out = _tok(query), len(chunks), []
    for c, d in zip(chunks, docs):
        dl = sum(d.values())
        s = sum(math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5)) * d[w] * (k1 + 1) / (d[w] + k1 * (1 - b + b * dl / avg))
                for w in q if w in d)
        if s > 0:
            out.append({**c, "score": round(s, 3), "source": "OceanLook notes (Argo User's Manual / argo.ucsd.edu)"})
    return sorted(out, key=lambda x: -x["score"])[:k]


# ===== SECTION: routing gate - is this a concept question rather than a data question? =====
_CONCEPT = re.compile(r"^\s*(what|why|how|explain|define|tell me about|describe)\b", re.I)
# CHANGED (v2): only "how many"/"number of" and a number with a depth unit mark a data question (digits like "QC flag 1" do not)
_DATA_WORDS = re.compile(r"\bhow many\b|\bnumber of\b|\d[\d,]*\s*(?:m\b|metres?|meters?|dbar)", re.I)


def is_concept_question(q: str) -> bool:
    low = q.lower()
    return bool(_CONCEPT.match(q)) and not _DATA_WORDS.search(q) and not any(r in low for r in REGIONS)
