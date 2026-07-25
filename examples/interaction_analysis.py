"""Do the LLM and the attribution architecture interact, or act independently?

The model comparison varies the narrator with the architecture fixed; the
architecture experiment varies the architecture with the narrator fixed. Read
together they answer a further question: is the ranking of narrators preserved
when the architecture changes?

  - Preserved ranking implies the two factors are separable, so the ten-model
    comparison generalises beyond the architecture it was run on.
  - Reordering implies an interaction, which bounds how far any single-architecture
    model comparison can be trusted.

Also reports which factor accounts for more of the spread in grounding precision.

Offline; rescoring only, no model calls.

    python examples/interaction_analysis.py
"""

from __future__ import annotations

import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from gnnarrate import DiseaseAssociations, score_faithfulness, score_grounding
from gnnarrate.clarus_log import parse_clarus_log

LOGS = pathlib.Path("data/clarus_logs_arch")
ARCH_OUT = pathlib.Path("data/results_arch")
RES = pathlib.Path("data/results_comparison")
ARCHS = ["gcn", "gin", "gat"]
LLMS = {"opus": "", "kimi": "_kimi"}      # dir suffix per narrator


def score_cell(arch: str, suffix: str, assoc):
    """Grounding precision and recall for one (architecture, narrator) cell."""
    d = ARCH_OUT / f"{arch}{suffix}"
    prec, rec = [], []
    for f in sorted(d.glob("narrative_*.txt")):
        pid = f.stem.replace("narrative_", "")
        lf = LOGS / arch / f"{pid}.txt"
        if not lf.exists():
            continue
        log = parse_clarus_log(lf.read_text(encoding="utf-8"))
        narr = f.read_text(encoding="utf-8")
        g = score_grounding(log, narr, assoc)
        if g.grounding_precision is not None:
            prec.append(g.grounding_precision)
        rec.append(score_faithfulness(log, narr, k=3).top_k_recall)
    if not prec:
        return None
    return {"n": len(rec), "grounding": statistics.fmean(prec),
            "recall": statistics.fmean(rec)}


def main() -> int:
    assoc = DiseaseAssociations.from_tsv(
        "data/kirc_open_targets.tsv", disease="clear cell renal carcinoma",
        terms=["kidney", "renal", "carcinoma", "cancer", "tumor"])

    grid = {}
    for llm, suffix in LLMS.items():
        for arch in ARCHS:
            cell = score_cell(arch, suffix, assoc)
            if cell:
                grid[(llm, arch)] = cell

    print("grounding precision by narrator x architecture\n")
    print(f"{'narrator':<10}" + "".join(f"{a.upper():>10}" for a in ARCHS) + f"{'spread':>10}")
    for llm in LLMS:
        vals = [grid.get((llm, a)) for a in ARCHS]
        if not all(vals):
            continue
        gs = [v["grounding"] for v in vals]
        print(f"{llm:<10}" + "".join(f"{g:>10.3f}" for g in gs)
              + f"{max(gs)-min(gs):>10.3f}")

    # Ranking preserved across architectures?
    print("\nnarrator ranking within each architecture:")
    consistent = True
    orders = {}
    for arch in ARCHS:
        cells = [(llm, grid[(llm, arch)]["grounding"]) for llm in LLMS
                 if (llm, arch) in grid]
        if len(cells) < 2:
            continue
        order = [c[0] for c in sorted(cells, key=lambda t: -t[1])]
        orders[arch] = order
        print(f"  {arch.upper():<5} " + " > ".join(
            f"{llm} ({dict(cells)[llm]:.3f})" for llm in order))
    if len(orders) > 1:
        first = list(orders.values())[0]
        consistent = all(o == first for o in orders.values())
        print(f"\n  ranking preserved across architectures: {consistent}")

    # Which factor moves grounding more?
    arch_spreads = []
    for llm in LLMS:
        gs = [grid[(llm, a)]["grounding"] for a in ARCHS if (llm, a) in grid]
        if len(gs) > 1:
            arch_spreads.append(max(gs) - min(gs))
    llm_spreads = []
    for arch in ARCHS:
        gs = [grid[(llm, arch)]["grounding"] for llm in LLMS if (llm, arch) in grid]
        if len(gs) > 1:
            llm_spreads.append(max(gs) - min(gs))

    out = {"grid": {f"{k[0]}|{k[1]}": v for k, v in grid.items()},
           "ranking_preserved": consistent,
           "mean_spread_across_architectures": round(statistics.fmean(arch_spreads), 3)
           if arch_spreads else None,
           "mean_spread_across_narrators": round(statistics.fmean(llm_spreads), 3)
           if llm_spreads else None}
    if arch_spreads and llm_spreads:
        a, l = out["mean_spread_across_architectures"], out["mean_spread_across_narrators"]
        print(f"\nmean spread when changing architecture (narrator fixed): {a:.3f}")
        print(f"mean spread when changing narrator (architecture fixed):  {l:.3f}")
        if l > 0:
            print(f"  -> architecture moves grounding {a/l:.1f}x as much as the narrator")

    RES.mkdir(parents=True, exist_ok=True)
    (RES / "interaction.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {RES/'interaction.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
