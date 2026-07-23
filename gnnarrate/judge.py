"""LLM-as-judge for counterfactual direction faithfulness.

The lexical direction check in `faithfulness.py` cannot tell a real class flip from
a confidence change or a negated "did not flip" -- it conflates them and produces
unreliable numbers. This module asks a separate model to read the narrative and say
whether it claims the *predicted class* flipped, then compares that to the ground
truth taken from the log (not from any model). Use a different model as the judge
than the one that wrote the narrative, to avoid self-grading.

The judge is injected (like `llm_reviser`), so scoring and aggregation are testable
with a stub and no API key.
"""

from __future__ import annotations

from dataclasses import dataclass

from .clarus_log import ParsedLog

_JUDGE_PROMPT = """An AI explained a graph neural network's prediction after one gene was deleted from a patient's graph.

Read the explanation and decide ONE thing: does it state that the model's PREDICTED CLASS changed to the other class (flipped) after the deletion, or that the predicted class stayed the SAME? A change in confidence WITHOUT a change in the predicted class counts as SAME.

Answer with exactly one word: FLIPPED, SAME, or UNCLEAR.

Explanation:
\"\"\"
{narrative}
\"\"\""""

_VERDICTS = {"FLIPPED": True, "SAME": False, "UNCLEAR": None}


@dataclass
class DirectionResult:
    actual_flip: bool
    narrative_claims_flip: bool | None   # None when the judge says UNCLEAR
    correct: bool | None                 # None when unjudgeable


def score_direction(log: ParsedLog, narrative: str, judge_fn) -> DirectionResult | None:
    """Compare the narrative's claimed flip (per `judge_fn`) to the log's ground truth.

    `judge_fn(narrative) -> "FLIPPED" | "SAME" | "UNCLEAR"`. Returns None if the log
    has no counterfactual edit to judge. Scores the first edit (single-deletion logs).
    """
    changes = log.prediction_changes()
    if not changes:
        return None
    actual = bool(changes[0].flipped)

    verdict = judge_fn(narrative).strip().upper()
    claims = next((_VERDICTS[t] for t in _VERDICTS if t in verdict), None)
    correct = None if claims is None else (claims == actual)
    return DirectionResult(actual, claims, correct)


def aggregate_direction(results) -> dict:
    """Accuracy overall and split by whether the prediction actually flipped."""
    res = [r for r in results if r is not None]
    judged = [r for r in res if r.correct is not None]
    flips = [r for r in judged if r.actual_flip]
    nonflips = [r for r in judged if not r.actual_flip]

    def acc(rows):
        return sum(r.correct for r in rows) / len(rows) if rows else None

    return {
        "n": len(res),
        "n_judged": len(judged),
        "n_unclear": len(res) - len(judged),
        "direction_accuracy": acc(judged),
        "acc_on_flips": acc(flips),
        "acc_on_nonflips": acc(nonflips),
        "n_flips": len(flips),
    }


def llm_direction_judge(model: str = "claude-haiku-4-5-20251001",
                        provider: str = "anthropic", temperature: float = 0.0):
    """Build an LLM-backed judge to pass into `score_direction` (needs an API key)."""

    def _judge(narrative: str) -> str:
        from .llm import explain_model_prediction

        answer = explain_model_prediction(
            _JUDGE_PROMPT.format(narrative=narrative),
            provider=provider, model=model, temperature=temperature,
        ).strip().upper()
        return next((t for t in _VERDICTS if t in answer), "UNCLEAR")

    return _judge
