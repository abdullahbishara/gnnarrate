"""Open vs. proprietary model comparison over the CLARUS log corpus.

Generates one narrative per (patient, model), scoring is left to the analysis
step. Designed to be cheap and safe to re-run:

* **Resumes** -- an existing non-empty narrative file is never regenerated, so
  the Anthropic runs already paid for are reused as-is.
* **Per-patient isolation** -- one failing patient is recorded and skipped; it
  never aborts the rest of a model's run.
* **Truncation guard** -- responses that stop at the token cap are rejected and
  retried rather than silently biasing the scores.

Check model ids before spending anything:

    python examples/run_model_comparison.py --check

Then run (default: every patient in the corpus):

    python examples/run_model_comparison.py
    python examples/run_model_comparison.py --limit 25 --only kimi,glm
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

from gnnarrate.benchmark import PROMPT_VARIANTS, llm_generator
from gnnarrate.config import load_env, use_utf8_stdout

# Model ids follow each provider's own naming. OpenRouter ids can change --
# `--check` verifies every one of them with a single cheap call before a real run.
MODELS = {
    # name          provider       model id                              variant
    "opus":       ("anthropic",  "claude-opus-4-8",                     "default"),
    "sonnet":     ("anthropic",  "claude-sonnet-5",                     "default"),
    "haiku":      ("anthropic",  "claude-haiku-4-5-20251001",           "default"),
    "kimi":       ("openrouter", "moonshotai/kimi-k2",                  "default"),
    "glm":        ("openrouter", "z-ai/glm-4.6",                        "default"),
    "deepseek":   ("openrouter", "deepseek/deepseek-chat",              "default"),
    "qwen":       ("openrouter", "qwen/qwen-2.5-72b-instruct",          "default"),
    "llama":      ("openrouter", "meta-llama/llama-3.3-70b-instruct",   "default"),
    # Newest frontier model at time of submission, so the result is not tied to one
    # model generation.
    "opus5":      ("anthropic",  "claude-opus-5",                       "default"),
    # Ablation: same model, biomedical context switched off.
    "opus_nobio": ("anthropic",  "claude-opus-4-8",                     "no_biomedical"),
    "opus5_nobio":("anthropic",  "claude-opus-5",                       "no_biomedical"),
    # Template variant: same model and flags, tighter length budget.
    "opus_terse": ("anthropic",  "claude-opus-4-8",                     "terse"),
    "kimi_terse": ("openrouter", "moonshotai/kimi-k2",                  "terse"),
}

# Directory names already written by earlier runs, so those narratives are reused.
LEGACY_DIRS = {
    "opus": "opus_default",
    "sonnet": "sonnet_default",
    "haiku": "haiku_default",
    "opus_nobio": "opus_nobio",
}

LOGS_DIR = pathlib.Path("data/clarus_logs_kirc")
EXPERIMENTS = pathlib.Path("data/experiments")


def out_dir(name: str) -> pathlib.Path:
    return EXPERIMENTS / LEGACY_DIRS.get(name, name)


def generate_one(gen, log_text: str, model: str, variant: str, attempts: int = 4) -> str:
    """Generate a narrative, retrying transient failures and truncated output."""
    for attempt in range(attempts):
        try:
            text = gen(log_text, model, variant)
            # A response ending mid-word means the token cap clipped it.
            if text and not text.rstrip().endswith(("...",)) and len(text) > 200:
                return text
            raise RuntimeError("response too short or truncated")
        except Exception as exc:
            if attempt == attempts - 1:
                raise
            print(f"      retry {attempt + 1} after {type(exc).__name__}", flush=True)
            time.sleep(4 * (attempt + 1))
    raise RuntimeError("unreachable")


def check_models(names) -> int:
    """One tiny call per model to verify the id and key before a real run."""
    print("verifying model ids (1 short call each)...\n")
    ok = True
    for name in names:
        provider, model, _ = MODELS[name]
        try:
            from gnnarrate.llm import explain_model_prediction

            explain_model_prediction(
                "Reply with the single word: ok.",
                provider=provider, model=model, max_tokens=16,
            )
            print(f"  OK    {name:<11} {provider}/{model}")
        except Exception as exc:
            ok = False
            print(f"  FAIL  {name:<11} {provider}/{model}\n        {str(exc)[:140]}")
    print("\nall model ids valid" if ok else "\nfix the FAIL rows above before running")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify model ids, then exit")
    parser.add_argument("--limit", type=int, default=None, help="patients per model")
    parser.add_argument("--only", default=None, help="comma-separated subset of model names")
    args = parser.parse_args()

    load_env()
    use_utf8_stdout()

    names = [n.strip() for n in args.only.split(",")] if args.only else list(MODELS)
    unknown = [n for n in names if n not in MODELS]
    if unknown:
        print(f"unknown model name(s): {unknown}\nknown: {list(MODELS)}", file=sys.stderr)
        return 1

    if args.check:
        return check_models(names)

    logs = sorted(LOGS_DIR.glob("*.txt"))
    if args.limit:
        logs = logs[: args.limit]
    if not logs:
        print(f"no logs found in {LOGS_DIR}", file=sys.stderr)
        return 1

    report: dict[str, dict] = {}
    for name in names:
        provider, model, variant = MODELS[name]
        if variant not in PROMPT_VARIANTS:
            print(f"unknown prompt variant {variant!r} for {name}", file=sys.stderr)
            return 1

        dest = out_dir(name)
        dest.mkdir(parents=True, exist_ok=True)
        gen = llm_generator(provider=provider)

        reused = generated = 0
        failures: list[str] = []
        print(f"\n=== {name}: {provider}/{model} [{variant}] -> {dest} ===", flush=True)

        for i, log_path in enumerate(logs, start=1):
            target = dest / f"narrative_{log_path.stem}.txt"
            if target.exists() and target.read_text(encoding="utf-8").strip():
                reused += 1
                continue
            try:
                text = generate_one(
                    gen, log_path.read_text(encoding="utf-8"), model, variant
                )
            except Exception as exc:
                # Record and move on -- never abandon the whole model over one patient.
                failures.append(log_path.stem)
                print(f"  [{i}/{len(logs)}] FAILED {log_path.stem}: {str(exc)[:90]}", flush=True)
                continue
            target.write_text(text, encoding="utf-8")
            generated += 1
            if generated % 10 == 0:
                print(f"  [{i}/{len(logs)}] generated {generated}", flush=True)

        report[name] = {
            "provider": provider, "model": model, "variant": variant,
            "reused": reused, "generated": generated,
            "failed": len(failures), "failed_ids": failures[:20],
        }
        print(f"  done: {reused} reused, {generated} new, {len(failures)} failed", flush=True)

    EXPERIMENTS.mkdir(parents=True, exist_ok=True)
    (EXPERIMENTS / "generation_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print("\n=== GENERATION REPORT ===")
    print(json.dumps(report, indent=2))
    print(f"\nwrote {EXPERIMENTS / 'generation_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
