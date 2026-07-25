"""Structural faithfulness scoring: narrative vs. attribution log.

This measures whether an LLM narrative is faithful to the CLARUS log it was given
-- independent of whether its biology is correct (that is the job of the ontology
grounding stage). Three questions:

1. **Recall** -- does the narrative surface the nodes the model actually relied on
   (the top-k by relevance)?
2. **Fabrication** -- does it name gene-like entities that aren't in this patient's
   graph at all?
3. **Counterfactual direction** -- when it discusses a deletion, does it correctly
   state whether the prediction flipped?

Recall and fabrication use closed-vocabulary matching against the log and are
robust. The direction check is a documented lexical heuristic: it flags likely
disagreements for the expert-validation / LLM-judge stage rather than settling
them. Metrics are reported separately so the robust ones aren't diluted by the
heuristic one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ._textutil import mentions as _mentions, sentences as _sentences
from .clarus_log import ParsedLog

# All-uppercase alphanumeric tokens, length >= 3, starting with a letter.
# Catches gene symbols like MGAT3, TP53, BRCA1 (and method acronyms, removed via
# the stoplist below).
_CANDIDATE = re.compile(r"\b[A-Z][A-Z0-9]{2,}\b")

# Uppercase tokens that look like gene symbols but are not.
#
# Two groups. Method/dataset acronyms are obvious. The second group matters more:
# narratives routinely name pathways, protein families, structural domains and
# disease abbreviations, all of which are correct biology rather than invented
# genes. Counting them as fabrications inflates the measure -- inspection of one
# corpus found nearly every flagged token to be of this kind. Genuine gene symbols
# absent from the patient graph (NRF2, BRCA1) are deliberately NOT listed: those
# are real off-graph mentions and the metric should report them.
_STOPWORDS = frozenset({
    # method, dataset and reporting acronyms
    "GNN", "GNNS", "LLM", "LLMS", "XAI", "GCN", "GIN", "GAT", "CLARUS",
    "AI", "ML", "DNA", "RNA", "PPI", "KIRC", "MUTAG", "TN", "TP", "FP", "FN",
    "ROC", "AUC", "API", "SHAP", "LIME", "IG", "JBHI", "SI",
    # pathways, families, domains, receptor classes -- not gene symbols
    "RAS", "PI3K", "MAPK", "GPCR", "GPCRS", "S6K", "HECT", "WASP", "JAK",
    "STAT", "TGF", "NFKB", "MTOR", "ERK", "AMPK", "HIF", "ROS", "ECM",
    # disease and clinical abbreviations
    "RCC", "CCRCC", "TCGA", "OS", "PFS",
})

_FLIP_WORDS = re.compile(
    r"\b(flip|flipped|flips|revers\w+|switch\w+|correct\w+|"
    r"chang\w+|overturn\w+|from\s+class)\b",
    re.IGNORECASE,
)


@dataclass
class EditFaithfulness:
    """How faithfully the narrative reports one counterfactual edit."""

    action: tuple
    mentioned: bool
    actually_flipped: bool
    narrative_claims_flip: bool | None   # None when the edit isn't discussed
    direction_consistent: bool | None    # heuristic; None when undeterminable


@dataclass
class FaithfulnessReport:
    top_k: int
    top_nodes: list[str]
    mentioned_top_nodes: list[str]
    mentioned_known_nodes: list[str]
    unverified_entities: list[str]
    edits: list[EditFaithfulness] = field(default_factory=list)

    @property
    def top_k_recall(self) -> float:
        """Fraction of the model's top-k nodes the narrative names. Robust."""
        if not self.top_nodes:
            return 1.0
        return len(self.mentioned_top_nodes) / len(self.top_nodes)

    @property
    def edit_coverage(self) -> float:
        """Fraction of counterfactual edits the narrative discusses. Robust."""
        if not self.edits:
            return 1.0
        return sum(e.mentioned for e in self.edits) / len(self.edits)

    @property
    def direction_accuracy(self) -> float | None:
        """Of discussed edits, fraction whose flip/no-flip is stated correctly.

        WARNING: crude lexical heuristic -- it cannot separate a real class flip
        from a confidence change or a negated "did not flip", so its numbers are
        unreliable. Use `gnnarrate.judge.score_direction` (LLM-as-judge) for the
        real metric; keep this only as a cheap pre-filter.
        """
        judged = [e for e in self.edits if e.direction_consistent is not None]
        if not judged:
            return None
        return sum(e.direction_consistent for e in judged) / len(judged)

    def summary(self) -> dict:
        return {
            "top_k_recall": round(self.top_k_recall, 3),
            "edit_coverage": round(self.edit_coverage, 3),
            "direction_accuracy": (
                None if self.direction_accuracy is None
                else round(self.direction_accuracy, 3)
            ),
            "num_unverified_entities": len(self.unverified_entities),
            "unverified_entities": self.unverified_entities,
        }


def score_faithfulness(
    log: ParsedLog, narrative: str, k: int = 3
) -> FaithfulnessReport:
    """Score one narrative against one parsed CLARUS log."""
    if not narrative or not narrative.strip():
        raise ValueError("empty narrative")

    vocab = log.node_vocabulary()
    initial = log.states[0] if log.states else None
    top_nodes = initial.top_nodes(k) if initial else []

    mentioned_known = sorted(n for n in vocab if _mentions(n, narrative))
    mentioned_top = [n for n in top_nodes if n in mentioned_known]

    # Fabrication signal: gene-like tokens that are neither known nodes nor acronyms.
    # Exclude tokens that prefix a real gene (e.g. "MGAT" -> the MGAT family), which
    # are references to the gene family, not invented genes.
    candidates = set(_CANDIDATE.findall(narrative))
    unverified = sorted(
        c
        for c in candidates - vocab - _STOPWORDS
        if not any(gene.startswith(c) for gene in vocab)
    )

    sentences = _sentences(narrative)
    edits: list[EditFaithfulness] = []
    for change in log.prediction_changes():
        action = change.action
        if action[0] == "node_deleted":
            entities = [action[1]]
        else:  # edge_deleted
            entities = list(action[1:])

        relevant = [
            s for s in sentences if all(_mentions(e, s) for e in entities)
        ]
        mentioned = bool(relevant)
        claims_flip = (
            any(_FLIP_WORDS.search(s) for s in relevant) if mentioned else None
        )
        consistent = (
            None if claims_flip is None else (claims_flip == change.flipped)
        )
        edits.append(
            EditFaithfulness(
                action=action,
                mentioned=mentioned,
                actually_flipped=change.flipped,
                narrative_claims_flip=claims_flip,
                direction_consistent=consistent,
            )
        )

    return FaithfulnessReport(
        top_k=k,
        top_nodes=top_nodes,
        mentioned_top_nodes=mentioned_top,
        mentioned_known_nodes=mentioned_known,
        unverified_entities=unverified,
        edits=edits,
    )
