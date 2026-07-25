"""The serialised sensitivity/specificity must agree with the confusion matrix.

Every log in the current corpus states ``Sensitivity: 0.75%`` where the matrix
gives 75%. The narrator is asked to account for those figures, so a hundredfold
error propagates into the narratives, and the faithfulness audit never looked at
them. These tests pin the check that WP0 introduces and the corpus regenerated
in WP3 must satisfy.
"""

from __future__ import annotations

import pathlib

import pytest

from gnnarrate.clarus_log import parse_clarus_log

HEADER = (
    "Dataset selected: KIRC\n"
    "GNN TN: 35, FP: 12, FN: 20, TP: 60\n"
    "GNN Sensitivity: {sens}, Specificity: {spec}\n"
    "Currently selected: Patient 1, Graph 0\n"
    "Amount of modified graphs for this patient: 0\n"
    "Patient Information: In Test Data, True label = 1, Predicted label = 0, "
    "GNNs prediction confidence = 0.58\n"
    "Node relevance scores (top 2 of 1594 genes):\n"
    "Node WASL: 0.88\nNode CD4: 0.88\n"
)


def _state(sens: str, spec: str):
    """First graph state of a synthetic log; the metrics live on the state."""
    return parse_clarus_log(HEADER.format(sens=sens, spec=spec)).states[0]


def test_correct_percentages_are_accepted():
    # TP=60, FN=20 -> 75%.  TN=35, FP=12 -> 74.5%.
    assert _state("75%", "74.5%").metric_inconsistencies() == []


def test_fraction_written_as_percent_is_caught():
    """The exact defect in the released corpus."""
    problems = _state("0.75%", "0.74%").metric_inconsistencies()
    assert len(problems) == 2
    assert "sensitivity" in problems[0]
    assert "looks like a fraction written with a % sign" in problems[0]


def test_unrelated_wrong_value_is_caught_without_the_fraction_hint():
    problems = _state("40%", "74.5%").metric_inconsistencies()
    assert len(problems) == 1
    assert "fraction" not in problems[0]


def test_missing_metrics_are_not_flagged():
    text = HEADER.format(sens="75%", spec="74.5%").replace(
        "GNN Sensitivity: 75%, Specificity: 74.5%\n", "")
    assert parse_clarus_log(text).states[0].metric_inconsistencies() == []


@pytest.mark.parametrize("corpus", ["data/clarus_logs_kirc"])
def test_released_corpus_currently_fails_this_check(corpus):
    """Documents the defect until WP3 regenerates the corpus.

    Flip the assertion to `== 0` once regeneration lands; leaving it as a known
    failure would let the corpus quietly stay broken.
    """
    d = pathlib.Path(corpus)
    if not d.is_dir():
        pytest.skip(f"{corpus} not present")
    bad = 0
    for f in sorted(d.glob("patient_*.txt")):
        log = parse_clarus_log(f.read_text(encoding="utf-8"))
        if any(st.metric_inconsistencies() for st in log.states):
            bad += 1
    assert bad > 0, (
        "the corpus no longer shows the unit defect -- if it was regenerated, "
        "change this test to assert bad == 0")
