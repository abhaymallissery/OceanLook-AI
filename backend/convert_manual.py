"""Turn raw ERDDAP CSV file(s) (downloaded by fetch_subset.py or by hand in a browser) into the engine's table.

  python convert_manual.py data/raw/*.csv --out data/argo_subset.csv.gz
"""
import argparse, glob

import pandas as pd

# FILE: convert_manual.py - NEW (v2 download fix). Converts raw ERDDAP CSV files (script or browser downloads) to the engine table.
# ===== SECTION 1: columns required in the download =====
KEEP = ["platform_number", "cycle_number", "time", "latitude", "longitude",
        "pres_adjusted", "pres_adjusted_qc", "temp_adjusted", "temp_adjusted_qc", "psal_adjusted", "psal_adjusted_qc"]


# ===== SECTION 2: convert - drop units row, rename *_adjusted -> pres/temp/psal, drop empty pressure, label the source =====
def convert(paths, source):
    parts = [pd.read_csv(p, dtype=str) for p in paths]
    df = pd.concat(parts, ignore_index=True)
    df.columns = [c.strip().lower() for c in df.columns]
    missing = [c for c in KEEP if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing columns {missing}. Download must include: {','.join(KEEP)}")
    df = df[KEEP]
    df = df[df["time"] != "UTC"]  # ERDDAP's second header row holds units, not data
    df = df.rename(columns={c: c.replace("_adjusted", "") for c in KEEP if "_adjusted" in c})
    df = df.dropna(subset=["pres", "time", "latitude", "longitude"]).drop_duplicates()
    df["platform_number"] = df["platform_number"].str.strip().str.strip('"')
    df["source"] = source
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", default="data/argo_subset.csv.gz")
    ap.add_argument("--source", default="Argo GDAC via ERDDAP (manual download)")
    a = ap.parse_args()
    files = [f for pat in a.files for f in glob.glob(pat)]
    if not files:
        raise SystemExit("no input files found")
    df = convert(files, a.source)
    df.to_csv(a.out, index=False)
    print(f"saved {len(df)} rows, {df.groupby(['platform_number','cycle_number']).ngroups} profiles, "
          f"{df.platform_number.nunique()} floats -> {a.out}")
