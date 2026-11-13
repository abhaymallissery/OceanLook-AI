"""FILE: store.py - NEW (v6) CHAT HISTORY STORE.
Every /ask exchange is saved in a small SQLite file (default data/floatchat.db, change with HISTORY_DB).
SQLite is in the Python standard library, so no new dependency. Used by the History sheet and by the Dashboard."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

_lock = threading.Lock()


# ===== SECTION 1: connection - the table is created on first use =====
def _conn() -> sqlite3.Connection:
    p = Path(os.environ.get("HISTORY_DB", "data/floatchat.db"))
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p)
    c.row_factory = sqlite3.Row
    c.execute("create table if not exists turns(id integer primary key autoincrement, session_id text, ts text, question text,"
              " status text, intent text, variable text, region text, preview text, answer text)")
    c.execute("create index if not exists ix_turns_session on turns(session_id)")
    return c


# ===== SECTION 2: write =====
def record(session_id: str | None, question: str, ans: dict) -> None:
    """Save one question and its full answer (the answer JSON lets the app redraw the card when a chat is resumed)."""
    it = ans.get("interpretation") or {}
    preview = (ans.get("explanation") or ans.get("message") or "")[:200]
    with _lock, closing(_conn()) as c, c:
        c.execute("insert into turns(session_id, ts, question, status, intent, variable, region, preview, answer) values(?,?,?,?,?,?,?,?,?)",
                  (session_id or "anonymous", datetime.now(timezone.utc).isoformat(timespec="seconds"), question, ans.get("status", ""),
                   it.get("intent"), it.get("variable"), it.get("region"), preview, json.dumps(ans)))


def delete_session(session_id: str) -> int:
    with _lock, closing(_conn()) as c, c:
        return c.execute("delete from turns where session_id=?", (session_id,)).rowcount


# ===== SECTION 3: read =====
def all_turns() -> list[dict]:
    """Light rows (no answer JSON), oldest first. Used by the dashboard."""
    with closing(_conn()) as c:
        rows = c.execute("select id, session_id, ts, question, status, intent, variable, region, preview from turns order by id").fetchall()
    return [dict(r) for r in rows]


def sessions(limit: int = 50) -> list[dict]:
    """One entry per conversation, newest first: title = first question, topic tag, count, preview of the last answer."""
    by: dict[str, list[dict]] = {}
    for t in all_turns():
        by.setdefault(t["session_id"], []).append(t)
    out = []
    for sid, ts in by.items():
        first, last = ts[0], ts[-1]
        tag = "Concepts" if first["status"] == "docs" else (first["variable"] or "General").title()
        out.append({"session_id": sid, "title": first["question"], "tag": tag, "region": first["region"] or "",
                    "messages": len(ts) * 2, "started": first["ts"], "last": last["ts"], "preview": last["preview"], "status": last["status"]})
    out.sort(key=lambda s: s["last"], reverse=True)
    return out[:limit]


def session_turns(session_id: str) -> list[dict]:
    with closing(_conn()) as c:
        rows = c.execute("select ts, question, answer from turns where session_id=? order by id", (session_id,)).fetchall()
    return [{"ts": r["ts"], "question": r["question"], "answer": json.loads(r["answer"])} for r in rows]
