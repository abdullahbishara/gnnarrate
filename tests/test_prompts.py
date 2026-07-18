import pathlib

import pytest

from gnnarrate import generate_gnn_explanation_prompt

SAMPLE_LOG = (
    pathlib.Path(__file__).parent.parent / "examples" / "sample_clarus_log.txt"
).read_text(encoding="utf-8")


def test_log_is_embedded_verbatim():
    prompt = generate_gnn_explanation_prompt(SAMPLE_LOG)
    assert "Node MGAT3: 0.87" in prompt
    assert "Edge deleted between nodes: MGAT4B and MGAT5" in prompt


def test_dataset_name_is_quoted_back():
    prompt = generate_gnn_explanation_prompt(SAMPLE_LOG, dataset_name="PROTEINS")
    assert "'PROTEINS'" in prompt


def test_max_sentences_reaches_the_prompt():
    assert "up to 3 sentences" in generate_gnn_explanation_prompt(
        SAMPLE_LOG, max_sentences=3
    )


def test_xai_methods_are_named_for_disagreement_analysis():
    prompt = generate_gnn_explanation_prompt(
        SAMPLE_LOG, xai_methods=("Saliency", "PGExplainer")
    )
    assert "Saliency, PGExplainer" in prompt


@pytest.mark.parametrize(
    "flag,marker",
    [
        ("biomedical_context", "known biomedical context"),
        ("interpretability_focus", "Keep the focus causal"),
        ("include_model_metrics", "sensitivity/specificity"),
        ("verbose", "sharp transitions"),
    ],
)
def test_optional_sections_are_toggleable(flag, marker):
    """Every documented flag must actually change the prompt."""
    enabled = generate_gnn_explanation_prompt(SAMPLE_LOG, **{flag: True})
    disabled = generate_gnn_explanation_prompt(SAMPLE_LOG, **{flag: False})
    assert marker in enabled
    assert marker not in disabled


@pytest.mark.parametrize("empty", ["", "   \n  "])
def test_empty_log_is_rejected(empty):
    with pytest.raises(ValueError, match="empty"):
        generate_gnn_explanation_prompt(empty)
