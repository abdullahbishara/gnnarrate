"""Score every generated narrative and emit the paper's comparison tables.

Reads `data/experiments/<config>/narrative_*.txt`, scores each against its CLARUS
log (faithfulness) and the disease knowledge base (grounding), and writes:

* `per_model.csv`     -- one row per model, full corpus, with 95% bootstrap CIs
* `common_subset.csv` -- the same metrics restricted to patients every model
                         covered, so the cross-model comparison is like-for-like
* `per_narrative.csv` -- the raw per-narrative scores behind both tables

Fully offline: it only reads narratives already on disk, so it costs nothing and
can be re-run freely.

    python examples/analyze_comparison.py
    python examples/analyze_comparison.py --exclude opus_nobio
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib

from gnnarrate import (
    DiseaseAssociations,
    mean_ci,
    score_faithfulness,
    score_grounding,
)
from gnnarrate.clarus_log import parse_clarus_log
from gnnarrate.config import use_utf8_stdout

LOGS_DIR = pathlib.Path("data/clarus_logs_kirc")
EXPERIMENTS = pathlib.Path("data/experiments")
RESULTS = pathlib.Path("data/results_comparison")

# Which configs came from an open-weights model -- the paper's central grouping.
OPEN_MODELS = {"kimi", "glm", "deepseek", "qwen", "llama"}

ASSOC_KWARGS = dict(
    disease="clear cell renal carcinoma",
    terms=["kidney", "renal", "carcinoma", "cancer", "tumor"],
)


def score_config(name: str, assoc: DiseaseAssociations, k: int) -> dict[str, dict]:
    """Score every narrative in one config, keyed by patient id."""
    rows: dict[str, dict] = {}
    for path in sorted((EXPERIMENTS / name).glob("narrative_*.txt")):
        pid = path.stem.replace("narrative_", "")
        log_path = LOGS_DIR / f"{pid}.txt"
        if not log_path.exists():
            continue
        narrative = path.read_text(encoding="utf-8")
        if not narrative.strip():
            continue
        log = parse_clarus_log(log_path.read_text(encoding="utf-8"))
        faith = score_faithfulness(log, narrative, k=k)
        ground = score_grounding(log, narrative, assoc)
        rows[pid] = {
            "config": name,
            "patient": pid,
            "kind": "open" if name in OPEN_MODELS else "proprietary",
            "recall": faith.top_k_recall,
            "fabricated": len(faith.unverified_entities),
            "claims": len(ground.claimed_genes),
            "supported": len(ground.supported),
            "unsupported": len(ground.unsupported),
            "precision": ground.grounding_precision,   # None when no claim was made
        }
    return rows


def summarise(name: str, rows: list[dict]) -> dict:
    """Aggregate per-narrative rows into one reportable line."""
    n = len(rows)
    recall_m, recall_lo, recall_hi = mean_ci([r["recall"] for r in rows])
    prec_m, prec_lo, prec_hi = mean_ci([r["precision"] for r in rows])
    return {
        "config": name,
        "kind": "open" if name in OPEN_MODELS else "proprietary",
        "n": n,
        "recall": None if recall_m is None else round(recall_m, 3),
        "recall_lo": None if recall_lo is None else round(recall_lo, 3),
        "recall_hi": None if recall_hi is None else round(recall_hi, 3),
        "grounding_precision": None if prec_m is None else round(prec_m, 3),
        "precision_lo": None if prec_lo is None else round(prec_lo, 3),
        "precision_hi": None if prec_hi is None else round(prec_hi, 3),
        "fabricated_per_narrative": round(sum(r["fabricated"] for r in rows) / n, 3) if n else None,
        "pct_making_a_claim": round(sum(r["claims"] > 0 for r in rows) / n, 3) if n else None,
        "pct_with_unsupported_claim": round(sum(r["unsupported"] > 0 for r in rows) / n, 3) if n else None,
        "total_claims": sum(r["claims"] for r in rows),
        "total_unsupported": sum(r["unsupported"] for r in rows),
    }


def write_csv(path: pathlib.Path, rows: list[dict]) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def print_table(title: str, summaries: list[dict]) -> None:
    print(f"\n=== {title} ===")
    print(f"{'config':<16}{'kind':<13}{'n':>4}  {'recall (95% CI)':<24}"
          f"{'grounding prec (95% CI)':<26}{'fab/n':>7}{'claim%':>8}{'halluc%':>9}")
    for s in summaries:
        recall = ("n/a" if s["recall"] is None
                  else f"{s['recall']:.3f} [{s['recall_lo']:.3f}, {s['recall_hi']:.3f}]")
        prec = ("n/a" if s["grounding_precision"] is None
                else f"{s['grounding_precision']:.3f} [{s['precision_lo']:.3f}, {s['precision_hi']:.3f}]")
        print(f"{s['config']:<16}{s['kind']:<13}{s['n']:>4}  {recall:<24}{prec:<26}"
              f"{s['fabricated_per_narrative']:>7.2f}{s['pct_making_a_claim']*100:>7.0f}%"
              f"{s['pct_with_unsupported_claim']*100:>8.0f}%")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--exclude", default="", help="comma-separated configs to skip")
    parser.add_argument("--associations", default="data/kirc_open_targets.tsv")
    args = parser.parse_args()

    use_utf8_stdout()
    excluded = {c.strip() for c in args.exclude.split(",") if c.strip()}
    configs = sorted(
        d.name for d in EXPERIMENTS.iterdir()
        if d.is_dir() and d.name not in excluded and any(d.glob("narrative_*.txt"))
    )
    if not configs:
        print(f"no narratives found under {EXPERIMENTS}")
        return 1

    assoc = DiseaseAssociations.from_tsv(args.associations, **ASSOC_KWARGS)
    scored = {name: score_config(name, assoc, args.top_k) for name in configs}
    scored = {name: rows for name, rows in scored.items() if rows}

    RESULTS.mkdir(parents=True, exist_ok=True)
    flat = [row for rows in scored.values() for row in rows.values()]
    write_csv(RESULTS / "per_narrative.csv", flat)

    print(f"configs: {[(n, len(r)) for n, r in scored.items()]}")

    per_model = [summarise(n, list(r.values())) for n, r in scored.items()]
    per_model.sort(key=lambda s: (s["kind"], -(s["grounding_precision"] or 0)))
    write_csv(RESULTS / "per_model.csv", per_model)
    print_table("PER-MODEL (full corpus available for each)", per_model)

    common = set.intersection(*[set(r) for r in scored.values()])
    subset = []
    if common:
        subset = [summarise(n, [scored[n][pid] for pid in sorted(common)]) for n in scored]
        subset.sort(key=lambda s: (s["kind"], -(s["grounding_precision"] or 0)))
        write_csv(RESULTS / "common_subset.csv", subset)
        print_table(f"COMMON SUBSET ({len(common)} patients, like-for-like)", subset)

    (RESULTS / "summary.json").write_text(
        json.dumps({"per_model": per_model, "common_subset": subset,
                    "n_common": len(common)}, indent=2),
        encoding="utf-8",
    )
    print(f"\nwrote {RESULTS}/per_model.csv, common_subset.csv, per_narrative.csv, summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
