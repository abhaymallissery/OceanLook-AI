# FILE: verify.py - NEW (v2). Stage 3 "validation" from the brief, and Unit VI explainability/testing at run time.
# Re-checks a finished Result against the Query WITHOUT trusting the engine's own bookkeeping.
import math

import numpy as np
import pandas as pd

from engine import STATS, VARS, Query, Result

PLAUSIBLE = {"temperature": (-2.5, 40.0), "salinity": (0.0, 42.0)}  # physical limits of sea water


# ===== SECTION: verify - run all checks, record them, downgrade the result if one fails =====
def verify(q: Query, r: Result) -> Result:
    checks = []

    def add(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("unit matches variable", r.unit == VARS[q.variable][1], f"{r.unit}")
    vals = [s.value for s in r.series + r.curve if s.value is not None]
    add("all numbers finite", all(math.isfinite(v) for v in vals) and all(s.std is None or math.isfinite(s.std) for s in r.series))
    lo, hi = PLAUSIBLE[q.variable]
    add("values physically plausible", all(lo <= v <= hi for v in vals), f"allowed {lo} to {hi} {r.unit}")
    add("counts consistent", all(s.n_profiles <= r.n_profiles_in_scope and s.n_floats <= r.n_floats_in_scope for s in r.series))
    add("QC rule and source recorded", bool(r.qc_rule) and bool(r.source))
    if r.observations:
        la0, la1, lo0, lo1 = q.bbox
        t0, t1 = pd.Timestamp(q.start), pd.Timestamp(q.end) + pd.Timedelta(days=1)
        inside = all(la0 <= o["latitude"] <= la1 and lo0 <= o["longitude"] <= lo1 and t0 <= pd.Timestamp(o["time"]) < t1
                     for o in r.observations)
        add("every observation lies inside the requested region and period", inside)
        if not r.observations_truncated:  # recompute each statistic from the evidence rows the user can see
            ok = True
            for s in r.series:
                v = [o["value"] for o in r.observations if o["target_depth_m"] == s.depth_m]
                ok &= bool(v) and abs(float(STATS[q.stat](np.array(v))) - s.value) <= 1e-9 * max(1.0, abs(s.value))
            add("statistic recomputed from evidence rows matches", ok)
    r.checks = checks
    failed = [c["name"] for c in checks if not c["ok"]]
    if failed and r.status == "ok":
        r.status = "unverified"
        r.caveats.append("VERIFICATION FAILED: " + "; ".join(failed))
    return r
