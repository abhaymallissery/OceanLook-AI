"""Download daily Indian Ocean multi-profile files from the official Argo GDACs, then convert.

  python fetch_gdac.py --region "arabian sea" --start 2024-01-01 --end 2024-12-31
Files go to data/gdac/ (re-running skips files already downloaded). Both GDACs serve identical data.
Check the folders in a browser first:  https://data-argo.ifremer.fr/geo/indian_ocean/2024/01/
"""
import argparse, os, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from convert_gdac import convert
from engine import REGIONS

# FILE: fetch_gdac.py - NEW (v3). Downloads daily geo/indian_ocean files from the official GDACs, then converts them.
# ===== SECTION 1: server list and per-day URL =====
GDACS = ["https://data-argo.ifremer.fr", "https://usgodae.org/pub/outgoing/argo"]  # CHANGED (v5): Ifremer first (the NOAA mirror returned HTTP 500 on 2026-11-01)


def day_url(root, d):
    return f"{root}/geo/indian_ocean/{d:%Y}/{d:%m}/{d:%Y%m%d}_prof.nc"


# ===== SECTION 2: download one day (retries, falls back to the second GDAC, atomic rename) =====
def download(d, dest):
    f = f"{dest}/{d:%Y%m%d}_prof.nc"
    if os.path.exists(f):
        return d, "cached"
    errs: dict[str, str] = {}  # CHANGED (v5): remember the error of EVERY server (before, only the last one was shown)
    for root in GDACS:
        for i in range(3):
            try:
                req = urllib.request.Request(day_url(root, d), headers={"User-Agent": "FloatChat/0.1 (student project)"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = r.read()
                open(f + ".part", "wb").write(data)
                os.replace(f + ".part", f)
                return d, "ok"
            except urllib.error.HTTPError as e:
                errs[root] = f"HTTP {e.code}"
                if e.code == 404:
                    break  # this GDAC has no such file; try the other
            except Exception as e:
                errs[root] = f"{type(e).__name__}: {e}"
            time.sleep(3 * (i + 1))
    return d, "FAILED: " + "; ".join(f"{r} -> {m}" for r, m in errs.items())


# ===== SECTION 3: main - 4 parallel downloads, then convert =====
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="arabian sea", choices=sorted(REGIONS))
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", default="data/argo_subset.csv.gz")
    ap.add_argument("--dest", default="data/gdac")
    ap.add_argument("--print-urls", action="store_true")
    ap.add_argument("--raw", help="NEW (v5): folder of *_prof.nc files you downloaded by hand (for example data/raw); no download is done")
    a = ap.parse_args()
    days = list(pd.date_range(a.start, a.end, freq="D"))
    if a.print_urls:
        print("\n".join(day_url(GDACS[0], d) for d in days))
        return
    bad = []
    if a.raw:  # NEW (v5): manual route - use files already placed in the folder
        a.dest = a.raw
    else:
        os.makedirs(a.dest, exist_ok=True)
        with ThreadPoolExecutor(4) as ex:
            for d, status in ex.map(lambda d: download(d, a.dest), days):
                print(f"{d:%Y-%m-%d} {status}", flush=True)
                if status.startswith("FAILED"):
                    bad.append(d)
    files = sorted(f"{a.dest}/{n}" for n in os.listdir(a.dest) if n.endswith("_prof.nc"))
    if not files:  # NEW (v5): clear message instead of the confusing "no profiles matched"
        raise SystemExit(f"no *_prof.nc files in {a.dest}. Download failed or the folder is empty; see README 'Manual download'.")
    print(f"converting {len(files)} files ...", flush=True)
    df = convert(files, a.region, a.start, a.end)
    df.to_csv(a.out, index=False)
    print(f"saved {len(df)} rows, {df.groupby(['platform_number','cycle_number']).ngroups} profiles, "
          f"{df.platform_number.nunique()} floats -> {a.out}" + (f"  ({len(bad)} days failed; re-run to retry)" if bad else ""))


if __name__ == "__main__":
    main()
