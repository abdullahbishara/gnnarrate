"""Score expert annotations against the knowledge-base labels.

Reports the two numbers the paper needs:

1. **Validation of the proxy** -- how often each expert agrees with the automatic
   (Open Targets) label. This is what licenses interpreting grounding precision as
   a hallucination measure rather than a bare knowledge-base lookup.
2. **Inter-annotator agreement** -- how often the two experts agree with each
   other (Cohen's kappa). Without it, a reviewer cannot tell whether the task is
   well posed or the labels are arbitrary.

    python examples/score_annotation.py data/annotation/annotations_*.json
"""

from __future__ import annotations

import argparse
import glob
import json
import pathlib

from gnnarrate.annotation import compute_agreement


def kappa(a: list[str], b: list[str]) -> float | None:
    """Cohen's kappa between two label sequences."""
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    labels = set(a) | set(b)
    pe = sum((a.count(k) / n) * (b.count(k) / n) for k in labels)
    return None if pe == 1 else (po - pe) / (1 - pe)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+", help="annotator JSON exports (globs ok)")
    ap.add_argument("--key", default="data/annotation/answer_key.json")
    ap.add_argument("--drop-unsure", action="store_true", default=True)
    args = ap.parse_args()

    key = json.loads(pathlib.Path(args.key).read_text(encoding="utf-8"))

    paths: list[str] = []
    for f in args.files:
        paths.extend(sorted(glob.glob(f)) or [f])

    loaded = {}
    for p in paths:
        d = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
        loaded[d["annotator"]] = d["answers"]

    print(f"disease claims in key: {len(key)}\n")

    # --- 1. each expert vs the knowledge base ---
    print("=== Expert vs. knowledge base (validates the proxy) ===")
    per_expert = {}
    for name, ans in loaded.items():
        rows = []
        for cid, label in ans.items():
            if cid not in key:
                continue
            if args.drop_unsure and label == "unsure":
                continue
            rows.append({"auto_label": key[cid]["auto_label"], "expert_label": label})
        res = compute_agreement(rows)
        n_unsure = sum(1 for v in ans.values() if v == "unsure")
        per_expert[name] = res
        acc = res["accuracy"]
        k = res["cohen_kappa"]
        print(f"  {name:<12} n={res['n_labeled']:<4} "
              f"agreement={acc:.3f}" if acc is not None else f"  {name}: no labels")
        if k is not None:
            print(f"  {'':<12} kappa={k:.3f}   (unsure, excluded: {n_unsure})")

    # --- 2. expert vs expert ---
    if len(loaded) >= 2:
        names = list(loaded)
        a_name, b_name = names[0], names[1]
        shared = [c for c in loaded[a_name] if c in loaded[b_name] and c in key]
        if args.drop_unsure:
            shared = [c for c in shared
                      if loaded[a_name][c] != "unsure" and loaded[b_name][c] != "unsure"]
        a = [loaded[a_name][c] for c in shared]
        b = [loaded[b_name][c] for c in shared]
        if shared:
            agree = sum(x == y for x, y in zip(a, b)) / len(shared)
            k = kappa(a, b)
            print(f"\n=== Inter-annotator ({a_name} vs {b_name}) ===")
            print(f"  n={len(shared)}  raw agreement={agree:.3f}"
                  + (f"  kappa={k:.3f}" if k is not None else ""))
        else:
            print("\n(no overlapping claims judged by both annotators yet)")
    else:
        print("\n(only one annotator file; inter-annotator agreement needs two)")

    print("\nInterpretation: high expert-vs-KB agreement means grounding precision "
          "tracks expert judgement.\nLow agreement means the knowledge base is "
          "missing associations the experts recognise, and\ngrounding precision "
          "should be reported as a lower bound only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
