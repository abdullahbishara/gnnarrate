"""Do narratives describe the modality the evidence actually came from?

Each node in these graphs carries two measurements: mRNA expression and DNA
methylation. The attribution the narrator receives is computed over both, then
pooled to a single per-gene relevance, so the modality that drove a gene's
importance is not recoverable from the log the narrator reads.

That creates a specific failure mode for multimodal explanation. If narratives
describe every gene in transcriptomic language -- "overexpressed", "upregulated"
-- while half the input is epigenomic, the prose asserts a mechanism the
evidence does not distinguish. This counts the vocabulary actually used.

Offline; no model calls.

    python examples/modality_language.py
"""

from __future__ import annotations

import csv
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from gnnarrate._textutil import sentences

from _configs import reported_dirs

EXP = pathlib.Path("data/experiments")
OUT = pathlib.Path("data/results_comparison")

# Vocabulary that commits to one modality as the mechanism.
TRANSCRIPTOMIC = re.compile(
    r"\b(overexpress\w*|underexpress\w*|up-?regulat\w*|down-?regulat\w*|"
    r"expression levels?|gene expression|mRNA|transcript\w*|transcription\w*)\b", re.I)
EPIGENOMIC = re.compile(
    r"\b(methylat\w*|hypermethylat\w*|hypomethylat\w*|epigenetic\w*|"
    r"CpG|promoter methylation|DNA methylation)\b", re.I)
# Language that correctly names both, or stays agnostic about which drove it.
BOTH = re.compile(r"\b(multi-?omic\w*|both modalit\w*|expression and methylation|"
                  r"methylation and expression|molecular profile\w*)\b", re.I)


def main() -> int:
    rows = []
    print(f"{'config':<16}{'narr':>6}{'transcriptomic':>16}{'epigenomic':>12}"
          f"{'both/agnostic':>15}")
    for d in reported_dirs(EXP):
        n = t_only = e_only = both = neither = 0
        t_sent = e_sent = 0
        for f in sorted(d.glob("narrative_*.txt")):
            text = f.read_text(encoding="utf-8")
            n += 1
            has_t = bool(TRANSCRIPTOMIC.search(text))
            has_e = bool(EPIGENOMIC.search(text))
            has_b = bool(BOTH.search(text))
            t_sent += sum(1 for s in sentences(text) if TRANSCRIPTOMIC.search(s))
            e_sent += sum(1 for s in sentences(text) if EPIGENOMIC.search(s))
            if has_b:
                both += 1
            elif has_t and not has_e:
                t_only += 1
            elif has_e and not has_t:
                e_only += 1
            elif has_t and has_e:
                both += 1
            else:
                neither += 1
        if not n:
            continue
        rows.append({"config": d.name, "narratives": n,
                     "pct_transcriptomic_only": round(100 * t_only / n, 1),
                     "pct_epigenomic_only": round(100 * e_only / n, 1),
                     "pct_both_or_agnostic": round(100 * both / n, 1),
                     "pct_neither": round(100 * neither / n, 1),
                     "transcriptomic_sentences": t_sent,
                     "epigenomic_sentences": e_sent})
        print(f"{d.name:<16}{n:>6}{100*t_only/n:>15.1f}%{100*e_only/n:>11.1f}%"
              f"{100*both/n:>14.1f}%")

    tot_n = sum(r["narratives"] for r in rows)
    ts = sum(r["transcriptomic_sentences"] for r in rows)
    es = sum(r["epigenomic_sentences"] for r in rows)
    t_only_all = sum(r["pct_transcriptomic_only"] * r["narratives"] for r in rows) / tot_n
    both_all = sum(r["pct_both_or_agnostic"] * r["narratives"] for r in rows) / tot_n
    print(f"\n{'ALL':<16}{tot_n:>6}{t_only_all:>15.1f}%{'':>12}{both_all:>14.1f}%")
    print(f"\nmodality-committed sentences: {ts} transcriptomic, {es} epigenomic")
    if ts + es:
        print(f"  transcriptomic share: {100*ts/(ts+es):.1f}%")

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "modality_language.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    (OUT / "modality_language.json").write_text(json.dumps(
        {"per_config": rows, "total_narratives": tot_n,
         "transcriptomic_sentences": ts, "epigenomic_sentences": es,
         "pct_transcriptomic_only": round(t_only_all, 1),
         "pct_both_or_agnostic": round(both_all, 1),
         "transcriptomic_share_of_modality_sentences":
             round(100 * ts / (ts + es), 1) if ts + es else None},
        indent=2), encoding="utf-8")
    print(f"\nwrote {OUT/'modality_language.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
