"""Benchmark runner: score many narratives and aggregate into paper tables.

Combines Tier 1 (structural faithfulness) and Tier 2 (gene-disease grounding) into
one record per narrative, then aggregates across a corpus grouped by model and
prompt variant.

Generation is injected as a callable, so this module never needs an API key: tests
pass a stub, production passes an LLM-backed function (see gnnarrate.llm). Scoring
and aggregation are pure and fully offline.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass

from .clarus_log import ParsedLog, parse_clarus_log
from .faithfulness import FaithfulnessReport, score_faithfulness
from .grounding import DiseaseAssociations, GroundingReport, score_grounding

# Prompt-flag presets a benchmark can vary the narrative over.
PROMPT_VARIANTS: dict[str, dict] = {
    "default": {},
    "verbose": {"verbose": True},
    "no_biomedical": {"biomedical_context": False},
}


@dataclass
class NarrativeRecord:
    """One narrative to score, with the log it came from and its provenance."""

    item_id: str
    log: ParsedLog
    narrative: str
    model: str = "unknown"
    prompt_variant: str = "default"


@dataclass
class ScoredRecord:
    item_id: str
    model: str
    prompt_variant: str
    faithfulness: FaithfulnessReport
    grounding: GroundingReport

    def metrics(self) -> dict:
        """Flat, CSV-ready metrics for this narrative."""
        f, g = self.faithfulness, self.grounding
        return {
            "item_id": self.item_id,
            "model": self.model,
            "prompt_variant": self.prompt_variant,
            "top_k_recall": f.top_k_recall,
            "edit_coverage": f.edit_coverage,
            "direction_accuracy": f.direction_accuracy,
            "num_fabricated": len(f.unverified_entities),
            "num_claimed": len(g.claimed_genes),
            "num_supported": len(g.supported),
            "num_unsupported": len(g.unsupported),
            "grounding_precision": g.grounding_precision,
        }


def _mean(values) -> float | None:
    """Mean over non-None values; None if there are none."""
    nums = [v for v in values if v is not None]
    return sum(nums) / len(nums) if nums else None


@dataclass
class BenchmarkResult:
    scored: list[ScoredRecord]

    def rows(self) -> list[dict]:
        return [s.metrics() for s in self.scored]

    def aggregate(self) -> list[dict]:
        """One summary row per (model, prompt_variant), sorted for stable output."""
        groups: dict[tuple[str, str], list[dict]] = {}
        for row in self.rows():
            groups.setdefault((row["model"], row["prompt_variant"]), []).append(row)

        summary = []
        for (model, variant), rows in sorted(groups.items()):
            summary.append({
                "model": model,
                "prompt_variant": variant,
                "n": len(rows),
                "mean_top_k_recall": _round(_mean([r["top_k_recall"] for r in rows])),
                "mean_edit_coverage": _round(_mean([r["edit_coverage"] for r in rows])),
                "mean_direction_accuracy": _round(
                    _mean([r["direction_accuracy"] for r in rows])
                ),
                "mean_grounding_precision": _round(
                    _mean([r["grounding_precision"] for r in rows])
                ),
                "total_fabricated": sum(r["num_fabricated"] for r in rows),
                "total_hallucination_candidates": sum(r["num_unsupported"] for r in rows),
            })
        return summary

    def to_csv(self, path) -> None:
        _write_csv(path, self.rows())

    def aggregate_to_csv(self, path) -> None:
        _write_csv(path, self.aggregate())


def _round(value, digits: int = 3):
    return None if value is None else round(value, digits)


def _write_csv(path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("no rows to write")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def score_record(
    record: NarrativeRecord, associations: DiseaseAssociations, k: int = 3
) -> ScoredRecord:
    return ScoredRecord(
        item_id=record.item_id,
        model=record.model,
        prompt_variant=record.prompt_variant,
        faithfulness=score_faithfulness(record.log, record.narrative, k=k),
        grounding=score_grounding(record.log, record.narrative, associations),
    )


def run_benchmark(
    records, associations: DiseaseAssociations, k: int = 3
) -> BenchmarkResult:
    """Score every record and return an aggregatable result."""
    return BenchmarkResult([score_record(r, associations, k=k) for r in records])


def generate_records(
    logs, generate_fn, models, prompt_variants
) -> list[NarrativeRecord]:
    """Build the corpus by generating a narrative per (log, model, variant).

    `logs` is an iterable of (item_id, raw_log_text). Each raw log is parsed once
    (for scoring) and passed as text to `generate_fn(log_text, model, variant)`,
    which returns narrative text -- a stub in tests, an LLM call in production.
    """
    records = []
    for item_id, raw_text in logs:
        parsed = parse_clarus_log(raw_text)
        for model in models:
            for variant in prompt_variants:
                narrative = generate_fn(raw_text, model, variant)
                records.append(
                    NarrativeRecord(item_id, parsed, narrative, model, variant)
                )
    return records


def llm_generator(provider: str = "anthropic", temperature: float = 1.0):
    """Build a generate_fn that turns a CLARUS log into a narrative via an LLM.

    `variant` selects a preset from PROMPT_VARIANTS (prompt-flag kwargs). `model`
    is the provider's model id. Needs an API key; not used by the test suite.
    """

    def _generate(log_text: str, model: str, variant: str) -> str:
        from .llm import explain_model_prediction
        from .prompts import generate_gnn_explanation_prompt

        kwargs = PROMPT_VARIANTS.get(variant, {})
        prompt = generate_gnn_explanation_prompt(log_text, **kwargs)
        return explain_model_prediction(
            prompt, provider=provider, model=model, temperature=temperature
        )

    return _generate
