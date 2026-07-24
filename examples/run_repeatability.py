"""Repeated generation, to characterise within-model variance.

Every configuration in the main comparison was generated once, so the reported
metrics carry no estimate of how much they move under resampling. This script
regenerates a patient subset several times for selected configurations and reports
the spread, which is what licenses treating a single run as representative.

Load is placed mainly on OpenRouter models, whose credits are separate and cheap;
one inexpensive Anthropic model is included so the claim covers both providers.

    python examples/run_repeatability.py --configs kimi,deepseek,haiku --patients 40 --repeats 3
    python examples/run_repeatability.py --score-only
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from gnnarrate import DiseaseAssociations, score_faithfulness, score_grounding
from gnnarrate.benchmark import llm_generator
from gnnarrate.clarus_log import parse_clarus_log
from gnnarrate.config import load_env, use_utf8_stdout

from run_model_comparison import LOGS_DIR, MODELS  # noqa: E402

OUT = pathlib.Path("data/repeatability")


def retry(fn, *a, attempts=4, **k):
    for i in range(attempts):
        try:
            return fn(*a, **k)
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(4 * (i + 1))


def generate(configs, n_patients, repeats):
    logs = sorted(LOGS_DIR.glob("*.txt"))[:n_patients]
    for name in configs:
        provider, model_id, variant = MODELS[name]
        gen = llm_generator(provider=provider)
        for r in range(1, repeats + 1):
            d = OUT / f"{name}_run{r}"
            d.mkdir(parents=True, exist_ok=True)
            made = 0
            for p in logs:
                f = d / f"narrative_{p.stem}.txt"
                if f.exists() and f.read_text(encoding="utf-8").strip():
                    continue
                try:
                    f.write_text(retry(gen, p.read_text(encoding="utf-8"), model_id, variant),
                                 encoding="utf-8")
                    made += 1
                except Exception as e:
                    print(f"    {name} run{r} {p.stem}: {type(e).__name__}", flush=True)
            print(f"  {name} run{r}: {made} new, "
                  f"{len(list(d.glob('narrative_*.txt')))} total", flush=True)


def score(configs, repeats, assoc):
    report = {}
    print(f"\n{'config':<12}{'runs':>5}{'grounding precision per run':>34}"
          f"{'mean':>8}{'SD':>7}{'range':>8}")
    for name in configs:
        per_run = []
        for r in range(1, repeats + 1):
            d = OUT / f"{name}_run{r}"
            if not d.exists():
                continue
            vals = []
            for f in sorted(d.glob("narrative_*.txt")):
                pid = f.stem.replace("narrative_", "")
                log = parse_clarus_log((LOGS_DIR / f"{pid}.txt").read_text(encoding="utf-8"))
                g = score_grounding(log, f.read_text(encoding="utf-8"), assoc)
                if g.grounding_precision is not None:
                    vals.append(g.grounding_precision)
            if vals:
                per_run.append(statistics.fmean(vals))
        if not per_run:
            continue
        mean = statistics.fmean(per_run)
        sd = statistics.stdev(per_run) if len(per_run) > 1 else 0.0
        rng = max(per_run) - min(per_run)
        report[name] = {"runs": len(per_run), "per_run": [round(v, 3) for v in per_run],
                        "mean": round(mean, 3), "sd": round(sd, 3), "range": round(rng, 3)}
        shown = ", ".join(f"{v:.3f}" for v in per_run)
        print(f"{name:<12}{len(per_run):>5}{shown:>34}{mean:>8.3f}{sd:>7.3f}{rng:>8.3f}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "repeatability.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT/'repeatability.json'}")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--configs", default="kimi,deepseek,haiku")
    ap.add_argument("--patients", type=int, default=40)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--score-only", action="store_true")
    args = ap.parse_args()

    load_env()
    use_utf8_stdout()
    configs = [c.strip() for c in args.configs.split(",") if c.strip()]
    unknown = [c for c in configs if c not in MODELS]
    if unknown:
        print(f"unknown configs: {unknown}", file=sys.stderr)
        return 1

    assoc = DiseaseAssociations.from_tsv(
        "data/kirc_open_targets.tsv", disease="clear cell renal carcinoma",
        terms=["kidney", "renal", "carcinoma", "cancer", "tumor"])

    if not args.score_only:
        print(f"generating {args.repeats} runs x {args.patients} patients "
              f"for {configs}", flush=True)
        generate(configs, args.patients, args.repeats)
    score(configs, args.repeats, assoc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
