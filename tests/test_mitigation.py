import pathlib
import re

import pytest

from gnnarrate._textutil import mentions
from gnnarrate.clarus_log import parse_clarus_log
from gnnarrate.grounding import DiseaseAssociations, GroundingReport
from gnnarrate.mitigation import (
    build_revision_prompt,
    measure_mitigation,
    mitigate,
)

SAMPLE = (
    pathlib.Path(__file__).parent.parent / "examples" / "sample_clarus_log.txt"
).read_text(encoding="utf-8")

ASSOC = DiseaseAssociations.from_dict(
    {"MGAT3": 0.42, "MGAT4B": 0.0, "MGAT5": 0.0, "MGAT5B": 0.0},
    disease="kidney renal clear cell carcinoma",
    terms=["kidney", "renal", "carcinoma", "cancer"],
)

# Asserts an unsupported disease link for MGAT5 -> one hallucination candidate.
UNSUPPORTED = (
    "MGAT3 and MGAT4B drove the prediction. MGAT5 is a known driver of kidney cancer."
)
# Only a supported claim (MGAT3) -> nothing to mitigate.
SUPPORTED_ONLY = "MGAT3 is implicated in kidney cancer and dominated the decision."


@pytest.fixture
def log():
    return parse_clarus_log(SAMPLE)


def _sentence_dropping_reviser(narrative, unsupported_genes, disease):
    """Deterministic stub: delete any sentence mentioning an unsupported gene."""
    kept = [
        s for s in re.split(r"(?<=[.!?])\s+", narrative)
        if not any(mentions(g, s) for g in unsupported_genes)
    ]
    return " ".join(kept)


def test_revision_prompt_names_genes_and_disease():
    prompt = build_revision_prompt("some narrative", ["MGAT5", "MGAT7"], "kidney cancer")
    assert "MGAT5" in prompt and "MGAT7" in prompt
    assert "kidney cancer" in prompt
    assert "Revise" in prompt


def test_measure_mitigation_math():
    before = GroundingReport("d", ["A", "B"], supported=[], unsupported=["A", "B"],
                             associations_available=True)
    after = GroundingReport("d", ["A", "B"], supported=["A"], unsupported=["B"],
                            associations_available=True)
    result = measure_mitigation(before, after)
    assert result.hallucinations_before == 2
    assert result.hallucinations_after == 1
    assert result.reduction == 1
    assert result.reduction_rate == 0.5


def test_mitigate_removes_unsupported_claim(log):
    revised, result = mitigate(log, UNSUPPORTED, ASSOC, _sentence_dropping_reviser)
    assert result.hallucinations_before == 1          # MGAT5
    assert result.hallucinations_after == 0           # sentence dropped
    assert result.reduction_rate == 1.0
    assert "MGAT5" not in revised
    # The supported MGAT3 content must survive.
    assert "MGAT3" in revised


def test_mitigate_skips_when_nothing_unsupported(log):
    def exploding_reviser(*_args):
        raise AssertionError("reviser must not be called when nothing is unsupported")

    revised, result = mitigate(log, SUPPORTED_ONLY, ASSOC, exploding_reviser)
    assert revised == SUPPORTED_ONLY                  # unchanged
    assert result.hallucinations_before == 0
    assert result.reduction == 0
    assert result.reduction_rate is None              # nothing to reduce


def test_summary_shape(log):
    _, result = mitigate(log, UNSUPPORTED, ASSOC, _sentence_dropping_reviser)
    s = result.summary()
    assert s["hallucinations_before"] == 1
    assert s["hallucinations_after"] == 0
    assert s["reduction_rate"] == 1.0
