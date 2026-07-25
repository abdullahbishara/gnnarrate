"""Does a narrative convey the *relative* importance of genes, not just name them?

Top-k recall counts whether a gene the model relied on is mentioned. A narrative
that names the three most relevant genes but presents them in the wrong order
scores perfectly, even though a reader would take away the wrong emphasis. This
measures ordering: genes are ranked by the order in which the narrative first
mentions them, and that ranking is correlated (Spearman) with the attribution
log's relevance ranking.

Order of first mention is a proxy for emphasis, not a perfect one -- a narrative
may introduce a gene early and then discount it. It is nonetheless checkable
without annotation, and it detects the failure mode that recall cannot see.

Offline; no model calls.

    python examples/emphasis_analysis.py
"""

from __future__ import annotations

import csv
import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from gnnarrate._textutil import mentions
from gnnarrate.clarus_log import parse_clarus_log

from _configs import reported_dirs

LOGS = pathlib.Path("data/clarus_logs_kirc")
EXP = pathlib.Path("data/experiments")
OUT = pathlib.Path("data/results_comparison")
K = 5


def spearman(a: list[float], b: list[float]) -> float | None:
    """Spearman rho for two equal-length rank vectors (no ties expected)."""
    n = len(a)
    if n < 2:
        return None
    d2 = sum((x - y) ** 2 for x, y in zip(a, b))
    denom = n * (n * n - 1)
    return None if denom == 0 else 1 - (6 * d2) / denom


def first_mention_index(narrative: str, gene: str) -> int | None:
    """Character offset of the first whole-word mention, or None."""
    import re
    m = re.search(rf"\b{re.escape(gene)}\b", narrative, re.IGNORECASE)
    return m.start() if m else None


def main() -> int:
    rows = []
    print(f"{'config':<16}{'narratives':>11}{'mean rho':>10}{'exact order':>13}")
    for d in reported_dirs(EXP):
        rhos, exact, used = [], 0, 0
        for f in sorted(d.glob("narrative_*.txt")):
            pid = f.stem.replace("narrative_", "")
            log_file = LOGS / f"{pid}.txt"
            if not log_file.exists():
                continue
            log = parse_clarus_log(log_file.read_text(encoding="utf-8"))
            if not log.states:
                continue
            top = log.states[0].top_nodes(K)
            narr = f.read_text(encoding="utf-8")

            # Keep only genes the narrative actually mentions; ordering is undefined
            # for the rest, and recall already accounts for their absence.
            present = [(g, first_mention_index(narr, g)) for g in top]
            present = [(g, i) for g, i in present if i is not None]
            if len(present) < 3:
                continue
            used += 1
            log_rank = {g: r for r, (g, _) in enumerate(
                [(g, None) for g in top if any(g == p[0] for p in present)])}
            by_text = sorted(present, key=lambda t: t[1])
            text_rank = {g: r for r, (g, _) in enumerate(by_text)}
            genes = [g for g, _ in present]
            rho = spearman([log_rank[g] for g in genes], [text_rank[g] for g in genes])
            if rho is not None:
                rhos.append(rho)
                if rho == 1.0:
                    exact += 1
        if not rhos:
            continue
        mean_rho = statistics.fmean(rhos)
        pct_exact = 100 * exact / len(rhos)
        rows.append({"config": d.name, "narratives": used,
                     "mean_spearman": round(mean_rho, 3),
                     "pct_exact_order": round(pct_exact, 1)})
        print(f"{d.name:<16}{used:>11}{mean_rho:>10.3f}{pct_exact:>12.1f}%")

    allr = [r["mean_spearman"] for r in rows]
    print(f"\n{'MEAN':<16}{'':>11}{statistics.fmean(allr):>10.3f}")
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "emphasis.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    (OUT / "emphasis.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT/'emphasis.csv'}")
    print("\nrho = 1.0 means mention order matches relevance order exactly;")
    print("rho = 0 means mention order carries no information about relevance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
