"""Find a narrative that illustrates the audit's two verdicts in one case.

A good worked example is faithful to the model (high recall, nothing fabricated)
while asserting at least one supported and at least one unsupported gene-disease
link, so a reader can see both halves of the audit disagreeing about the same
text. Ranks candidates and prints the best few with their verdicts.

    python examples/find_worked_example.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from gnnarrate import DiseaseAssociations, score_faithfulness, score_grounding
from gnnarrate.clarus_log import parse_clarus_log

LOGS = pathlib.Path("data/clarus_logs_kirc")
CONFIG = pathlib.Path("data/experiments/opus_default")


def main() -> int:
    assoc = DiseaseAssociations.from_tsv(
        "data/kirc_open_targets.tsv", disease="clear cell renal carcinoma",
        terms=["kidney", "renal", "carcinoma", "cancer", "tumor"])

    cands = []
    for f in sorted(CONFIG.glob("narrative_*.txt")):
        pid = f.stem.replace("narrative_", "")
        log_file = LOGS / f"{pid}.txt"
        if not log_file.exists():
            continue
        log = parse_clarus_log(log_file.read_text(encoding="utf-8"))
        narr = f.read_text(encoding="utf-8")
        fa = score_faithfulness(log, narr, k=3)
        gr = score_grounding(log, narr, assoc)
        if not (gr.supported and gr.unsupported):
            continue                      # need both verdicts present
        if fa.top_k_recall < 1.0 or fa.unverified_entities:
            continue                      # need clean faithfulness
        # Prefer short narratives with few claims: easiest to show in a paper.
        cands.append((len(gr.claimed_genes), len(narr), pid, fa, gr, narr))

    cands.sort()
    print(f"{len(cands)} candidates that are faithful yet partly ungrounded\n")
    for n_claims, length, pid, fa, gr, narr in cands[:4]:
        print(f"=== {pid}  ({length} chars, {n_claims} claims) ===")
        print(f"  recall       : {fa.top_k_recall:.2f}  (top genes {fa.top_nodes})")
        print(f"  fabricated   : {len(fa.unverified_entities)}")
        print(f"  supported    : {gr.supported}")
        print(f"  UNSUPPORTED  : {gr.unsupported}")
        print()
    if cands:
        best = cands[0]
        pathlib.Path("data/results_comparison/worked_example.txt").write_text(
            f"patient: {best[2]}\n\n{best[5]}", encoding="utf-8")
        print(f"best candidate written to data/results_comparison/worked_example.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
