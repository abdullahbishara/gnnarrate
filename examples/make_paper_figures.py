"""Generate the paper's result figures from the analysis CSVs.

Two figures, both straight from data/results_comparison/per_model.csv:

  fig_grounding.pdf  -- grounding precision per configuration with 95% CIs, which
                        shows at a glance that no model clears 0.5.
  fig_mechanism.pdf  -- hallucination exposure against claim volume, which shows
                        that exposure is governed by how much a model volunteers.

    python examples/make_paper_figures.py
"""

from __future__ import annotations

import csv
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SRC = pathlib.Path("data/results_comparison/per_model.csv")
OUT = pathlib.Path("../gnnarrate-paper/submission/figures")

# Names must match Table II of the manuscript exactly, so a reader moving between
# the figure and the table sees the same label for the same configuration.
LABEL = {
    "opus_default": "Opus 4.8",
    "opus5": "Opus 5",
    "opus_nobio": "Opus 4.8 (no bio. prompt)",
    "sonnet_default": "Sonnet 5",
    "haiku_default": "Haiku 4.5",
    "kimi": "Kimi K2",
    "glm": "GLM-4.6",
    "deepseek": "DeepSeek-V3",
    "qwen": "Qwen2.5-72B",
    "llama": "Llama-3.3-70B",
}
# Label offsets (pts) for the scatter, hand-set to stop the clustered points
# from overprinting each other.
OFFSET = {
    # the four top-right points sit within a few percent of each other, so their
    # labels are fanned out rather than offset uniformly
    "opus5": (-3, 7), "sonnet_default": (7, -1), "opus_default": (7, -8),
    "kimi": (-7, 1),
    # the mid cluster
    "haiku_default": (-7, 2), "deepseek": (0, -11), "glm": (7, 1),
    # the low cluster
    "llama": (7, -1), "qwen": (8, 1), "opus_nobio": (-2, -12),
}
HA = {"kimi": "right", "haiku_default": "right", "opus5": "right",
      "sonnet_default": "left", "opus_default": "left", "glm": "left",
      "llama": "left", "deepseek": "center", "qwen": "left",
      "opus_nobio": "center"}
PROP = "#3b6ea5"   # proprietary
OPEN = "#c1663a"   # open-weight

plt.rcParams.update({
    "font.family": "serif", "font.size": 8,
    "axes.linewidth": .6, "xtick.major.width": .6, "ytick.major.width": .6,
    "axes.spines.top": False, "axes.spines.right": False,
})


def load():
    rows = list(csv.DictReader(open(SRC, newline="", encoding="utf-8")))
    for r in rows:
        r["label"] = LABEL.get(r["config"], r["config"])
        for k in ("grounding_precision", "precision_lo", "precision_hi",
                  "pct_making_a_claim", "pct_with_unsupported_claim"):
            r[k] = float(r[k])
        r["n"] = int(r["n"])
        r["color"] = PROP if r["kind"] == "proprietary" else OPEN
    return rows


def fig_grounding(rows):
    rows = sorted(rows, key=lambda r: r["grounding_precision"])
    fig, ax = plt.subplots(figsize=(3.4, 2.9))
    y = range(len(rows))
    for i, r in enumerate(rows):
        ax.plot([r["precision_lo"], r["precision_hi"]], [i, i],
                color=r["color"], lw=1.4, solid_capstyle="round", alpha=.75)
        ax.plot(r["grounding_precision"], i, "o", color=r["color"], ms=4.5, zorder=3)
    ax.axvline(0.5, color="0.35", ls="--", lw=.7, zorder=1)
    ax.text(0.505, len(rows) - .55, "half of claims", fontsize=6.5, color="0.35")
    ax.set_yticks(list(y))
    ax.set_yticklabels([f"{r['label']}  ($n$={r['n']})" for r in rows], fontsize=6.8)
    ax.set_xlabel("Grounding precision (95% CI)")
    ax.set_xlim(0.1, 1.0)
    ax.set_ylim(-0.8, len(rows) - 0.2)
    ax.tick_params(length=2)
    h = [plt.Line2D([], [], color=PROP, marker="o", ls="-", ms=4, lw=1.4),
         plt.Line2D([], [], color=OPEN, marker="o", ls="-", ms=4, lw=1.4)]
    ax.legend(h, ["proprietary", "open-weight"], fontsize=6.5, frameon=False,
              loc="upper right", bbox_to_anchor=(1.02, .28), handlelength=1.4)
    fig.tight_layout(pad=.3)
    p = OUT / "fig_grounding.pdf"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return p


def fig_mechanism(rows):
    fig, ax = plt.subplots(figsize=(3.4, 2.7))
    for r in rows:
        x, y = r["pct_making_a_claim"] * 100, r["pct_with_unsupported_claim"] * 100
        ax.plot(x, y, "o", color=r["color"], ms=5, zorder=3)
        short = r["label"].replace(" (no bio. prompt)", "\n(no bio. prompt)")
        ax.annotate(short, (x, y), textcoords="offset points",
                    xytext=OFFSET.get(r["config"], (0, -10)),
                    ha=HA.get(r["config"], "center"), fontsize=5.6, color="0.25")
    ax.plot([0, 108], [0, 108], color="0.6", ls=":", lw=.7, zorder=1)
    # Annotate the diagonal in the empty region above it, clear of every point.
    ax.text(30, 104, "every asserted link unsupported", fontsize=6, color="0.5",
            ha="left", va="top")
    ax.set_xlabel("Narratives asserting a gene-disease link (%)")
    ax.set_ylabel("Narratives with an\nunsupported claim (%)")
    ax.set_xlim(14, 126)
    ax.set_ylim(8, 112)
    ax.tick_params(length=2)
    fig.tight_layout(pad=.3)
    p = OUT / "fig_mechanism.pdf"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return p


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load()
    for p in (fig_grounding(rows), fig_mechanism(rows)):
        print(f"wrote {p.resolve()}  ({p.stat().st_size/1024:.0f} KB)")
    print(f"\nfrom {len(rows)} configurations, "
          f"{sum(r['n'] for r in rows)} narratives")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
