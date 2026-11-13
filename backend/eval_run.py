"""FILE: eval_run.py - Unit VI: evaluation. Scores SEPARATELY:
  parse accuracy     did the parser produce the expected structured query?        (--parser rules | llm | expected)
  retrieval accuracy did the engine select exactly the reference profile/level set? (set comparison vs a plain-Python reference)
  numeric accuracy   does the engine's value match the reference within --tol?      (reference re-implements the maths with loops)
  rag accuracy       did concept questions retrieve the expected note?
CHANGED (v2): --parser option (offline 'rules' now measurable without an API key), RAG cases, and --report writes the Markdown report.
  python eval_run.py --data data/argo_subset.csv.gz --parser rules --report REPORT.md
Honest limit: the bundled cases were written by the same author as the rule parser, so rules scores are optimistic. Use
data/finetune/val_cases.json (held-out phrasings) or your own questions for an unbiased number.
"""
import argparse, json, math
from datetime import date

import pandas as pd

import llm
import rag
import verify
from engine import GOOD_QC, STATS, VARS, Query, depth_m, load_table, run
from errors import Unsupported
from rules import parse_rules


# ===== SECTION 1: independent reference - same maths, written with plain loops (no pandas groupby) =====
def reference(df: pd.DataFrame, q: Query):
    col = VARS[q.variable][0]
    la0, la1, lo0, lo1 = q.bbox
    t0, t1 = pd.Timestamp(q.start), pd.Timestamp(q.end) + pd.Timedelta(days=1)
    prof = {}
    for r in df.itertuples(index=False):
        if not (la0 <= r.latitude <= la1 and lo0 <= r.longitude <= lo1 and t0 <= r.time < t1):
            continue
        key = (r.platform_number, int(r.cycle_number))
        v, vq = getattr(r, col), getattr(r, col + "_qc")
        if any(math.isnan(x) for x in (r.pres, v)) or r.pres_qc not in GOOD_QC or vq not in GOOD_QC:
            prof.setdefault(key, [])
            continue
        prof.setdefault(key, []).append((float(depth_m(r.pres, r.latitude)), v))
    out = {}
    for target in q.depths_m:
        ids, vals = set(), []
        for key, lv in prof.items():
            lv.sort()
            below, above = [x for x in lv if x[0] <= target], [x for x in lv if x[0] >= target]
            if not below or not above:
                continue
            (d0, v0), (d1, v1) = below[-1], above[0]
            if d1 - d0 > q.max_gap_m:
                continue
            vals.append(v0 if d1 == d0 else v0 + (target - d0) / (d1 - d0) * (v1 - v0))
            ids.add(key)
        out[target] = (ids, float(STATS[q.stat](vals)) if vals else None)
    return out


# ===== SECTION 2: parse step according to --parser =====
def parse(question, want, mode):
    if mode == "expected":
        return want
    return parse_rules(question) if mode == "rules" else llm.parse_question(question)


def same_query(a: Query, b: Query) -> bool:
    return a.model_dump(mode="json", exclude={"max_gap_m"}) == b.model_dump(mode="json", exclude={"max_gap_m"})


# ===== SECTION 3: main loop - one case at a time, collecting scores and Q&A pairs for the report =====
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/argo_subset.csv.gz")
    ap.add_argument("--cases", default="eval_cases.json")
    ap.add_argument("--parser", choices=["expected", "rules", "llm"], default="rules")
    ap.add_argument("--skip-parse", action="store_true", help="alias for --parser expected")
    ap.add_argument("--tol", type=float, default=1e-6)
    ap.add_argument("--report")
    a = ap.parse_args()
    mode = "expected" if a.skip_parse else a.parser
    df = load_table(a.data)
    src = ", ".join(sorted(df["source"].unique()))
    rows, qa, S = [], [], dict(parse=[0, 0], ret=[0, 0], num=[0, 0], rag=[0, 0], ver=[0, 0])
    for c in json.load(open(a.cases)):
        text, exp = c["question"], c["expected"]
        if "docs" in exp:  # concept question -> RAG
            hits = rag.search(text)
            ok = bool(hits) and exp["docs"] in hits[0]["title"].lower()
            S["rag"][0] += ok; S["rag"][1] += 1
            rows.append((text, "docs", "-", "ok" if ok else "FAIL", hits[0]["title"] if hits else "none"))
            qa.append((text, f"(concept question) retrieved note: **{hits[0]['title'] if hits else 'none'}**", hits[0]["text"] if hits else ""))
            continue
        if exp.get("unsupported"):
            S["parse"][1] += 1
            try:
                if mode == "expected":
                    raise Unsupported()
                parse(text, None, mode)
                verdict = "FAIL (answered)"
            except Unsupported:
                verdict, _ = "ok (refused)", S["parse"].__setitem__(0, S["parse"][0] + 1)
            except Exception as e:
                verdict = f"FAIL ({type(e).__name__})"
            rows.append((text, verdict, "-", "-", "-"))
            qa.append((text, "refused as unsupported" if verdict.startswith("ok") else verdict, ""))
            continue
        want = Query(**exp)
        S["parse"][1] += 1
        try:
            got = parse(text, want, mode)
        except Exception as e:
            rows.append((text, f"FAIL ({type(e).__name__})", "-", "-", "-"))
            continue
        same = same_query(got, want)
        S["parse"][0] += same
        r = verify.verify(got, run(df, got, max_obs=10**9))  # CHANGED (v2): full evidence list, so retrieval can be compared exactly
        S["ver"][1] += 1; S["ver"][0] += all(k["ok"] for k in r.checks)
        ref = reference(df, want)
        S["ret"][1] += 1; S["num"][1] += 1
        if want.intent in ("mean_at_depth", "compare_depths"):
            used = {(o["platform_number"], o["cycle_number"], o["target_depth_m"]) for o in r.observations}
            exp_ids = {(p, cy, d) for d, (ids, _) in ref.items() for p, cy in ids}
            r_ok = (not r.observations_truncated) and used == exp_ids
            n_ok = all(s.value is not None and ref[s.depth_m][1] is not None and abs(s.value - ref[s.depth_m][1]) <= a.tol
                       for s in r.series) or all(s.value is None and ref[s.depth_m][1] is None for s in r.series)
        else:
            r_ok = n_ok = True
            if want.intent == "count_profiles":
                sc = df[df.latitude.between(want.bbox[0], want.bbox[1]) & df.longitude.between(want.bbox[2], want.bbox[3])
                        & (df.time >= pd.Timestamp(want.start)) & (df.time < pd.Timestamp(want.end) + pd.Timedelta(days=1))]
                n_ok = r.n_profiles_in_scope == len({(p, int(cy)) for p, cy in zip(sc.platform_number, sc.cycle_number)})
        S["ret"][0] += r_ok; S["num"][0] += n_ok
        val = f"{r.series[0].value:.4f}" if r.series and r.series[0].value is not None else r.status
        rows.append((text, "ok" if same else "MISMATCH", "ok" if r_ok else "FAIL", "ok" if n_ok else "FAIL", val))
        qa.append((text, f"`{got.intent}` · {got.variable} · {got.region} · {got.start} → {got.end} · depths {got.depths_m or '-'}",
                   llm.summarize(r, got) + f"  _(checks passed: {sum(k['ok'] for k in r.checks)}/{len(r.checks)})_"))
    pm = "not measured (parser=expected)" if mode == "expected" else f"{S['parse'][0]}/{S['parse'][1]}"
    summary = (f"parse[{mode}] {pm}  retrieval {S['ret'][0]}/{S['ret'][1]}  numeric {S['num'][0]}/{S['num'][1]}  "
               f"verification {S['ver'][0]}/{S['ver'][1]}  rag {S['rag'][0]}/{S['rag'][1]}  (tol {a.tol})")
    print("| Question | Parse | Retrieval | Numeric/RAG | Value |\n|---|---|---|---|---|")
    for x in rows:
        print("| " + " | ".join(str(i) for i in x) + " |")
    print("\n" + summary)
    if a.report:
        write_report(a.report, src, df, mode, summary, S, qa, a.tol)


# ===== SECTION 4: Markdown report - data source, accuracy table, example Q&A pairs =====
def write_report(path, src, df, mode, summary, S, qa, tol):
    pct = lambda k: "n/a" if S[k][1] == 0 else f"{S[k][0]}/{S[k][1]} = {S[k][0]/S[k][1]:.0%}"
    synth = "SYNTHETIC" in src.upper()
    L = ["# FloatChat - evaluation report", f"_Generated {date.today()}_", ""]
    if synth:
        L += ["> **WARNING: this report was produced on SYNTHETIC DEMO DATA. The numbers are invented and show only that the pipeline "
              "works. Re-run `eval_run.py` on the real ARGO subset before submitting.**", ""]
    L += ["## 1. Data", f"- Source: {src}",
          f"- {df.groupby(['platform_number','cycle_number']).ngroups} profiles, {df.platform_number.nunique()} floats, "
          f"{df.time.min():%Y-%m-%d} to {df.time.max():%Y-%m-%d}", "",
          "## 2. Accuracy (measured separately, as the brief asks)", "| Metric | What it measures | Score |", "|---|---|---|",
          f"| Parse accuracy ({mode}) | question -> correct structured query | {'not measured' if mode == 'expected' else pct('parse')} |",
          f"| Retrieval accuracy | engine used exactly the reference profiles/levels | {pct('ret')} |",
          f"| Numerical accuracy | engine value vs independent reference, tolerance {tol:g} | {pct('num')} |",
          f"| Verification checks | all run-time checks passed | {pct('ver')} |",
          f"| RAG retrieval | concept question found the right note | {pct('rag')} |", "",
          "Limits: the example questions were written by the project author, so parse accuracy for the rule parser is optimistic; "
          "the reference and the engine share the pressure-to-depth function (checked separately against the UNESCO value 9712.653 m).", "",
          "## 3. Example question and answer pairs"]
    for i, (q, interp, ans) in enumerate(qa, 1):
        L += [f"**Q{i}. {q}**", f"- Interpreted as: {interp}", f"- Answer: {ans}" if ans else "", ""]
    open(path, "w", encoding="utf8").write("\n".join(L))
    print("report written to", path)


if __name__ == "__main__":
    main()
