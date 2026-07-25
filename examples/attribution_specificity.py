"""How patient-specific are the patient-specific explanations?

The premise of a per-patient explanation is that it reflects that patient. If an
explainer returns nearly the same genes for everyone, its relevance ranking is a
property of the trained model rather than of the individual, and any groundedness
score it earns is really a score for one fixed gene list.

This measures, per architecture, how much the top-k sets vary across patients:
the number of distinct genes that ever appear, mean pairwise Jaccard overlap, and
the genes present for essentially every patient.

Offline; reads the architecture logs.

    python examples/attribution_specificity.py
"""

from __future__ import annotations

import collections
import itertools
import json
import pathlib
import re
import statistics
import sys

LOGS = pathlib.Path("data/clarus_logs_arch")
OUT = pathlib.Path("data/results_arch/attribution_specificity.json")
K = 5


def top_k(path: pathlib.Path, k: int = K) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [g for g, _ in re.findall(r"Node (\S+): ([\d.]+)", text)][:k]


def main() -> int:
    out = {}
    for arch in ("gcn", "gin", "gat"):
        d = LOGS / arch
        if not d.is_dir():
            continue
        sets = [set(top_k(p)) for p in sorted(d.glob("patient_*.txt"))]
        sets = [s for s in sets if s]
        if len(sets) < 2:
            continue
        pair = [len(a & b) / len(a | b) for a, b in itertools.combinations(sets, 2)]
        counts = collections.Counter(g for s in sets for g in s)
        n = len(sets)
        universal = sorted(g for g, c in counts.items() if c == n)
        out[arch] = {
            "patients": n,
            "k": K,
            "distinct_genes_in_topk": len(counts),
            "mean_pairwise_jaccard": round(statistics.fmean(pair), 3),
            "genes_in_every_patient": universal,
            "n_genes_in_every_patient": len(universal),
            "most_common": counts.most_common(6),
        }
        print(f"{arch:<5} patients={n:<4} distinct top-{K} genes={len(counts):<5} "
              f"mean Jaccard={statistics.fmean(pair):.3f}  "
              f"in every patient={len(universal)}")
        print(f"      always present: {universal}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")
    print("\nJaccard 1.0 means every patient receives the same top-k gene set.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
