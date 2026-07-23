"""Score an LLM narrative against the CLARUS log it was generated from.

    python examples/score_faithfulness.py examples/sample_clarus_log.txt narrative.txt

With --demo, scores two built-in narratives (one faithful, one not) so you can
see the metrics without supplying your own.
"""

import argparse
import json
import pathlib
import sys

from gnnarrate import parse_clarus_log, score_faithfulness

_FAITHFUL = (
    "The model initially predicted class 0. Genes MGAT3 and MGAT4B dominated the "
    "decision. When MGAT3 was removed, the prediction flipped to class 1, showing "
    "MGAT3 had a misleading effect."
)
_UNFAITHFUL = (
    "The prediction was driven mainly by TP53 and BRCA1. Removing MGAT3 had no "
    "effect on the output, which stayed the same."
)


def _report(log, narrative: str, label: str, k: int) -> None:
    print(f"\n=== {label} ===")
    print(json.dumps(score_faithfulness(log, narrative, k=k).summary(), indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=pathlib.Path, help="CLARUS log file")
    parser.add_argument("narrative", type=pathlib.Path, nargs="?", help="Narrative text file")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--demo", action="store_true", help="Score built-in narratives")
    args = parser.parse_args()

    log = parse_clarus_log(args.log.read_text(encoding="utf-8"))

    if args.demo:
        _report(log, _FAITHFUL, "FAITHFUL narrative", args.top_k)
        _report(log, _UNFAITHFUL, "UNFAITHFUL narrative", args.top_k)
        return 0

    if not args.narrative:
        print("Provide a narrative file, or pass --demo", file=sys.stderr)
        return 1

    _report(log, args.narrative.read_text(encoding="utf-8"), args.narrative.name, args.top_k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
