"""Read official Argo GDAC multi-profile NetCDF files (geo/<basin>/YYYY/MM/YYYYMMDD_prof.nc) into the engine's table.

  python convert_gdac.py data/gdac/*.nc --region "arabian sea" --start 2024-01-01 --end 2024-12-31 --out data/argo_subset.csv.gz
Uses the *_ADJUSTED variables and their QC flags (profiles without adjusted data are dropped), ascending profiles only.
"""
import argparse, glob

import numpy as np
import pandas as pd
import xarray as xr

from engine import REGIONS


# FILE: convert_gdac.py - NEW (v3). Reads official GDAC NetCDF multi-profile files.
# ===== SECTION 1: helpers - Argo stores text as fixed-width character arrays =====
def _chars(a, width):
    return np.char.strip(a.astype(f"S{width}").astype(f"U{width}"))  # works for bytes, str or object arrays


def read_prof(path, box, t0, t1):
    la0, la1, lo0, lo1 = box
    ds = xr.open_dataset(path, decode_times=False)
    if not all(v in ds for v in ("PRES_ADJUSTED", "TEMP_ADJUSTED", "PSAL_ADJUSTED")):  # NEW (v5): skip instead of crashing
        ds.close()
        return None
    time = pd.Timestamp("1950-01-01") + pd.to_timedelta(ds["JULD"].values.astype(float), unit="D")  # JULD = days since 1950
    lat, lon = ds["LATITUDE"].values, ds["LONGITUDE"].values
    keep = (lat >= la0) & (lat <= la1) & (lon >= lo0) & (lon <= lo1) & np.asarray((time >= t0) & (time < t1))
    if "DIRECTION" in ds:
        keep &= _chars(ds["DIRECTION"].values, 1) == "A"
    idx = np.flatnonzero(keep)
    if not len(idx):
        return None
    n = ds.sizes["N_LEVELS"]

    def qc(name):
        return pd.to_numeric(pd.Series(_chars(ds[name].values[idx], 1).ravel()), errors="coerce").to_numpy()

    out = pd.DataFrame({
        "platform_number": np.repeat(_chars(ds["PLATFORM_NUMBER"].values[idx], 8), n),
        "cycle_number": np.repeat(ds["CYCLE_NUMBER"].values[idx], n),
        "time": np.repeat(time.values[idx], n),
        "latitude": np.repeat(lat[idx], n), "longitude": np.repeat(lon[idx], n),
        "pres": ds["PRES_ADJUSTED"].values[idx].ravel(), "pres_qc": qc("PRES_ADJUSTED_QC"),
        "temp": ds["TEMP_ADJUSTED"].values[idx].ravel(), "temp_qc": qc("TEMP_ADJUSTED_QC"),
        "psal": ds["PSAL_ADJUSTED"].values[idx].ravel(), "psal_qc": qc("PSAL_ADJUSTED_QC"),
    })
    ds.close()
    return out[out["pres"].between(0, 2000)]


def convert(paths, region, start, end, source="Argo GDAC (official NetCDF multi-profile files)"):
    t0, t1 = pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(days=1)
    parts = [p for p in (read_prof(f, REGIONS[region], t0, t1) for f in sorted(paths)) if p is not None]
    if not parts:
        raise SystemExit("no profiles matched region/period in these files")
    df = pd.concat(parts, ignore_index=True)
    df["source"] = source
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--region", default="arabian sea", choices=sorted(REGIONS))
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", default="data/argo_subset.csv.gz")
    a = ap.parse_args()
    df = convert([f for pat in a.files for f in glob.glob(pat)], a.region, a.start, a.end)
    df.to_csv(a.out, index=False)
    print(f"saved {len(df)} rows, {df.groupby(['platform_number','cycle_number']).ngroups} profiles, "
          f"{df.platform_number.nunique()} floats -> {a.out}")
