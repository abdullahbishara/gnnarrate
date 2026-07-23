import pathlib

import pytest

from gnnarrate.clarus_log import parse_clarus_log
from gnnarrate.faithfulness import score_faithfulness

SAMPLE = (
    pathlib.Path(__file__).parent.parent / "examples" / "sample_clarus_log.txt"
).read_text(encoding="utf-8")

# Faithful: names the true top genes, correctly says removing MGAT3 flipped the class.
FAITHFUL = (
    "The model initially predicted class 0 for this patient. Genes MGAT3 and "
    "MGAT4B dominated the decision with the highest relevance. When MGAT3 was "
    "removed, the prediction flipped to class 1, revealing MGAT3 had a "
    "misleading effect. Later, deleting the MGAT4B and MGAT5 edge kept the "
    "prediction stable."
)

# Unfaithful: invents TP53/BRCA1, ignores the real top genes, denies the flip.
UNFAITHFUL = (
    "The prediction was driven mainly by TP53 and BRCA1. Removing MGAT3 had no "
    "effect on the model's output, which stayed the same throughout."
)


@pytest.fixture
def log():
    return parse_clarus_log(SAMPLE)


def test_faithful_narrative_high_recall(log):
    r = score_faithfulness(log, FAITHFUL, k=2)
    assert r.top_k_recall == 1.0                      # names MGAT3 and MGAT4B
    assert set(r.mentioned_top_nodes) == {"MGAT3", "MGAT4B"}
    assert r.unverified_entities == []                # invents nothing


def test_faithful_narrative_reports_flip_correctly(log):
    r = score_faithfulness(log, FAITHFUL, k=2)
    node_edit = next(e for e in r.edits if e.action == ("node_deleted", "MGAT3"))
    assert node_edit.mentioned is True
    assert node_edit.actually_flipped is True
    assert node_edit.narrative_claims_flip is True
    assert node_edit.direction_consistent is True
    assert r.direction_accuracy == 1.0


def test_unfaithful_narrative_flags_fabrication(log):
    r = score_faithfulness(log, UNFAITHFUL, k=2)
    assert "TP53" in r.unverified_entities
    assert "BRCA1" in r.unverified_entities
    # Names MGAT3 (only to deny its role) but not MGAT4B -> partial recall.
    # Recall measures whether a gene is named, not whether the claim is true;
    # the false claim about MGAT3 is caught by the direction check instead.
    assert r.top_k_recall == 0.5


def test_unfaithful_narrative_catches_wrong_direction(log):
    r = score_faithfulness(log, UNFAITHFUL, k=2)
    node_edit = next(e for e in r.edits if e.action == ("node_deleted", "MGAT3"))
    # It discusses MGAT3 and claims no change, but the deletion actually flipped it.
    assert node_edit.mentioned is True
    assert node_edit.narrative_claims_flip is False
    assert node_edit.direction_consistent is False


def test_method_acronyms_are_not_flagged_as_fabrication(log):
    r = score_faithfulness(log, "The GNN and the LLM used IG and Saliency.", k=2)
    assert r.unverified_entities == []                # GNN/LLM/IG are stopworded


def test_summary_is_serializable(log):
    s = score_faithfulness(log, FAITHFUL, k=2).summary()
    assert s["top_k_recall"] == 1.0
    assert set(s.keys()) >= {
        "top_k_recall", "edit_coverage", "direction_accuracy",
        "num_unverified_entities",
    }


def test_empty_narrative_rejected(log):
    with pytest.raises(ValueError, match="empty"):
        score_faithfulness(log, "   ")
