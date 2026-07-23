"""Run the full GNNarrate benchmark over a folder of CLARUS logs.

Offline demo (no key, no data needed) -- verifies the pipeline end to end:

    python examples/run_benchmark.py --demo

Real run (needs ANTHROPIC_API_KEY in the environment or .env, plus your data):

    python examples/run_benchmark.py \
        --logs data/clarus_logs \
        --associations data/kirc_open_targets.tsv \
        --disease "clear cell renal carcinoma" \
        --models claude-opus-4-8 \
        --variants default verbose \
        --out results

Writes <out>_rows.csv (per narrative) and <out>_aggregate.csv (per model/variant).
Fetch the associations file once with gnnarrate.opentargets (see README).
"""

import argparse
import json
import pathlib
import sys

from gnnarrate import DiseaseAssociations, NarrativeRecord, run_benchmark
from gnnarrate.benchmark import generate_records, llm_generator
from gnnarrate.clarus_log import parse_clarus_log
from gnnarrate.config import load_env

_SAMPLE = pathlib.Path(__file__).parent / "sample_clarus_log.txt"


def _disease_terms(name: str) -> list[str]:
    words = [w for w in name.lower().split() if len(w) > 3]
    return sorted(set(words) | {"cancer", "tumor", "tumour", "carcinoma"})


def _run_demo(top_k: int) -> int:
    """Offline: score built-in narratives against a synthetic KB across two models."""
    log = parse_clarus_log(_SAMPLE.read_text(encoding="utf-8"))
    assoc = DiseaseAssociations.from_dict(
        {"MGAT3": 0.42, "MGAT4B": 0.0, "MGAT5": 0.0, "MGAT5B": 0.0},
        disease="clear cell renal carcinoma",
        terms=["kidney", "renal", "carcinoma", "cancer"],
    )
    faithful = (
        "The model predicted class 0. MGAT3 and MGAT4B were most relevant. When "
        "MGAT3 was removed, the prediction flipped to class 1. MGAT3 is implicated "
        "in renal carcinoma."
    )
    unfaithful = (
        "The prediction was driven by TP53 and MGAT5. MGAT5 is a known driver of "
        "renal carcinoma. Removing MGAT3 had no effect."
    )
    records = [
        NarrativeRecord(item, log, text, model=model, prompt_variant="default")
        for model in ("claude-opus-4-8", "gpt-4o")
        for item, text in [("p0", faithful), ("p1", unfaithful)]
    ]
    _report(run_benchmark(records, assoc, k=top_k))
    return 0


def _run_real(args) -> int:
    log_dir = pathlib.Path(args.logs)
    log_files = sorted(log_dir.glob("*.txt"))
    if not log_files:
        print(f"No .txt logs found in {log_dir}", file=sys.stderr)
        return 1

    logs = [(p.stem, p.read_text(encoding="utf-8")) for p in log_files]
    associations = DiseaseAssociations.from_tsv(
        args.associations, disease=args.disease, terms=_disease_terms(args.disease)
    )
    generate = llm_generator(provider=args.provider)

    print(f"Generating narratives for {len(logs)} logs x {len(args.models)} models "
          f"x {len(args.variants)} variants via {args.provider}...", file=sys.stderr)
    records = generate_records(
        logs, generate, models=args.models, prompt_variants=args.variants
    )
    result = run_benchmark(records, associations, k=args.top_k)

    result.to_csv(f"{args.out}_rows.csv")
    result.aggregate_to_csv(f"{args.out}_aggregate.csv")
    print(f"\nWrote {args.out}_rows.csv and {args.out}_aggregate.csv", file=sys.stderr)
    _report(result)
    return 0


def _report(result) -> None:
    print("\n=== AGGREGATE (per model / prompt variant) ===")
    for row in result.aggregate():
        print(json.dumps(row))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--demo", action="store_true", help="Offline demo; no key or data")
    parser.add_argument("--logs", help="Folder of .txt CLARUS logs")
    parser.add_argument("--associations", help="Cached Open Targets TSV (gene<TAB>score)")
    parser.add_argument("--disease", default="clear cell renal carcinoma")
    parser.add_argument("--models", nargs="+", default=["claude-opus-4-8"])
    parser.add_argument("--variants", nargs="+", default=["default"])
    parser.add_argument("--provider", default="anthropic")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--out", default="benchmark")
    args = parser.parse_args()
    load_env()  # read .env so ANTHROPIC_API_KEY is available

    if args.demo:
        return _run_demo(args.top_k)
    if not args.logs or not args.associations:
        print("Provide --logs and --associations, or use --demo", file=sys.stderr)
        return 1
    return _run_real(args)


if __name__ == "__main__":
    raise SystemExit(main())
