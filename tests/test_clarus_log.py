import pathlib

import pytest

from gnnarrate.clarus_log import parse_clarus_log

SAMPLE = (
    pathlib.Path(__file__).parent.parent / "examples" / "sample_clarus_log.txt"
).read_text(encoding="utf-8")


@pytest.fixture
def log():
    return parse_clarus_log(SAMPLE)


def test_dataset_and_state_count(log):
    assert log.dataset == "KIRC SubNet"
    assert len(log.states) == 3  # original + node deletion + edge deletion


def test_initial_state_prediction(log):
    s0 = log.states[0]
    assert s0.action is None
    assert (s0.true_label, s0.predicted_label) == (1, 0)
    assert s0.confidence == -0.36


def test_node_relevance_and_ranking(log):
    s0 = log.states[0]
    assert s0.node_relevance["MGAT3"] == 0.87
    assert s0.top_nodes(k=2) == ["MGAT3", "MGAT4B"]


def test_edge_relevance_parsed(log):
    s0 = log.states[0]
    assert s0.edge_relevance[("MGAT3", "MGAT4B")]["Saliency"] == 0.8
    assert s0.edge_relevance[("MGAT4B", "MGAT5B")]["IG"] == 1.0


def test_confusion_and_metrics(log):
    s0 = log.states[0]
    assert s0.confusion == {"TN": 21, "FP": 29, "FN": 6, "TP": 71}
    assert s0.sensitivity == 0.92


def test_actions_recorded(log):
    assert log.states[1].action == ("node_deleted", "MGAT3")
    assert log.states[2].action == ("edge_deleted", "MGAT4B", "MGAT5")


def test_node_deletion_flips_prediction(log):
    changes = log.prediction_changes()
    first = changes[0]  # deleting MGAT3
    assert first.action == ("node_deleted", "MGAT3")
    assert first.flipped is True            # predicted 0 -> 1
    assert first.confidence_delta == pytest.approx(1.53 - (-0.36))


def test_vocabulary_covers_all_genes(log):
    assert {"MGAT3", "MGAT4B", "MGAT5", "MGAT5B"} <= log.node_vocabulary()


def test_empty_log_rejected():
    with pytest.raises(ValueError, match="empty"):
        parse_clarus_log("   ")
