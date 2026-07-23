import pathlib

from gnnarrate.clarus_log import parse_clarus_log
from gnnarrate.judge import DirectionResult, aggregate_direction, score_direction

# The sample log has a counterfactual node deletion (MGAT3) that flips the
# prediction 0 -> 1.
SAMPLE = (
    pathlib.Path(__file__).parent.parent / "examples" / "sample_clarus_log.txt"
).read_text(encoding="utf-8")


def test_ground_truth_flip_detected():
    log = parse_clarus_log(SAMPLE)
    assert log.prediction_changes()[0].flipped is True


def test_judge_correct_when_it_matches_ground_truth():
    log = parse_clarus_log(SAMPLE)
    r = score_direction(log, "narrative", judge_fn=lambda n: "FLIPPED")
    assert r.actual_flip is True
    assert r.narrative_claims_flip is True
    assert r.correct is True


def test_judge_wrong_when_it_denies_a_real_flip():
    log = parse_clarus_log(SAMPLE)
    r = score_direction(log, "narrative", judge_fn=lambda n: "SAME")
    assert r.narrative_claims_flip is False
    assert r.correct is False


def test_unclear_verdict_is_unjudged():
    log = parse_clarus_log(SAMPLE)
    r = score_direction(log, "narrative", judge_fn=lambda n: "UNCLEAR")
    assert r.narrative_claims_flip is None
    assert r.correct is None


def test_verbose_judge_answer_is_parsed():
    log = parse_clarus_log(SAMPLE)
    r = score_direction(log, "narrative", judge_fn=lambda n: "I think it FLIPPED, yes.")
    assert r.narrative_claims_flip is True


def test_no_counterfactual_edit_returns_none():
    single_state = (
        "Dataset selected: KIRC\n"
        "Patient Information: True label = 1, Predicted label = 1, "
        "GNNs prediction confidence = 0.5\n"
        "Node relevance scores:\nNode MGAT3: 0.8\n"
    )
    assert score_direction(parse_clarus_log(single_state), "x", judge_fn=lambda n: "SAME") is None


def test_aggregate_splits_flips_and_nonflips():
    results = [
        DirectionResult(actual_flip=True, narrative_claims_flip=True, correct=True),
        DirectionResult(actual_flip=False, narrative_claims_flip=False, correct=True),
        DirectionResult(actual_flip=False, narrative_claims_flip=True, correct=False),
        DirectionResult(actual_flip=False, narrative_claims_flip=None, correct=None),
        None,
    ]
    agg = aggregate_direction(results)
    assert agg["n"] == 4                      # the None is dropped
    assert agg["n_judged"] == 3               # one UNCLEAR excluded
    assert agg["n_unclear"] == 1
    assert agg["acc_on_flips"] == 1.0         # 1/1
    assert abs(agg["acc_on_nonflips"] - 0.5) < 1e-9   # 1/2
