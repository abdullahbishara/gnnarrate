"""Bootstrap confidence intervals for the attribution-quality measurements.

The raw per-patient Fidelity+/- and sparsity values are produced on the platform
(measure_attribution_quality.py, which needs the trained checkpoints). This turns
them into the same interval estimate every other table in the paper uses:
nonparametric bootstrap over patients, 2000 resamples, fixed seed.

    python examples/attribution_quality_ci.py
"""

from __future__ import annotations

import json
import pathlib
import random
import statistics
import sys

SRC = pathlib.Path("data/results_arch/attribution_quality.json")
SPEC = pathlib.Path("data/results_arch/attribution_specificity.json")
OUT = pathlib.Path("data/results_arch/attribution_quality_ci.json")
RESAMPLES = 2000
SEED = 20260725


def ci(values: list[float], resamples: int = RESAMPLES) -> dict:
    """Percentile bootstrap over patients, matching the paper's other intervals."""
    rng = random.Random(SEED)
    n = len(values)
    means = []
    for _ in range(resamples):
        means.append(statistics.fmean(rng.choices(values, k=n)))
    means.sort()
    return {"mean": round(statistics.fmean(values), 3),
            "lo": round(means[int(0.025 * resamples)], 3),
            "hi": round(means[int(0.975 * resamples) - 1], 3),
            "n": n}


def main() -> int:
    if not SRC.exists():
        print(f"{SRC} not found -- run measure_attribution_quality.py on the platform")
        return 1
    data = json.loads(SRC.read_text(encoding="utf-8"))
    spec = json.loads(SPEC.read_text(encoding="utf-8")) if SPEC.exists() else {}

    out = {}
    print(f"{'arch':<6}{'Fidelity+ (95% CI)':>26}{'Fidelity- (95% CI)':>26}"
          f"{'distinct':>10}{'Jaccard':>9}")
    for arch, v in data.items():
        raw = v.get("raw")
        if not raw:
            print(f"{arch}: no raw values; re-run the platform script")
            continue
        row = {"fidelity_plus": ci(raw["fidelity_plus"]),
               "fidelity_minus": ci(raw["fidelity_minus"]),
               "sparsity": ci(raw["sparsity"])}
        row["characterization_gap"] = round(
            row["fidelity_plus"]["mean"] - row["fidelity_minus"]["mean"], 3)
        s = spec.get(arch, {})
        row["distinct_genes_in_topk"] = s.get("distinct_genes_in_topk")
        row["mean_pairwise_jaccard"] = s.get("mean_pairwise_jaccard")
        row["n_genes_in_every_patient"] = s.get("n_genes_in_every_patient")
        row["genes_in_every_patient"] = s.get("genes_in_every_patient")
        out[arch] = row
        fp, fm = row["fidelity_plus"], row["fidelity_minus"]
        print(f"{arch:<6}{fp['mean']:>10.3f} [{fp['lo']:.3f}, {fp['hi']:.3f}]"
              f"{fm['mean']:>10.3f} [{fm['lo']:.3f}, {fm['hi']:.3f}]"
              f"{str(row['distinct_genes_in_topk']):>10}"
              f"{str(row['mean_pairwise_jaccard']):>9}")

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
