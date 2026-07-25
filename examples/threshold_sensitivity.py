"""How much does grounding precision depend on the association threshold?

Grounding treats a gene as associated when its Open Targets score exceeds a
threshold, fixed at 0 throughout the main results. That choice is consequential:
Open Targets scores are continuous and many are very small, so a permissive
threshold counts weak evidence as support. This sweeps the threshold and reports
grounding precision at each, turning a stated caveat into a measured curve.

Purely offline -- rescoring existing narratives, no model calls.

    python examples/threshold_sensitivity.py
"""

from __future__ import annotations

import csv
import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from gnnarrate import DiseaseAssociations, score_grounding
from gnnarrate.clarus_log import parse_clarus_log

LOGS = pathlib.Path("data/clarus_logs_kirc")
EXP = pathlib.Path("data/experiments")
OUT = pathlib.Path("data/results_comparison")
THRESHOLDS = [0.0, 0.01, 0.05, 0.1, 0.2, 0.3, 0.5]


def main() -> int:
    configs = sorted(d.name for d in EXP.glob("*") if d.is_dir())
    # Load every narrative once; rescoring is cheap, re-reading is not.
    corpus = {}
    for c in configs:
        items = []
        for f in sorted((EXP / c).glob("narrative_*.txt")):
            pid = f.stem.replace("narrative_", "")
            log_file = LOGS / f"{pid}.txt"
            if not log_file.exists():
                continue
            items.append((parse_clarus_log(log_file.read_text(encoding="utf-8")),
                          f.read_text(encoding="utf-8")))
        if items:
            corpus[c] = items
    print(f"loaded {sum(len(v) for v in corpus.values())} narratives "
          f"across {len(corpus)} configurations\n")

    rows = []
    header = f"{'threshold':>10}" + "".join(f"{c[:11]:>13}" for c in corpus) + f"{'mean':>9}"
    print(header)
    for t in THRESHOLDS:
        assoc = DiseaseAssociations.from_tsv(
            "data/kirc_open_targets.tsv", disease="clear cell renal carcinoma",
            threshold=t, terms=["kidney", "renal", "carcinoma", "cancer", "tumor"])
        line, per_cfg = f"{t:>10.2f}", {}
        for c, items in corpus.items():
            vals = [g.grounding_precision for g in
                    (score_grounding(log, narr, assoc) for log, narr in items)
                    if g.grounding_precision is not None]
            m = statistics.fmean(vals) if vals else None
            per_cfg[c] = None if m is None else round(m, 3)
            line += f"{m:>13.3f}" if m is not None else f"{'-':>13}"
        vals = [v for v in per_cfg.values() if v is not None]
        overall = statistics.fmean(vals) if vals else 0.0
        line += f"{overall:>9.3f}"
        print(line)
        rows.append({"threshold": t, **per_cfg, "mean": round(overall, 3)})

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "threshold_sensitivity.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (OUT / "threshold_sensitivity.json").write_text(json.dumps(rows, indent=2),
                                                    encoding="utf-8")
    print(f"\nwrote {OUT/'threshold_sensitivity.csv'}")

    lo, hi = rows[0]["mean"], rows[-1]["mean"]
    print(f"\nmean grounding precision falls {lo:.3f} -> {hi:.3f} as the threshold "
          f"rises 0 -> {THRESHOLDS[-1]}")
    print("A permissive threshold is the generous reading; the paper's headline uses it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
