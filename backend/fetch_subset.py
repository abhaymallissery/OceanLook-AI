"""Download raw ARGO CSV chunks from an ERDDAP server, then convert them (resumable).

  python fetch_subset.py --region "arabian sea" --start 2024-01-01 --end 2024-12-31
  python fetch_subset.py --print-urls ...     # just print the URLs so you can paste them into a browser instead

Raw chunks go to data/raw/. Chunks already on disk are skipped, so re-run the same command after a failure.
Servers tried in order (all host the same Argo GDAC dataset 'ArgoFloats'); --base puts yours first.
"""
import argparse, os, time, urllib.error, urllib.request
from urllib.parse import quote

import pandas as pd

from convert_manual import KEEP, convert
from engine import REGIONS

SERVERS = ["https://erddap.ifremer.fr/erddap/tabledap/ArgoFloats",
           "https://osmc.noaa.gov/erddap/tabledap/ArgoFloats",
           "https://erddap.emodnet-physics.eu/erddap/tabledap/ArgoFloats"]


# FILE: fetch_subset.py - CHANGED (v2 download fix): resumable 15-day chunks, retries, three ERDDAP mirrors, readable errors.
# ===== SECTION 1: build the list of date chunks and the ERDDAP URL for each =====
def chunks(start, end, days=15):
    s, e = pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(days=1)
    edges = list(pd.date_range(s, e, freq=f"{days}D")) + [e]
    return [(a, b) for a, b in zip(edges[:-1], edges[1:]) if a < b]


def url(base, box, t0, t1):
    la0, la1, lo0, lo1 = box
    cons = [f"time>={t0:%Y-%m-%dT%H:%M:%SZ}", f"time<{t1:%Y-%m-%dT%H:%M:%SZ}", f"latitude>={la0}", f"latitude<={la1}",
            f"longitude>={lo0}", f"longitude<={lo1}", "pres_adjusted<=2000"]
    return f"{base}.csv?{','.join(KEEP)}&" + "&".join(quote(c, safe="=") for c in cons)


# ===== SECTION 2: HTTP get with User-Agent, 300 s timeout, retries; 404 "no matching data" means an empty chunk =====
def get(u, tries=3):
    req = urllib.request.Request(u, headers={"User-Agent": "FloatChat/0.1 (student project)"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf8", "replace")
            if e.code == 404 and "no matching" in body.lower():
                return b""  # genuinely empty chunk
            if e.code < 500 and e.code != 429:
                raise RuntimeError(f"HTTP {e.code}: {body}")
        except Exception as e:  # timeouts, resets
            err = e
        time.sleep(5 * (i + 1))
    raise RuntimeError(f"gave up after {tries} tries: {locals().get('err', 'server error')}")


# ===== SECTION 3: main - download chunks to data/raw/, then convert them with convert_manual.convert =====
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="arabian sea", choices=sorted(REGIONS))
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", default="data/argo_subset.csv.gz")
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--base", help="ERDDAP .../tabledap/ArgoFloats URL to try first")
    ap.add_argument("--print-urls", action="store_true")
    a = ap.parse_args()
    servers = ([a.base] if a.base else []) + SERVERS
    os.makedirs(a.raw, exist_ok=True)
    if a.print_urls:
        for t0, t1 in chunks(a.start, a.end):
            print(url(servers[0], REGIONS[a.region], t0, t1))
        return
    server_used, failed = None, []
    for t0, t1 in chunks(a.start, a.end):
        f = f"{a.raw}/argo_{t0:%Y%m%d}.csv"
        if os.path.exists(f):
            continue
        for s in ([server_used] if server_used else servers):
            try:
                data = get(url(s, REGIONS[a.region], t0, t1))
                server_used = s
                break
            except RuntimeError as e:
                print(f"  {s.split('/erddap')[0]}: {e}", flush=True)
        else:
            failed.append(t0)
            print(f"FAILED {t0:%Y-%m-%d} (will be retried on re-run)", flush=True)
            continue
        print(f"{t0:%Y-%m-%d}: {len(data)//1024} KB", flush=True)
        if data:
            open(f, "wb").write(data)
        else:
            open(f, "w").write("")  # remember empty chunk
    files = [f"{a.raw}/{n}" for n in sorted(os.listdir(a.raw)) if n.endswith(".csv") and os.path.getsize(f"{a.raw}/{n}") > 0]
    if not files:
        raise SystemExit("No data downloaded. Use --print-urls and open a URL in your browser to see the server's error message.")
    df = convert(files, f"Argo GDAC via ERDDAP ({(server_used or servers[0]).split('/erddap')[0].replace('https://', '')})")
    df.to_csv(a.out, index=False)
    print(f"saved {len(df)} rows, {df.groupby(['platform_number','cycle_number']).ngroups} profiles, "
          f"{df.platform_number.nunique()} floats -> {a.out}" + (f"  (failed chunks: {len(failed)}, re-run to retry)" if failed else ""))


if __name__ == "__main__":
    main()
