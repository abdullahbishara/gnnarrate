"""How many flagged claims are hedged rather than asserted?

Grounding flags a gene-disease link whenever an unsupported gene co-occurs with a
disease term. That treats

    "MGAT5 is a known driver of renal carcinoma"

and

    "MGAT5 may plausibly relate to renal carcinoma, though this is speculative"

identically, yet only the first is a confident false assertion. A model that marks
its uncertainty is behaving better than one that does not, and conflating the two
overstates hallucination for careful models.

This measures the split, giving a stricter rate alongside the headline figure.
Offline; no model calls.

    python examples/hedging_analysis.py
"""

from __future__ import annotations

import csv
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from gnnarrate import DiseaseAssociations
from gnnarrate._textutil import has_term, mentions, sentences
from gnnarrate.clarus_log import parse_clarus_log

LOGS = pathlib.Path("data/clarus_logs_kirc")
EXP = pathlib.Path("data/experiments")
OUT = pathlib.Path("data/results_comparison")

# Epistemic markers. Deliberately broad: the aim is to identify claims a reader
# would not take as asserted fact.
HEDGE = re.compile(
    r"\b(may|might|could|possibly|plausibl\w+|speculativ\w+|suggest\w*|potential\w*|"
    r"appears?\sto|seems?\sto|likely|unclear|uncertain|hypothes\w+|warrant\w*\s"
    r"(?:further|experimental)|pending\s\w+\svalidation|not\s+establish\w+|"
    r"remains?\s+to\s+be|would\s+need|candidate)\b", re.IGNORECASE)


def main() -> int:
    assoc = DiseaseAssociations.from_tsv(
        "data/kirc_open_targets.tsv", disease="clear cell renal carcinoma",
        terms=["kidney", "renal", "carcinoma", "cancer", "tumor"])
    terms = assoc.terms

    rows = []
    print(f"{'config':<16}{'flagged':>9}{'hedged':>9}{'asserted':>10}{'hedged %':>10}")
    for d in sorted(p for p in EXP.glob("*") if p.is_dir()):
        flagged = hedged = 0
        for f in sorted(d.glob("narrative_*.txt")):
            pid = f.stem.replace("narrative_", "")
            log_file = LOGS / f"{pid}.txt"
            if not log_file.exists():
                continue
            log = parse_clarus_log(log_file.read_text(encoding="utf-8"))
            narr = f.read_text(encoding="utf-8")
            vocab = log.node_vocabulary()
            for s in sentences(narr):
                if not has_term(s, terms):
                    continue
                for gene in vocab:
                    if mentions(gene, s) and not assoc.is_associated(gene):
                        flagged += 1
                        if HEDGE.search(s):
                            hedged += 1
        if not flagged:
            continue
        pct = 100 * hedged / flagged
        rows.append({"config": d.name, "flagged": flagged, "hedged": hedged,
                     "asserted": flagged - hedged, "hedged_pct": round(pct, 1)})
        print(f"{d.name:<16}{flagged:>9}{hedged:>9}{flagged-hedged:>10}{pct:>9.1f}%")

    tot_f = sum(r["flagged"] for r in rows)
    tot_h = sum(r["hedged"] for r in rows)
    print(f"\n{'TOTAL':<16}{tot_f:>9}{tot_h:>9}{tot_f-tot_h:>10}"
          f"{100*tot_h/tot_f:>9.1f}%")

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "hedging.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    (OUT / "hedging.json").write_text(
        json.dumps({"per_config": rows,
                    "total_flagged": tot_f, "total_hedged": tot_h,
                    "hedged_pct": round(100 * tot_h / tot_f, 1)}, indent=2),
        encoding="utf-8")
    print(f"\nwrote {OUT/'hedging.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
