# FILE: rules.py - NEW (v2). Offline question parser (no LLM, no API key). Used as the fallback when the LLM is missing/fails,
# and as the baseline that a fine-tuned or prompted LLM must beat (Unit III).
# shortcut: regular expressions cover the common phrasings only; unusual wording raises Unsupported rather than guessing.
import calendar
import re
from datetime import date

from engine import REGIONS, Query
from errors import Unsupported

NUM = r"\d[\d,]*(?:\.\d+)?"
UNIT = r"(?:m\b|metres?\b|meters?\b)"
MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
MONTHS["sept"] = 9
MONTH_RE = r"\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sept?|oct|nov|dec)\b"
OTHER = re.compile(r"\b(will|forecast|predict\w*|next year|tomorrow|future|oxygen|chlorophyll|nitrate|ph|currents?|velocity|trajector\w*)\b", re.I)


def _f(s: str) -> float:
    return float(s.replace(",", ""))


# ===== SECTION: period - years and months -> start/end dates =====
def _period(t: str, today: date) -> tuple[date, date]:
    if re.search(r"\blast year\b", t):
        years = [today.year - 1]
    elif re.search(r"\bthis year\b", t):
        years = [today.year]
    else:
        years = [int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", t)]
    if not years:
        raise Unsupported("no year or time period found in the question")
    months = []
    for m in re.finditer(MONTH_RE, t):
        if m.group(1) == "may" and not re.search(r"may\s*,?\s*(?:19|20)\d{2}|(?:in|during|of|and|to|from|between)\s+may\b", t):
            continue  # "may" used as a verb
        months.append(MONTHS[m.group(1)])
    y0, y1 = min(years), max(years)
    if months:
        return date(y0, months[0], 1), date(y1, months[-1], calendar.monthrange(y1, months[-1])[1])
    return date(y0, 1, 1), date(y1, 12, 31)


# ===== SECTION: depths - numbers followed by m / metres, including "100 and 1000 m" =====
def _depths(t: str) -> list[float]:
    found = [(m.start(), _f(m.group(1))) for m in re.finditer(rf"({NUM})\s*{UNIT}", t)]
    # CHANGED (v2): a comma only separates two depths when a space follows it ("100, 1000 m"); in "1,000 m" it is a thousands separator
    for m in re.finditer(rf"({NUM})\s*(?:and|vs\.?|versus|&|,\s)\s*({NUM})\s*{UNIT}", t):
        found.append((m.start(1), _f(m.group(1))))
    out = []
    for _, d in sorted(found):
        if d not in out:
            out.append(d)
    return out


# ===== SECTION: parse_rules - the public entry point =====
def parse_rules(question: str, today: date | None = None) -> Query:
    today, t = today or date.today(), question.lower()
    if OTHER.search(t):
        raise Unsupported("forecasts and variables other than temperature/salinity are not supported")
    region = next((r for r in sorted(REGIONS, key=len, reverse=True) if r in t), None)
    if not region:
        raise Unsupported(f"no known region found; known regions: {', '.join(sorted(REGIONS))}")
    start, end = _period(t, today)
    depths = _depths(t)
    variable = "salinity" if re.search(r"\b(salinity|salt|psu)\b", t) else "temperature"
    stat = ("median" if "median" in t else "max" if re.search(r"\b(max(imum)?|highest|warmest|saltiest|greatest)\b", t)
            else "min" if re.search(r"\b(min(imum)?|lowest|coldest|freshest)\b", t) else "mean")
    if len(depths) > 2:  # CHANGED (v2): checked before choosing an intent, so the message is accurate
        raise Unsupported("more than two depths in one question")
    if re.search(r"\b(how many|number of|count)\b", t):
        intent, depths = "count_profiles", []
    elif len(re.findall(NUM, re.sub(r"\b(?:19|20)\d{2}\b", " ", t))) != len(depths):
        # CHANGED (v2): never silently drop a number ("1, 2 and 3 m" used to lose the "1"); refuse instead of guessing
        raise Unsupported("could not match every number in the question to a depth; please give one or two depths with units")
    elif len(depths) == 2:
        intent = "compare_depths"
    elif len(depths) == 1:
        intent = "mean_at_depth"
    elif re.search(r"\bprofile\b|\b(?:against|vs\.?|versus|with|by)\s+depth\b", t):
        intent = "depth_profile"
    else:
        raise Unsupported("no depth (for example '500 m') found in the question")
    return Query(intent=intent, variable=variable, stat=stat, region=region, start=start, end=end, depths_m=depths)


# ===== SECTION: parse_smart - conversational & fault-tolerant parser =====
def parse_smart(question: str, history: list[dict] | None = None, today: date | None = None) -> Query:
    today, t = today or date.today(), question.lower().strip()
    if not t or len(t) < 3:
        raise Unsupported("question is too short or empty")
    if OTHER.search(t):
        raise Unsupported("forecasts and variables other than temperature/salinity are not supported")
    last = history[-1] if history else {}

    # 1. Region resolution
    region = next((r for r in sorted(REGIONS, key=len, reverse=True) if r in t), None)
    if not region:
        if re.search(r"\bar[ab]{1,3}i?a?n?\s*(?:sea)?\b", t):
            region = "arabian sea"
        elif re.search(r"\bbengal\b", t):
            region = "bay of bengal"
        elif re.search(r"\bequator(ial)?\b", t):
            region = "equatorial indian ocean"
        elif re.search(r"\bindian\b", t):
            region = "indian ocean"
        elif last.get("region"):
            region = last["region"]
        else:
            region = "arabian sea"

    # 2. Date / Period resolution
    try:
        start, end = _period(t, today)
    except Unsupported:
        months = [MONTHS[m.group(1)] for m in re.finditer(MONTH_RE, t)]
        if months:
            y = last.get("start", date(2024, 1, 1))
            year = y.year if isinstance(y, date) else int(str(y)[:4]) if str(y)[:4].isdigit() else 2024
            m0, m1 = months[0], months[-1]
            start = date(year, m0, 1)
            end = date(year, m1, calendar.monthrange(year, m1)[1])
        elif last.get("start") and last.get("end"):
            s_val = last["start"]
            e_val = last["end"]
            start = s_val if isinstance(s_val, date) else date.fromisoformat(str(s_val))
            end = e_val if isinstance(e_val, date) else date.fromisoformat(str(e_val))
        else:
            start, end = date(2024, 1, 1), date(2024, 12, 31)

    # 3. Variable resolution
    if re.search(r"\b(salinity|salt|psu)\b", t):
        variable = "salinity"
    elif re.search(r"\b(temp(erature)?|warm(est)?|cold(est)?|thermal|heat)\b", t):
        variable = "temperature"
    elif last.get("variable"):
        variable = last["variable"]
    else:
        variable = "temperature"

    # 4. Stat resolution
    stat = ("median" if "median" in t else "max" if re.search(r"\b(max(imum)?|highest|warmest|saltiest|greatest)\b", t)
            else "min" if re.search(r"\b(min(imum)?|lowest|coldest|freshest)\b", t) else None)
    if not stat:
        stat = last.get("stat", "mean")

    # 5. Intent and depths resolution
    if re.search(r"\b(how many|number of|count)\b", t):
        return Query(intent="count_profiles", variable=variable, stat=stat, region=region, start=start, end=end, depths_m=[])

    if re.search(r"\b(profile|ch[an]{1,2}ges?(?:\s+\w+)*\s+from\s+(?:the\s+)?sur[ef]{1,2}ace|sur[ef]{1,2}ace\s+down\s+to|vs\.?\s*depth|against\s+depth)\b", t):
        return Query(intent="depth_profile", variable=variable, stat=stat, region=region, start=start, end=end, depths_m=[])

    if re.search(r"\bsur[ef]{1,2}ace\b", t) and re.search(r"\bdeep\b", t):
        return Query(intent="compare_depths", variable=variable, stat=stat, region=region, start=start, end=end, depths_m=[100.0, 1000.0])

    depths = _depths(t)
    if len(depths) == 0:
        standalone = re.findall(r"\b([1-9]\d{1,3})\b", re.sub(r"\b(?:19|20)\d{2}\b", " ", t))
        depths = [float(x) for x in standalone if float(x) <= 2000][:2]

    if len(depths) == 2:
        return Query(intent="compare_depths", variable=variable, stat=stat, region=region, start=start, end=end, depths_m=depths)
    elif len(depths) == 1:
        return Query(intent="mean_at_depth", variable=variable, stat=stat, region=region, start=start, end=end, depths_m=depths)

    if last.get("depths_m"):
        return Query(intent=last.get("intent", "mean_at_depth"), variable=variable, stat=stat, region=region, start=start, end=end, depths_m=last["depths_m"])

    if re.search(r"\b(temp(erature)?|salinity|ocean|sea|layer|water)\b", t):
        return Query(intent="depth_profile", variable=variable, stat=stat, region=region, start=start, end=end, depths_m=[])

    raise Unsupported("could not understand question; please include a depth (e.g. 500 m) or ask for a profile")
