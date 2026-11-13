# FILE: memory.py - NEW (v2). Unit II/V: agent memory and state. Remembers the last few validated queries per session.
from collections import OrderedDict, deque

# shortcut: in-process dict (lost on restart, not shared between workers). Upgrade to Redis/PostgreSQL for real deployment.
_SESSIONS: "OrderedDict[str, deque]" = OrderedDict()
MAX_SESSIONS, KEEP = 1000, 3


# ===== SECTION: remember / recall =====
def remember(session_id: str | None, query_json: dict) -> None:
    if not session_id:
        return
    _SESSIONS.setdefault(session_id, deque(maxlen=KEEP)).append(query_json)
    _SESSIONS.move_to_end(session_id)
    while len(_SESSIONS) > MAX_SESSIONS:
        _SESSIONS.popitem(last=False)  # evict the least recently used session


def recall(session_id: str | None) -> list[dict]:
    return list(_SESSIONS.get(session_id, [])) if session_id else []
