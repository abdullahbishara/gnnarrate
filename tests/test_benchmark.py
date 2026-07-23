import csv
import pathlib

import pytest

from gnnarrate.benchmark import (
    NarrativeRecord,
    generate_records,
    run_benchmark,
    score_record,
)
from gnnarrate.clarus_log import parse_clarus_log
from gnnarrate.grounding import DiseaseAssociations

SAMPLE = (
    pathlib.Path(__file__).parent.parent / "examples" / "sample_clarus_log.txt"
).read_text(encoding="utf-8")

# Synthetic associations: MGAT3 associated, the rest not.
ASSOC = DiseaseAssociations.from_dict(
    {"MGAT3": 0.42, "MGAT4B": 0.0, "MGAT5": 0.0, "MGAT5B": 0.0},
    disease="kidney renal clear cell carcinoma",
    terms=["kidney", "renal", "carcinoma", "cancer"],
)

# Faithful AND grounded: names true top genes, correct flip, a supported disease claim.
FAITHFUL = (
    "The model predicted class 0. MGAT3 and MGAT4B were most relevant. When MGAT3 "
    "was removed, the prediction flipped to class 1. MGAT3 is implicated in kidney cancer."
)
# Unfaithful AND ungrounded: fabricates TP53, wrong direction, unsupported disease claim.
UNFAITHFUL = (
    "The prediction was driven by TP53 and MGAT5. MGAT5 is a known driver of kidney "
    "cancer. Removing MGAT3 had no effect on the output."
)


@pytest.fixture
def log():
    return parse_clarus_log(SAMPLE)


def _records(log):
    return [
        NarrativeRecord("p0", log, FAITHFUL, model="gpt-4o", prompt_variant="default"),
        NarrativeRecord("p1", log, UNFAITHFUL, model="gpt-4o", prompt_variant="default"),
        NarrativeRecord("p0", log, FAITHFUL, model="llama3", prompt_variant="default"),
    ]


def test_single_record_scoring(log):
    r = score_record(_records(log)[0], ASSOC, k=2)
    m = r.metrics()
    assert m["top_k_recall"] == 1.0
    assert m["direction_accuracy"] == 1.0
    assert m["num_fabricated"] == 0
    assert m["grounding_precision"] == 1.0


def test_unfaithful_record_scoring(log):
    r = score_record(_records(log)[1], ASSOC, k=2)
    m = r.metrics()
    assert m["top_k_recall"] == 0.5           # mentions MGAT3 (to deny it), not MGAT4B
    assert m["direction_accuracy"] == 0.0     # claims no change, but it flipped
    assert m["num_fabricated"] == 1           # TP53
    assert m["grounding_precision"] == 0.0    # MGAT5 not associated
    assert m["num_unsupported"] == 1


def test_aggregate_groups_by_model_and_variant(log):
    result = run_benchmark(_records(log), ASSOC, k=2)
    agg = result.aggregate()
    assert len(agg) == 2                       # gpt-4o and llama3

    by_model = {row["model"]: row for row in agg}
    gpt = by_model["gpt-4o"]
    assert gpt["n"] == 2
    assert gpt["mean_top_k_recall"] == 0.75    # mean(1.0, 0.5)
    assert gpt["mean_direction_accuracy"] == 0.5   # mean(1.0, 0.0)
    assert gpt["mean_grounding_precision"] == 0.5  # mean(1.0, 0.0)
    assert gpt["total_fabricated"] == 1
    assert gpt["total_hallucination_candidates"] == 1

    llama = by_model["llama3"]
    assert llama["n"] == 1
    assert llama["mean_top_k_recall"] == 1.0


def test_rows_count_matches_records(log):
    result = run_benchmark(_records(log), ASSOC, k=2)
    assert len(result.rows()) == 3


def test_to_csv_roundtrip(tmp_path, log):
    result = run_benchmark(_records(log), ASSOC, k=2)
    path = tmp_path / "results.csv"
    result.to_csv(path)
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3
    assert rows[0]["model"] == "gpt-4o"


def test_aggregate_csv_written(tmp_path, log):
    result = run_benchmark(_records(log), ASSOC, k=2)
    path = tmp_path / "agg.csv"
    result.aggregate_to_csv(path)
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert {"model", "mean_top_k_recall", "total_hallucination_candidates"} <= set(rows[0])


def test_generate_records_with_stub(log):
    def stub(log, model, variant):
        return f"{model}/{variant} narrative for a graph"

    records = generate_records(
        [("p0", log)], stub, models=["a", "b"], prompt_variants=["x", "y"]
    )
    assert len(records) == 4                    # 2 models x 2 variants
    assert records[0].narrative == "a/x narrative for a graph"
    assert {r.model for r in records} == {"a", "b"}


def test_mean_ignores_none(log):
    # A narrative with no disease claim -> grounding_precision None -> skipped in mean.
    recs = [
        NarrativeRecord("p0", log, "MGAT3 had the highest relevance score.", model="m"),
        NarrativeRecord("p1", log, FAITHFUL, model="m"),
    ]
    agg = run_benchmark(recs, ASSOC, k=2).aggregate()[0]
    # Only FAITHFUL contributes a grounding precision (1.0); the other is None.
    assert agg["mean_grounding_precision"] == 1.0
