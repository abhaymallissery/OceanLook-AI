# FILE: synthetic_demo.py - NEW (v2). Fallback data when the real ARGO file cannot be loaded.
# EVERYTHING HERE IS INVENTED. Shapes are plausible (warm surface, thermocline, salinity maximum) but values are NOT ocean measurements.
# The source column says SYNTHETIC, so the API, the UI banner, every answer and every report carry that label.
import sys

import numpy as np
import pandas as pd

from engine import depth_m

PRES = np.concatenate([np.arange(5, 100, 5), np.arange(100, 1000, 10), np.arange(1000, 2001, 25)]).astype(float)
SOURCE = "SYNTHETIC DEMO DATA - not real ARGO observations"


# ===== SECTION: one invented profile =====
def _profile(rng, z, doy, bob=False):
    ts = (28.0 if bob else 27.5) + 1.5 * np.cos(2 * np.pi * (doy - 120) / 365) + rng.normal(0, 0.3)  # seasonal surface temperature
    deep = 4 + 10 * np.exp(-z / 600)                                              # slowly cooling deep water
    f = (1 - np.tanh((z - 250) / 200)) / (1 - np.tanh(-1.25))                      # thermocline switch, f(0)=1
    temp = deep + (ts - (4 + 10)) * f + rng.normal(0, 0.05, z.size)
    psal = 35.0 + 1.0 * np.exp(-z / 200) + 0.3 * np.exp(-((z - 300) / 150) ** 2) + rng.normal(0, 0.01, z.size)
    if bob:  # CHANGED (v2): Bay of Bengal floats: warmer and fresher at the surface (invented, qualitative only)
        psal = psal - 1.5 * np.exp(-z / 80)
    return temp, psal


# ===== SECTION: whole dataset - floats on 10-day cycles through 2024, a few QC-flagged spikes =====
def make_demo_data(n_floats: int = 35, n_bob: int = 12, cycles: int = 36, year: int = 2024, seed: int = 7) -> pd.DataFrame:
    rng, frames = np.random.default_rng(seed), []
    for i in range(n_floats + n_bob):
        bob = i >= n_floats
        box = (8, 18, 82, 92) if bob else (8, 17, 52, 70) if i % 2 else (12, 22, 60, 72)  # roughly open ocean
        lat, lon = rng.uniform(box[0], box[1]), rng.uniform(box[2], box[3])
        t0 = pd.Timestamp(year, 1, 1) + pd.Timedelta(days=int(rng.integers(0, 10)))
        for c in range(1, cycles + 1):
            t = t0 + pd.Timedelta(days=10 * (c - 1))
            la, lo = lat + rng.normal(0, 0.15), lon + rng.normal(0, 0.15)
            temp, psal = _profile(rng, depth_m(PRES, la), t.dayofyear, bob)
            tq = np.ones(PRES.size, int)
            bad = rng.random(PRES.size) < 0.02  # 2% invented sensor spikes, flagged 4, so the QC filter has work to do
            temp[bad], tq[bad] = temp[bad] + 5, 4
            frames.append(pd.DataFrame(dict(
                platform_number=f"SYN{i:04d}", cycle_number=c, time=t, latitude=la, longitude=lo, pres=PRES,
                temp=temp, psal=psal, pres_qc=1, temp_qc=tq, psal_qc=1, source=SOURCE)))
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "data/synthetic_demo.csv.gz"
    make_demo_data().to_csv(out, index=False)
    print("wrote", out)
