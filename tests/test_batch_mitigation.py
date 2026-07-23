import csv
import pathlib
import re

import pytest

from gnnarrate._textutil import mentions
from gnnarrate.benchmark import NarrativeRecord, run_batch_mitigation
from gnnarrate.clarus_log import parse_clarus_log
from gnnarrate.grounding import DiseaseAssociations

SAMPLE = (
    pathlib.Path(__file__).parent.parent / "examples" / "sample_clarus_log.txt"
).read_text(encoding="utf-8")

ASSOC = DiseaseAssociations.from_dict(
    {"MGAT3": 0.42, "MGAT4B": 0.0, "MGAT5": 0.0, "MGAT5B": 0.0},
    disease="clear cell renal carcinoma",
    terms=["kidney", "renal", "carcinoma", "cancer"],
)

# One unsupported disease claim (MGAT5), plus a supported one (MGAT3).
UNSUPPORTED = "MGAT3 is implicated in renal carcinoma. MGAT5 also drives renal carcinoma."
# No unsupported claims -> nothing to mitigate.
CLEAN = "MGAT3 is implicated in renal carcinoma and dominated the decision."


@pytest.fixture
def log():
    return parse_clarus_log(SAMPLE)


def _dropping_reviser(narrative, unsupported_genes, disease):
    """Delete sentences that mention an unsupported gene."""
    return " ".join(
        s for s in re.split(r"(?<=[.!?])\s+", narrative)
        if not any(mentions(g, s) for g in unsupported_genes)
    )


def _noop_reviser(narrative, unsupported_genes, disease):
    """Revision that changes nothing -- models the mitigation failing to help."""
    return narrative


def _records(log):
    return [
        NarrativeRecord("p0", log, UNSUPPORTED, model="claude-opus-4-8"),
        NarrativeRecord("p1", log, CLEAN, model="claude-opus-4-8"),
        NarrativeRecord("p0", log, UNSUPPORTED, model="gpt-4o"),
    ]


def test_batch_reduces_hallucinations(log):
    result = run_batch_mitigation(_records(log), ASSOC, _dropping_reviser)
    rows = {(r["item_id"], r["model"]): r for r in result.rows()}

    fixed = rows[("p0", "claude-opus-4-8")]
    assert fixed["hallucinations_before"] == 1
    assert fixed["hallucinations_after"] == 0
    assert fixed["reduction_rate"] == 1.0

    clean = rows[("p1", "claude-opus-4-8")]
    assert clean["hallucinations_before"] == 0
    assert clean["reduction_rate"] is None            # nothing to reduce


def test_aggregate_corpus_reduction_rate(log):
    agg = {row["model"]: row for row in
           run_batch_mitigation(_records(log), ASSOC, _dropping_reviser).aggregate()}

    opus = agg["claude-opus-4-8"]
    assert opus["n"] == 2
    assert opus["hallucinations_before"] == 1         # p0 has 1, p1 has 0
    assert opus["hallucinations_after"] == 0
    assert opus["overall_reduction_rate"] == 1.0
    # mean over per-narrative rates ignores the None (the clean record).
    assert opus["mean_reduction_rate"] == 1.0


def test_failed_revision_shows_zero_reduction(log):
    records = [NarrativeRecord("p0", log, UNSUPPORTED, model="m")]
    agg = run_batch_mitigation(records, ASSOC, _noop_reviser).aggregate()[0]
    assert agg["hallucinations_before"] == 1
    assert agg["hallucinations_after"] == 1           # reviser did nothing
    assert agg["overall_reduction_rate"] == 0.0


def test_rows_and_aggregate_to_csv(tmp_path, log):
    result = run_batch_mitigation(_records(log), ASSOC, _dropping_reviser)

    rows_path = tmp_path / "mit_rows.csv"
    agg_path = tmp_path / "mit_agg.csv"
    result.to_csv(rows_path)
    result.aggregate_to_csv(agg_path)

    with open(rows_path, newline="", encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == 3
    with open(agg_path, newline="", encoding="utf-8") as f:
        agg_rows = list(csv.DictReader(f))
    assert len(agg_rows) == 2
    assert {"overall_reduction_rate", "hallucinations_before"} <= set(agg_rows[0])
