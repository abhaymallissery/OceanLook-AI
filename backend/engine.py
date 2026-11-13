"""FILE: engine.py - Stage 2 of the pipeline. Deterministic ARGO query engine.
No LLM code here: every number the app shows is computed in this file.
v2 CHANGES are marked 'CHANGED (v2)'. Sections are marked '===== SECTION'."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, model_validator

# ===== SECTION 1: constants - named regions, variables, statistics, QC rule =====
# shortcut: plain lat/lon boxes (may include a little land or neighbouring sea, no dateline crossing);
# upgrade to IHO sea-area polygons when region borders matter.
REGIONS = {  # lat_min, lat_max, lon_min, lon_max
    "arabian sea": (5.0, 27.0, 50.0, 77.0),
    "bay of bengal": (5.0, 23.0, 78.0, 100.0),
    "indian ocean": (-40.0, 30.0, 20.0, 120.0),
    "equatorial indian ocean": (-5.0, 5.0, 40.0, 100.0),
}
VARS = {"temperature": ("temp", "°C"), "salinity": ("psal", "PSU")}
STATS = {"mean": np.mean, "median": np.median, "min": np.min, "max": np.max}
CURVE_DEPTHS = [10, 25, 50, 75, 100, 150, 200, 300, 400, 500, 600, 800, 1000, 1250, 1500, 1800]
GOOD_QC = {1}  # Argo flag 1 = good
MAX_DEPTH_M = 2000
REQUIRED_COLS = ["platform_number", "cycle_number", "time", "latitude", "longitude",
                 "pres", "temp", "psal", "pres_qc", "temp_qc", "psal_qc", "source"]


# ===== SECTION 2: physics - pressure (dbar) to depth (m) =====
def depth_m(p, lat):
    """Depth (m) from pressure (dbar) and latitude: UNESCO/Saunders (Fofonoff & Millard 1983)."""
    p = np.asarray(p, dtype=float)
    x = np.sin(np.radians(lat)) ** 2
    g = 9.780318 * (1 + (5.2788e-3 + 2.36e-5 * x) * x) + 1.092e-6 * p
    return ((((-1.82e-15 * p + 2.279e-10) * p - 2.2512e-5) * p + 9.72659) * p) / g


# ===== SECTION 3: Query - the validated structure the LLM/rules must produce; bad input is rejected here =====
class Query(BaseModel):
    intent: Literal["mean_at_depth", "compare_depths", "depth_profile", "count_profiles"]
    variable: Literal["temperature", "salinity"] = "temperature"
    stat: Literal["mean", "median", "min", "max"] = "mean"
    region: Optional[str] = None
    bbox: Optional[tuple[float, float, float, float]] = None  # lat_min, lat_max, lon_min, lon_max
    start: date
    end: date
    depths_m: list[float] = []
    max_gap_m: float = 100.0

    @model_validator(mode="after")
    def _check(self):
        if self.region:
            self.region = self.region.strip().lower()
            if self.region not in REGIONS:
                raise ValueError(f"unknown region '{self.region}'; known: {sorted(REGIONS)}")
            if self.bbox is None:
                self.bbox = REGIONS[self.region]
        if self.bbox is None:
            raise ValueError("need a known region or an explicit bbox")
        la0, la1, lo0, lo1 = self.bbox
        if not (-90 <= la0 < la1 <= 90 and -180 <= lo0 < lo1 <= 180):
            raise ValueError("bbox must be lat_min<lat_max in [-90,90] and lon_min<lon_max in [-180,180]")
        if self.end < self.start:
            raise ValueError("end date is before start date")
        need = {"mean_at_depth": 1, "compare_depths": 2, "depth_profile": 0, "count_profiles": 0}[self.intent]
        if len(self.depths_m) != need:
            raise ValueError(f"{self.intent} needs exactly {need} depth(s), got {len(self.depths_m)}")
        if any(not 0 < d <= MAX_DEPTH_M for d in self.depths_m):
            raise ValueError(f"depths must be in (0, {MAX_DEPTH_M}] m")
        return self


# ===== SECTION 4: output schema - what the API and UI receive =====
class Series(BaseModel):
    depth_m: float
    value: Optional[float] = None
    std: Optional[float] = None
    n_profiles: int = 0
    n_floats: int = 0


class Result(BaseModel):
    # CHANGED (v2): added "unverified" (a verify.py check failed) and the `checks` list below
    status: Literal["ok", "no_data", "unverified"]
    intent: str
    variable: str
    unit: Optional[str] = None
    series: list[Series] = []
    difference: Optional[float] = None  # compare_depths: second depth minus first
    curve: list[Series] = []  # mean-style profile for the chart
    n_profiles_in_scope: int = 0
    n_floats_in_scope: int = 0
    time_min: Optional[str] = None
    time_max: Optional[str] = None
    observations: list[dict] = []
    n_observations: int = 0
    observations_truncated: bool = False
    method: str = ""
    qc_rule: str = ""
    source: str = ""
    caveats: list[str] = []
    checks: list[dict] = []  # CHANGED (v2): filled by verify.py


# ===== SECTION 5: loading - read the CSV table and check its columns/types =====
def load_table(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"platform_number": str})
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing columns {missing}")
    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_localize(None)
    for c in ["cycle_number", "latitude", "longitude", "pres", "temp", "psal", "pres_qc", "temp_qc", "psal_qc"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["platform_number"] = df["platform_number"].str.strip()
    return df


# ===== SECTION 6: calculation helpers - per-profile good levels, interpolation, statistics =====
def _profiles(scope: pd.DataFrame, col: str) -> dict:
    """One entry per profile: sorted depth/value arrays of good levels only."""
    ok = (scope["pres"].notna() & scope[col].notna()
          & scope["pres_qc"].isin(GOOD_QC) & scope[col + "_qc"].isin(GOOD_QC))
    out = {}
    # shortcut: a profile is (platform, cycle); descending/duplicate cycles would merge, split by direction if ever loaded.
    for key, g in scope[ok].groupby(["platform_number", "cycle_number"], sort=False):
        d = depth_m(g["pres"].to_numpy(), g["latitude"].iloc[0])
        o = np.argsort(d)
        out[key] = dict(depth=d[o], val=g[col].to_numpy(dtype=float)[o], time=g["time"].iloc[0],
                        lat=float(g["latitude"].iloc[0]), lon=float(g["longitude"].iloc[0]))
    return out


def _interp(depth, val, target, max_gap):
    """Linear interpolation between the two good levels bracketing target; never extrapolates."""
    i = int(np.searchsorted(depth, target))
    if i < len(depth) and depth[i] == target:
        return float(val[i]), float(depth[i]), float(depth[i])
    if i == 0 or i == len(depth):
        return None
    lo, hi = depth[i - 1], depth[i]
    if hi - lo > max_gap:
        return None
    return float(val[i - 1] + (target - lo) / (hi - lo) * (val[i] - val[i - 1])), float(lo), float(hi)


def _at_depth(profiles: dict, target: float, max_gap: float) -> list[dict]:
    rows = []
    for (plat, cyc), p in profiles.items():
        r = _interp(p["depth"], p["val"], target, max_gap)
        if r:
            rows.append(dict(platform_number=plat, cycle_number=int(cyc), time=p["time"].isoformat(),
                             latitude=p["lat"], longitude=p["lon"], target_depth_m=target,
                             value=r[0], bracket_lo_m=r[1], bracket_hi_m=r[2]))
    return rows


def _series(rows: list[dict], depth: float, stat: str) -> Series:
    if not rows:
        return Series(depth_m=depth)
    v = np.array([r["value"] for r in rows])
    return Series(depth_m=depth, value=float(STATS[stat](v)), std=float(v.std(ddof=1)) if len(v) > 1 else None,
                  n_profiles=len(v), n_floats=len({r["platform_number"] for r in rows}))


# ===== SECTION 7: run - filter by region/time, compute, attach evidence and caveats =====
def run(df: pd.DataFrame, q: Query, max_obs: int = 300) -> Result:
    col, unit = VARS[q.variable]
    la0, la1, lo0, lo1 = q.bbox
    t0, t1 = pd.Timestamp(q.start), pd.Timestamp(q.end) + pd.Timedelta(days=1)
    scope = df[df["latitude"].between(la0, la1) & df["longitude"].between(lo0, lo1)
               & (df["time"] >= t0) & (df["time"] < t1)]
    src = ", ".join(sorted(df["source"].dropna().unique()))
    res = Result(
        status="no_data", intent=q.intent, variable=q.variable, unit=unit, source=src,
        n_profiles_in_scope=scope.groupby(["platform_number", "cycle_number"]).ngroups,
        n_floats_in_scope=int(scope["platform_number"].nunique()),
        time_min=scope["time"].min().isoformat() if len(scope) else None,
        time_max=scope["time"].max().isoformat() if len(scope) else None,
        method=(f"Per profile: depth from pressure (UNESCO/Saunders, latitude-dependent); value linearly interpolated "
                f"between the two nearest good levels bracketing the target depth (no extrapolation, bracket ≤ {q.max_gap_m:g} m). "
                f"The {q.stat} is taken across profiles, each profile counted once."),
        qc_rule=f"Delayed/adjusted values; Argo QC flag 1 only, on both pressure and {col}.",
    )
    # CHANGED (v2): synthetic data is announced inside every result, so no answer can be mistaken for real measurements
    if "SYNTHETIC" in src.upper():
        res.caveats.insert(0, "SYNTHETIC DATA: values are invented for demonstration and are NOT real ocean measurements.")
    if len(df):
        res.caveats.append(f"Loaded subset covers {df['time'].min():%Y-%m-%d} to {df['time'].max():%Y-%m-%d}; "
                           "results describe this subset only.")
    if q.intent == "count_profiles":
        res.status = "ok" if res.n_profiles_in_scope else "no_data"
        return res
    if not res.n_profiles_in_scope:
        return res

    profiles = _profiles(scope, col)
    depths = sorted(set(q.depths_m) | set(CURVE_DEPTHS)) if q.intent != "depth_profile" else CURVE_DEPTHS
    by_depth = {d: _at_depth(profiles, d, q.max_gap_m) for d in depths}
    res.curve = [_series(by_depth[d], d, q.stat) for d in depths]
    if q.intent == "depth_profile":
        res.series = res.curve
        res.status = "ok" if any(s.n_profiles for s in res.curve) else "no_data"
        return res

    res.series = [_series(by_depth[d], d, q.stat) for d in q.depths_m]
    obs = sorted((r for d in q.depths_m for r in by_depth[d]),
                 key=lambda r: (r["target_depth_m"], r["time"], r["platform_number"]))
    res.n_observations, res.observations = len(obs), obs[:max_obs]
    res.observations_truncated = len(obs) > max_obs
    if all(s.value is not None for s in res.series):
        res.status = "ok"
        if q.intent == "compare_depths":
            res.difference = res.series[1].value - res.series[0].value
    for s in res.series:
        dropped = res.n_profiles_in_scope - s.n_profiles
        if dropped:
            res.caveats.append(f"At {s.depth_m:g} m, {dropped} of {res.n_profiles_in_scope} profiles in scope were unusable "
                               "(no good bracketing levels, or QC rejected).")
    return res
