"""Does the faithful-but-ungrounded dissociation depend on the architecture?

Every result so far used attributions from one GNN architecture, so it is fair to
ask whether the dissociation is a property of the narration or an artefact of how
that one model distributes relevance. This narrates matched logs -- same patients,
same explainers -- from GCN, GIN and GAT with a single LLM held fixed, so the only
thing varying is the attribution source.

    python examples/run_architecture_experiment.py            # generate + score
    python examples/run_architecture_experiment.py --score-only
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from gnnarrate import DiseaseAssociations, score_faithfulness, score_grounding
from gnnarrate.benchmark import llm_generator
from gnnarrate.clarus_log import parse_clarus_log
from gnnarrate.config import load_env, use_utf8_stdout

LOGS = pathlib.Path("data/clarus_logs_arch")
OUT = pathlib.Path("data/results_arch")
ARCHS = ["gcn", "gin", "gat"]
DEFAULT_MODEL = "claude-opus-4-8"


def retry(fn, *a, attempts=4, **k):
    for i in range(attempts):
        try:
            return fn(*a, **k)
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(4 * (i + 1))


def generate(archs, model, provider, tag):
    gen = llm_generator(provider=provider)
    for arch in archs:
        src, dest = LOGS / arch, OUT / (arch if tag == "opus" else f"{arch}_{tag}")
        dest.mkdir(parents=True, exist_ok=True)
        made = reused = 0
        for p in sorted(src.glob("*.txt")):
            f = dest / f"narrative_{p.stem}.txt"
            if f.exists() and f.read_text(encoding="utf-8").strip():
                reused += 1
                continue
            try:
                f.write_text(retry(gen, p.read_text(encoding="utf-8"), model, "default"),
                             encoding="utf-8")
                made += 1
            except Exception as exc:
                print(f"    {arch} {p.stem}: {type(exc).__name__}", flush=True)
        print(f"  {arch}: {reused} reused, {made} new", flush=True)


def score(archs, assoc, tag="opus"):
    rows = []
    print(f"\n{'arch':<6}{'n':>4}{'recall':>9}{'grounding':>11}"
          f"{'fab/n':>8}{'claim%':>9}{'halluc%':>9}")
    for arch in archs:
        rec, prec, fab, claim, hall, n = [], [], 0, 0, 0, 0
        sub = OUT / (arch if tag == "opus" else f"{arch}_{tag}")
        for f in sorted(sub.glob("narrative_*.txt")):
            pid = f.stem.replace("narrative_", "")
            lf = LOGS / arch / f"{pid}.txt"
            if not lf.exists():
                continue
            log = parse_clarus_log(lf.read_text(encoding="utf-8"))
            narr = f.read_text(encoding="utf-8")
            fa = score_faithfulness(log, narr, k=3)
            gr = score_grounding(log, narr, assoc)
            rec.append(fa.top_k_recall)
            if gr.grounding_precision is not None:
                prec.append(gr.grounding_precision)
            fab += len(fa.unverified_entities)
            claim += 1 if gr.claimed_genes else 0
            hall += 1 if gr.unsupported else 0
            n += 1
        if not n:
            continue
        row = {
            "arch": arch, "n": n,
            "recall": round(statistics.fmean(rec), 3),
            "grounding_precision": round(statistics.fmean(prec), 3) if prec else None,
            "fabricated_per_narrative": round(fab / n, 3),
            "pct_making_a_claim": round(claim / n, 3),
            "pct_with_unsupported_claim": round(hall / n, 3),
        }
        rows.append(row)
        g = f"{row['grounding_precision']:.3f}" if row["grounding_precision"] else "  -  "
        print(f"{arch.upper():<6}{n:>4}{row['recall']:>9.3f}{g:>11}"
              f"{row['fabricated_per_narrative']:>8.2f}"
              f"{row['pct_making_a_claim']*100:>8.0f}%{row['pct_with_unsupported_claim']*100:>8.0f}%")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"architecture_comparison_{tag}.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8")
    if len(rows) > 1:
        gs = [r["grounding_precision"] for r in rows if r["grounding_precision"]]
        print(f"\ngrounding precision across architectures: "
              f"{min(gs):.3f}-{max(gs):.3f} (spread {max(gs)-min(gs):.3f})")
    print(f"wrote {OUT/'architecture_comparison.json'}")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archs", default=",".join(ARCHS))
    ap.add_argument("--score-only", action="store_true")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--provider", default="anthropic")
    ap.add_argument("--tag", default="opus", help="output suffix for this model")
    args = ap.parse_args()

    load_env()
    use_utf8_stdout()
    archs = [a.strip() for a in args.archs.split(",") if a.strip()]

    assoc = DiseaseAssociations.from_tsv(
        "data/kirc_open_targets.tsv", disease="clear cell renal carcinoma",
        terms=["kidney", "renal", "carcinoma", "cancer", "tumor"])

    if not args.score_only:
        print(f"narrating {archs} with {args.model}", flush=True)
        generate(archs, args.model, args.provider, args.tag)
    score(archs, assoc, args.tag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
