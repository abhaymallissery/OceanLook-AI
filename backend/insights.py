"""FILE: insights.py - NEW (v6) DASHBOARD LOGIC.
Builds the Research Hub page from two things only: the chat history (store.py) and the loaded ARGO table.
No language model is used here, so the dashboard is instant and every number can be traced."""
from __future__ import annotations

import calendar

import pandas as pd

from engine import REGIONS

# Questions the dashboard may recommend when the user has not tried that kind yet. {when} = a period that exists in the loaded data.
_CONCEPTS = "What are the Argo data modes R, A and D?"


# ===== SECTION 1: data-side numbers (coverage, quality, hotspots) =====
def _profiles(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop_duplicates(["platform_number", "cycle_number"])


def data_metrics(df: pd.DataFrame) -> dict:
    p = _profiles(df)
    t = df["temp"].notna()
    qc = float((df.loc[t, "temp_qc"] == 1).mean() * 100) if t.any() else 0.0
    return {"profiles": int(len(p)), "floats": int(df["platform_number"].nunique()), "qc_good_pct": round(qc, 1),
            "deepest_dbar": round(float(df["pres"].max()), 0), "source": ", ".join(sorted(df["source"].unique())),
            "synthetic": "SYNTHETIC" in " ".join(df["source"].unique()).upper(),
            "time_min": df["time"].min().date().isoformat(), "time_max": df["time"].max().date().isoformat()}


def hotspots(df: pd.DataFrame, top: int = 3) -> list[dict]:
    """Regions with the most profiles in the loaded data, with the centre of their profiles. 'indian ocean' (everything) is skipped."""
    p, out = _profiles(df), []
    for name, (la0, la1, lo0, lo1) in REGIONS.items():
        if name == "indian ocean":
            continue
        s = p[p.latitude.between(la0, la1) & p.longitude.between(lo0, lo1)]
        if len(s):
            out.append({"region": name.title(), "profiles": int(len(s)), "floats": int(s.platform_number.nunique()),
                        "lat": round(float(s.latitude.mean()), 1), "lon": round(float(s.longitude.mean()), 1)})
    return sorted(out, key=lambda x: x["profiles"], reverse=True)[:top]


def _when(df: pd.DataFrame) -> str:
    """A period phrase that the loaded data really covers ('January 2024' for one month, '2024' otherwise)."""
    a, b = df["time"].min(), df["time"].max()
    if (a.year, a.month) == (b.year, b.month):
        return f"{calendar.month_name[a.month]} {a.year}"
    return str(b.year)


# ===== SECTION 2: history-side numbers (focus, topics, answer rate) =====
def _label(t: dict) -> str | None:
    if t["status"] == "docs":
        return "Concepts & QC notes"
    if t["region"] and t["variable"]:
        return f"{t['region'].title()} · {t['variable']}"
    return None


def topics(turns: list[dict], top: int = 4) -> list[dict]:
    counts: dict[str, int] = {}
    for t in turns:
        lab = _label(t)
        if lab:
            counts[lab] = counts.get(lab, 0) + 1
    total = sum(counts.values())
    return [{"label": k, "count": v, "pct": round(v * 100 / total)} for k, v in sorted(counts.items(), key=lambda kv: -kv[1])[:top]]


def summary(turns: list[dict], tp: list[dict]) -> str:
    """The short plain-English summary on top of the dashboard."""
    if not turns:
        return "No questions yet. Ask your first question in Chat; this page then learns what you study and suggests what to look at next."
    sessions = len({t["session_id"] for t in turns})
    answered = [t for t in turns if t["status"] in ("ok", "no_data", "unverified", "docs")]
    ok = sum(t["status"] in ("ok", "docs") for t in turns)
    s = f"You asked {len(turns)} question{'s' * (len(turns) != 1)} in {sessions} conversation{'s' * (sessions != 1)}. "
    if tp:
        s += f"{tp[0]['pct']}% of them were about {tp[0]['label']}. "
    s += f"{ok} of {len(answered) or len(turns)} got a verified answer"
    miss = len(turns) - len(answered)
    return s + (f"; {miss} could not be answered (outside scope or blocked)." if miss else ".")


# ===== SECTION 3: recommendations - rule based, so each one explains itself =====
def recommendations(df: pd.DataFrame, turns: list[dict], limit: int = 4) -> list[dict]:
    when, recs = _when(df), []
    asked_regions = {t["region"] for t in turns if t["region"]}
    asked_vars = {t["variable"] for t in turns if t["variable"]}
    asked_intents = {t["intent"] for t in turns if t["intent"]}
    for h in hotspots(df, 3):  # 1) a region with data that you have not looked at
        if h["region"].lower() not in asked_regions:
            recs.append({"tag": "UNEXPLORED REGION", "title": f"{h['region']} has {h['profiles']} profiles in your data. Check its temperature at 500 m.",
                         "question": f"What was the average temperature at 500 m in the {h['region']} in {when}?"})
            break
    for v, other in (("temperature", "salinity"), ("salinity", "temperature")):  # 2) the other variable
        if v in asked_vars and other not in asked_vars:
            reg = next(iter(asked_regions), "Arabian Sea").title()
            recs.append({"tag": "OTHER VARIABLE", "title": f"You studied {v}. Now look at {other} in the {reg}.",
                         "question": f"What was the average {other} at 200 m in the {reg} in {when}?"})
            break
    if "compare_depths" not in asked_intents:  # 3) a different kind of question
        reg = next(iter(asked_regions), "Arabian Sea").title()
        recs.append({"tag": "COMPARE DEPTHS", "title": f"Compare the surface layer with the deep layer in the {reg}.",
                     "question": f"Compare the average temperature at 100 metres and 1,000 metres in the {reg} in {when}."})
    if "depth_profile" not in asked_intents:
        recs.append({"tag": "VERTICAL PROFILE", "title": "See how temperature changes from the surface down to 1800 m.",
                     "question": f"Show the average temperature profile of the Arabian Sea in {when}."})
    if not any(t["status"] == "docs" for t in turns):  # 4) learn the data rules
        recs.append({"tag": "DATA QUALITY", "title": "Learn what the Argo data modes R, A and D mean before trusting recent months.", "question": _CONCEPTS})
    return recs[:limit]


# ===== SECTION 4: the whole dashboard payload =====
def dashboard(df: pd.DataFrame | None, turns: list[dict]) -> dict:
    tp = topics(turns)
    out = {"summary": summary(turns, tp), "topics": tp, "focus": tp[0] if tp else None, "questions": len(turns),
           "sessions": len({t["session_id"] for t in turns}),
           "recent": [{"question": t["question"], "status": t["status"], "ts": t["ts"]} for t in turns[-3:]][::-1],
           "metrics": None, "hotspots": [], "recommendations": []}
    if df is not None:
        out.update(metrics=data_metrics(df), hotspots=hotspots(df), recommendations=recommendations(df, turns))
    return out
