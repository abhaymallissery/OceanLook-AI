"""SYNTHETIC fixture with analytically known answers: temp = 28 - 0.01*depth, psal = 35 + 0.001*depth. Tests/UI dev only."""
# CHANGED (v2): moved the realistic demo generator to synthetic_demo.py; this fixture stays linear on purpose so tests have exact answers.
import sys
import numpy as np
import pandas as pd
from engine import depth_m

PRES = np.concatenate([np.arange(5, 100, 5), np.arange(100, 1000, 20), np.arange(1000, 2000, 50)]).astype(float)


def make_synthetic() -> pd.DataFrame:
    rows = []
    specs = [  # platform, lat, lon, first month, year, cycles
        *[(f"90000{i}", 12 + i, 62 + i, 1, 2024, 10) for i in range(5)],  # Arabian Sea, 2024
        ("9100001", 12.0, 88.0, 3, 2024, 6),                              # Bay of Bengal, 2024
        ("9200001", 15.0, 65.0, 1, 2023, 5),                              # Arabian Sea, 2023 (time filter)
    ]
    for plat, lat, lon, m0, yr, n in specs:
        for c in range(1, n + 1):
            t = pd.Timestamp(yr, m0, 1) + pd.Timedelta(days=10 * (c - 1))
            d = depth_m(PRES, lat)
            rows.append(pd.DataFrame(dict(platform_number=plat, cycle_number=c, time=t, latitude=lat, longitude=lon,
                                          pres=PRES, temp=28 - 0.01 * d, psal=35 + 0.001 * d,
                                          pres_qc=1, temp_qc=1, psal_qc=1, source="SYNTHETIC TEST DATA")))
    return pd.concat(rows, ignore_index=True)


if __name__ == "__main__":
    make_synthetic().to_csv(sys.argv[1], index=False)
