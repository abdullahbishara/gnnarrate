"""Recompute the headline grounding numbers on kidney patients only.

The TCGA barcodes distributed with this benchmark show the cohort is not purely
kidney: the target separates KIRC patients from a mixture that includes breast
and lung cancer cases. The grounding audit asks whether an asserted gene is
associated with clear cell renal carcinoma, which is the wrong question for a
breast or lung patient -- correct biology for their disease scores as
unsupported.

This recomputes every configuration on the kidney subset, using the narratives
already generated, so the effect of the contamination can be read directly.

    python examples/cohort_purity_impact.py
"""

from __future__ import annotations

import csv
import io
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from gnnarrate import DiseaseAssociations, score_grounding
from gnnarrate.clarus_log import parse_clarus_log

from _configs import reported_dirs

LOGS = pathlib.Path("data/clarus_logs_kirc")
EXP = pathlib.Path("data/experiments")
OUT = pathlib.Path("data/results_comparison/cohort_purity.json")
BARCODES = pathlib.Path("data/kirc_barcodes.tsv")

KIRC_TSS = {"3Z", "6D", "A3", "AK", "AS", "B0", "B2", "B4", "B8", "BP", "CB",
            "CJ", "CW", "CZ", "DV", "DW", "EU", "GK", "MM", "MW", "T7", "G6"}


def kidney_indices() -> set[int]:
    """Dataset indices whose TCGA barcode belongs to a kidney source site."""
    rows = [l.split("\t") for l in
            io.open(BARCODES, encoding="utf-8").read().strip().split("\n")[1:]]
    return {i for i, (barcode, _) in enumerate(rows)
            if barcode.split("-")[1] in KIRC_TSS}


def main() -> int:
    if not BARCODES.exists():
        print(f"missing {BARCODES}; export the target barcodes first")
        return 1
    keep = kidney_indices()
    assoc = DiseaseAssociations.from_tsv(
        "data/kirc_open_targets.tsv", disease="clear cell renal carcinoma",
        terms=["kidney", "renal", "carcinoma", "cancer", "tumor"])

    rows = []
    print(f"{'config':<16}{'all':>18}{'kidney only':>18}{'delta':>9}")
    for d in reported_dirs(EXP):
        allp, kid = [], []
        for f in sorted(d.glob("narrative_*.txt")):
            pid = f.stem.replace("narrative_", "")
            m = re.search(r"(\d+)", pid)
            if not m:
                continue
            idx = int(m.group(1))
            lf = LOGS / f"{pid}.txt"
            if not lf.exists():
                continue
            log = parse_clarus_log(lf.read_text(encoding="utf-8"))
            s = score_grounding(log, f.read_text(encoding="utf-8"), assoc)
            p = s.grounding_precision
            if p is None:          # narrative asserted no gene-disease link
                continue
            allp.append(p)
            if idx in keep:
                kid.append(p)
        if not allp:
            continue
        a = sum(allp) / len(allp)
        k = sum(kid) / len(kid) if kid else float("nan")
        rows.append({"config": d.name, "n_all": len(allp), "grounding_all": round(a, 3),
                     "n_kidney": len(kid), "grounding_kidney": round(k, 3),
                     "delta": round(k - a, 3)})
        print(f"{d.name:<16}{a:>10.3f} (n={len(allp):>3}){k:>10.3f} (n={len(kid):>3})"
              f"{k - a:>+9.3f}")

    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    ma = sum(r["grounding_all"] for r in rows) / len(rows)
    mk = sum(r["grounding_kidney"] for r in rows) / len(rows)
    print(f"\nmean across configurations: all={ma:.3f}  kidney-only={mk:.3f}  "
          f"delta={mk - ma:+.3f}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
