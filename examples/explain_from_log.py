"""Narrate a CLARUS log from the command line (default model: Claude Opus 4.8).

    python examples/explain_from_log.py examples/sample_clarus_log.txt
    python examples/explain_from_log.py my_log.txt --provider openai --dry-run
"""

import argparse
import pathlib
import sys

from gnnarrate import explain_model_prediction, generate_gnn_explanation_prompt
from gnnarrate.config import load_env, use_utf8_stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=pathlib.Path, help="Path to a CLARUS log file")
    parser.add_argument("--dataset", default="KIRC SubNet")
    parser.add_argument(
        "--provider", default="anthropic", choices=["anthropic", "openai", "groq"]
    )
    parser.add_argument("--model", default=None, help="Override the default model")
    parser.add_argument("--max-sentences", type=int, default=8)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the prompt without calling the API (no key needed)",
    )
    args = parser.parse_args()
    load_env()  # read .env so ANTHROPIC_API_KEY is available
    use_utf8_stdout()  # model output may contain non-ASCII (arrows, etc.)

    if not args.log.is_file():
        print(f"No such log file: {args.log}", file=sys.stderr)
        return 1

    prompt = generate_gnn_explanation_prompt(
        args.log.read_text(encoding="utf-8"),
        dataset_name=args.dataset,
        max_sentences=args.max_sentences,
        verbose=True,
    )

    if args.dry_run:
        print(prompt)
        return 0

    print(
        explain_model_prediction(prompt, provider=args.provider, model=args.model)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
