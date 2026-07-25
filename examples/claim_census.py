"""How much of a narrative's biomedical content does the verifier actually check?

The audit adjudicates one claim type: a gene in the patient graph linked to the
disease under study. Narratives assert more than that -- pathway roles, gene-gene
relationships, prognosis, subtype specificity, and claims about genes outside the
graph entirely. None of those are verified, so the reported hallucination rates are
lower bounds. This measures how much lower by counting biomedical assertions and
splitting them into checked and unchecked.

Classification is lexical and approximate; it is used to bound coverage, not to
adjudicate any individual sentence. Offline; no model calls.

    python examples/claim_census.py
"""

from __future__ import annotations

import csv
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from gnnarrate._textutil import has_term, mentions, sentences
from gnnarrate.clarus_log import parse_clarus_log

from _configs import reported_dirs

LOGS = pathlib.Path("data/clarus_logs_kirc")
EXP = pathlib.Path("data/experiments")
OUT = pathlib.Path("data/results_comparison")

DISEASE = ["kidney", "renal", "carcinoma", "cancer", "tumor", "tumour", "oncogen"]
# Biomedical assertion vocabulary beyond the gene-disease link we verify.
PATHWAY = re.compile(r"\b(pathway|signal\w*|cascade|axis|regulat\w+|express\w+|"
                     r"metabol\w+|immune|inflammat\w+|apoptos\w+|prolifer\w+|"
                     r"transcript\w+|kinase|receptor|transporter)\b", re.I)
PROGNOSIS = re.compile(r"\b(prognos\w+|surviv\w+|outcome|stage|grade|aggressiv\w+|"
                       r"metasta\w+|recurren\w+|subtype)\b", re.I)
GENELIKE = re.compile(r"\b[A-Z][A-Z0-9]{2,}\b")
STOP = frozenset({"GNN","GNNS","LLM","XAI","GCN","GIN","GAT","IG","AI","DNA","RNA",
                  "PPI","KIRC","TN","TP","FP","FN","AUC","ROC","CLARUS","MRNA"})


def main() -> int:
    rows = []
    print(f"{'config':<16}{'biomed sent':>12}{'checked':>9}{'unchecked':>11}{'coverage':>10}")
    for d in reported_dirs(EXP):
        checked = unchecked = 0
        kinds = {"pathway": 0, "prognosis": 0, "offgraph_gene": 0, "other": 0}
        for f in sorted(d.glob("narrative_*.txt")):
            pid = f.stem.replace("narrative_", "")
            lf = LOGS / f"{pid}.txt"
            if not lf.exists():
                continue
            log = parse_clarus_log(lf.read_text(encoding="utf-8"))
            vocab = log.node_vocabulary()
            for s in sentences(f.read_text(encoding="utf-8")):
                biomed = has_term(s, DISEASE) or PATHWAY.search(s) or PROGNOSIS.search(s)
                if not biomed:
                    continue
                # Checked: a graph gene co-occurring with a disease term -- exactly
                # what score_grounding adjudicates.
                if has_term(s, DISEASE) and any(mentions(g, s) for g in vocab):
                    checked += 1
                    continue
                unchecked += 1
                off = {t for t in GENELIKE.findall(s)} - vocab - STOP
                if off:
                    kinds["offgraph_gene"] += 1
                elif PATHWAY.search(s):
                    kinds["pathway"] += 1
                elif PROGNOSIS.search(s):
                    kinds["prognosis"] += 1
                else:
                    kinds["other"] += 1
        total = checked + unchecked
        if not total:
            continue
        cov = 100 * checked / total
        rows.append({"config": d.name, "biomedical_sentences": total,
                     "checked": checked, "unchecked": unchecked,
                     "coverage_pct": round(cov, 1), **kinds})
        print(f"{d.name:<16}{total:>12}{checked:>9}{unchecked:>11}{cov:>9.1f}%")

    tc = sum(r["checked"] for r in rows)
    tu = sum(r["unchecked"] for r in rows)
    print(f"\n{'TOTAL':<16}{tc+tu:>12}{tc:>9}{tu:>11}{100*tc/(tc+tu):>9.1f}%")
    print("\nunchecked breakdown:")
    for k in ("offgraph_gene", "pathway", "prognosis", "other"):
        n = sum(r[k] for r in rows)
        print(f"  {k:<16}{n:>6}  ({100*n/tu:.1f}% of unchecked)")

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "claim_census.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    (OUT / "claim_census.json").write_text(
        json.dumps({"per_config": rows, "total_checked": tc, "total_unchecked": tu,
                    "coverage_pct": round(100*tc/(tc+tu), 1)}, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT/'claim_census.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
