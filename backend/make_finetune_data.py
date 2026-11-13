"""FILE: make_finetune_data.py - NEW (v2). Unit III: builds a supervised fine-tuning / instruction-tuning dataset.
Each line:  {"input": <plain-English question>, "output": <the JSON Query the parser must produce>}
Templates are split so the validation file uses PHRASINGS THE TRAINING FILE NEVER SAW (held-out templates), which is what makes
the validation score meaningful. Every target is validated by engine.Query, so the data cannot teach an invalid schema.
Also prints how the offline rule parser scores on the held-out file = the baseline a tuned LLM must beat.

  python make_finetune_data.py --n 400 --out data/finetune
Use train.jsonl for LoRA / Gemini supervised tuning (see EXPLANATION.md, section 'Fine-tuning'); then evaluate the tuned model with
  GEMINI_MODEL=<tuned-model> python eval_run.py --parser llm --cases data/finetune/val_cases.json
"""
import argparse, json, os, random

from engine import REGIONS, Query
from errors import Unsupported
from rules import parse_rules

STAT_WORD = {"mean": ["average", "mean"], "median": ["median"], "max": ["maximum", "highest"], "min": ["minimum", "lowest"]}

# ===== SECTION 1: templates. The LAST template of each intent is held out for validation =====
T = {
    "mean_at_depth": ["What was the {sw} {var} at {d} m in the {reg} during {y}?",
                      "Find the {sw} {var} at {d} metres in the {reg} in {y}.",
                      "{regT}: {sw} {var} at {d} m depth, {y}?",
                      "Tell me the {sw} {var} around {d} m for the {reg} over {y}."],
    "compare_depths": ["Compare the {var} at {d} m and {d2} m in the {reg} during {y}.",
                       "How does {var} at {d} metres differ from {d2} metres in the {reg} in {y}?",
                       "{varT} at {d} m versus {d2} m, {reg}, {y}."],
    "depth_profile": ["Show the {var} profile of the {reg} in {y}.",
                      "What does the vertical {var} profile look like in the {reg} during {y}?",
                      "Give me {var} against depth for the {reg} in {y}."],
    "count_profiles": ["How many Argo profiles were recorded in the {reg} during {y}?",
                       "Count the profiles in the {reg} in {y}.",
                       "What is the number of profiles in the {reg} for {y}?"],
    "unsupported": ["Will the {reg} be warmer next year?", "What is the oxygen level at {d} m in the {reg} in {y}?",
                    "Show float trajectories in the {reg}."],
}


# ===== SECTION 2: one example from one template =====
def make(intent, tmpl, rng):
    reg, y, var = rng.choice(sorted(REGIONS)), rng.choice([2022, 2023, 2024]), rng.choice(["temperature", "salinity"])
    d, d2 = rng.choice([10, 50, 100, 150, 200, 300, 500, 750, 1000]), rng.choice([1200, 1500, 1800])
    if "{var" not in tmpl:  # CHANGED (v2): a question that never names a variable gets the default, otherwise the target would be unguessable
        var = "temperature"
    stat = rng.choice(list(STAT_WORD)) if intent == "mean_at_depth" else "mean"
    q = tmpl.format(sw=rng.choice(STAT_WORD[stat]), var=var, varT=var.title(), reg=reg, regT=reg.title(), d=d, d2=d2, y=y)
    if intent == "unsupported":
        return q, {"unsupported": "not supported"}
    target = dict(intent=intent, variable=var, stat=stat, region=reg, bbox=None, start=f"{y}-01-01", end=f"{y}-12-31",
                  depths_m=[float(d)] if intent == "mean_at_depth" else [float(d), float(d2)] if intent == "compare_depths" else [])
    Query.model_validate(target)  # the dataset can never contain an invalid target
    return q, target


# ===== SECTION 3: build train/val files and score the rules baseline on held-out phrasings =====
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--out", default="data/finetune")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    rng, os_ = random.Random(a.seed), os.makedirs(a.out, exist_ok=True)
    train, val, seen = [], [], set()
    while len(train) + len(val) < a.n:
        intent = rng.choice(list(T))
        held = rng.random() < 0.2
        tmpl = T[intent][-1] if held else rng.choice(T[intent][:-1])
        q, target = make(intent, tmpl, rng)
        if q in seen:
            continue
        seen.add(q)
        (val if held else train).append({"input": q, "output": json.dumps(target)})
    for name, rows in (("train", train), ("val", val)):
        with open(f"{a.out}/{name}.jsonl", "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)
    json.dump([{"question": r["input"], "expected": json.loads(r["output"]) if "unsupported" not in r["output"] else {"unsupported": True}}
               for r in val], open(f"{a.out}/val_cases.json", "w"), indent=1)  # ready for eval_run.py --cases
    ok = 0
    for r in val:
        want = json.loads(r["output"])
        try:
            got = parse_rules(r["input"])
            ok += "unsupported" not in want and got.model_dump(mode="json", exclude={"max_gap_m"}) == Query(**want).model_dump(mode="json", exclude={"max_gap_m"})
        except Unsupported:
            ok += "unsupported" in want
    print(f"train {len(train)}  val {len(val)}  -> {a.out}/   rules-parser baseline on held-out phrasings: {ok}/{len(val)} = {ok/len(val):.0%}")


if __name__ == "__main__":
    main()
