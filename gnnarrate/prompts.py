"""Prompt construction for narrating CLARUS explanation logs.

CLARUS emits a dense, machine-oriented log: relevance scores per node and edge,
confusion-matrix counts, and prediction deltas after each graph edit. This module
turns that log into a prompt that asks an LLM for a two-part narrative per patient
-- a short summary and a longer causal explanation.
"""

from __future__ import annotations

DEFAULT_XAI_METHODS = ("GNNExplainer", "Integrated Gradients", "Saliency")


def generate_gnn_explanation_prompt(
    log_text: str,
    dataset_name: str = "KIRC SubNet",
    xai_methods: tuple[str, ...] = DEFAULT_XAI_METHODS,
    include_model_metrics: bool = True,
    interpretability_focus: bool = True,
    biomedical_context: bool = True,
    max_sentences: int = 8,
    verbose: bool = False,
) -> str:
    """Build the LLM prompt for a CLARUS explanation log.

    Args:
        log_text: Raw CLARUS log. May cover several patients; each patient's
            section is narrated separately.
        dataset_name: Dataset the log came from, quoted back to the model so it
            can ground its biomedical claims.
        xai_methods: Attribution methods present in the log. Named explicitly so
            the model can comment on disagreement between them.
        include_model_metrics: Ask the model to account for sensitivity and
            specificity when a prediction was wrong.
        interpretability_focus: Ask *why* each element mattered, not just which
            ones ranked highest.
        biomedical_context: Allow the model to connect findings to known
            gene-disease associations.
        max_sentences: Ceiling on the detailed explanation, per patient.
        verbose: Ask for interpretation of conflicting attribution signals.

    Returns:
        The full prompt, with the log appended.
    """
    if not log_text or not log_text.strip():
        raise ValueError("log_text is empty; nothing to explain")

    methods = ", ".join(xai_methods)

    prompt = f"""You are an AI assistant helping biomedical researchers interpret predictions made by a Graph Neural Network (GNN) using data from the '{dataset_name}' dataset.

The input below contains a raw explanation log from CLARUS, which includes predictions, relevance scores, and model behavior after graph edits (e.g., node/edge removal). Each log section corresponds to a **different patient**.

Your task is to write **two outputs for each patient**:

1. **Summary** — a short (2–3 sentence) plain-language overview of the model's decision.
2. **Explanation** — a detailed causal reasoning narrative (up to {max_sentences} sentences), expanding on *why* the model made that decision.

---

**Instructions for each patient explanation:**

- In the **Summary**, state the model's prediction and its confidence/correctness in plain terms.
- In the **Explanation**, describe:
  - The model's original prediction and whether it was correct.
  - Which **nodes (features)** or **edges (connections)** had the greatest causal influence.
  - If removing an element (node/edge) **changed the prediction**, explain how and why.
  - Any **disagreement between XAI methods** ({methods}), and what that might imply.
- Label each case clearly, e.g., **"Patient 1 - Summary"**, **"Patient 1 - Explanation"**."""

    if interpretability_focus:
        prompt += (
            "\n- Keep the focus causal: not just *what* influenced the prediction, "
            "but *how* it pushed the model toward or away from a class."
        )

    if include_model_metrics:
        prompt += (
            "\n- Where a prediction was incorrect, consider what in the data or the "
            "reported sensitivity/specificity might explain the error."
        )

    if biomedical_context:
        prompt += (
            f"\n- Relate findings to known biomedical context where possible — for "
            f"instance, if a gene highlighted in '{dataset_name}' has an established "
            f"link to the disease. Say when such a link is speculative."
        )

    if verbose:
        prompt += (
            "\n- If two attribution methods disagree on what mattered, say what that "
            "might mean: one may track sharp transitions while another tracks steadier "
            "accumulated importance."
        )

    prompt += f"""

Think of the **Summary** as the quick takeaway, and the **Explanation** as the detailed reasoning story.

Below is the raw explanation log:

---

{log_text.strip()}
"""

    return prompt
