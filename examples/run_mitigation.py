"""Run the mitigation loop over a corpus and report the before/after drop.

The headline result: how much does knowledge-base grounding reduce hallucinated
gene-disease claims across the whole set of narratives?

Offline demo (no key, no data):
    python examples/run_mitigation.py --demo

Real run (needs ANTHROPIC_API_KEY in .env, plus your data):
    python examples/run_mitigation.py \
        --logs data/clarus_logs \
        --associations data/kirc_open_targets.tsv \
        --disease "clear cell renal carcinoma" \
        --models claude-opus-4-8 --out mitigation

Writes <out>_rows.csv (per narrative) and <out>_aggregate.csv (per model/variant).
"""

import argparse
import json
import pathlib
import re
import sys

from gnnarrate import DiseaseAssociations, NarrativeRecord, run_batch_mitigation
from gnnarrate._textutil import mentions
from gnnarrate.benchmark import generate_records, llm_generator
from gnnarrate.clarus_log import parse_clarus_log
from gnnarrate.config import load_env, use_utf8_stdout
from gnnarrate.mitigation import llm_reviser

_SAMPLE = pathlib.Path(__file__).parent / "sample_clarus_log.txt"


def _disease_terms(name: str) -> list[str]:
    words = [w for w in name.lower().split() if len(w) > 3]
    return sorted(set(words) | {"cancer", "tumor", "tumour", "carcinoma"})


def _stub_reviser(narrative, unsupported_genes, disease):
    """Deterministic offline reviser: drop sentences with unsupported genes."""
    return " ".join(
        s for s in re.split(r"(?<=[.!?])\s+", narrative)
        if not any(mentions(g, s) for g in unsupported_genes)
    )


def _report(result) -> None:
    print("\n=== MITIGATION (before -> after, per model / variant) ===")
    for row in result.aggregate():
        print(json.dumps(row))


def _run_demo() -> int:
    log = parse_clarus_log(_SAMPLE.read_text(encoding="utf-8"))
    assoc = DiseaseAssociations.from_dict(
        {"MGAT3": 0.42, "MGAT4B": 0.0, "MGAT5": 0.0, "MGAT5B": 0.0},
        disease="clear cell renal carcinoma",
        terms=["kidney", "renal", "carcinoma", "cancer"],
    )
    narrative = (
        "MGAT3 is implicated in renal carcinoma and dominated the decision. "
        "MGAT5B is also a known driver of renal carcinoma."
    )
    records = [NarrativeRecord("p0", log, narrative, model="claude-opus-4-8")]
    _report(run_batch_mitigation(records, assoc, _stub_reviser))
    return 0


def _run_real(args) -> int:
    log_files = sorted(pathlib.Path(args.logs).glob("*.txt"))
    if not log_files:
        print(f"No .txt logs found in {args.logs}", file=sys.stderr)
        return 1

    logs = [(p.stem, p.read_text(encoding="utf-8")) for p in log_files]
    associations = DiseaseAssociations.from_tsv(
        args.associations, disease=args.disease, terms=_disease_terms(args.disease)
    )

    print(f"Generating narratives for {len(logs)} logs via {args.provider}...",
          file=sys.stderr)
    records = generate_records(
        logs, llm_generator(provider=args.provider),
        models=args.models, prompt_variants=args.variants,
    )
    print("Running mitigation (revising unsupported claims)...", file=sys.stderr)
    result = run_batch_mitigation(
        records, associations, llm_reviser(provider=args.provider)
    )

    result.to_csv(f"{args.out}_rows.csv")
    result.aggregate_to_csv(f"{args.out}_aggregate.csv")
    print(f"\nWrote {args.out}_rows.csv and {args.out}_aggregate.csv", file=sys.stderr)
    _report(result)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--demo", action="store_true", help="Offline demo; no key or data")
    parser.add_argument("--logs", help="Folder of .txt CLARUS logs")
    parser.add_argument("--associations", help="Cached Open Targets TSV")
    parser.add_argument("--disease", default="clear cell renal carcinoma")
    parser.add_argument("--models", nargs="+", default=["claude-opus-4-8"])
    parser.add_argument("--variants", nargs="+", default=["default"])
    parser.add_argument("--provider", default="anthropic")
    parser.add_argument("--out", default="mitigation")
    args = parser.parse_args()
    load_env()
    use_utf8_stdout()

    if args.demo:
        return _run_demo()
    if not args.logs or not args.associations:
        print("Provide --logs and --associations, or use --demo", file=sys.stderr)
        return 1
    return _run_real(args)


if __name__ == "__main__":
    raise SystemExit(main())
