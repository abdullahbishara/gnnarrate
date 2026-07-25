"""Parser for CLARUS explanation logs.

A CLARUS log is a sequence of graph *states* separated by lines of ``#``. The
first state is the patient's original graph; each later state is the result of a
counterfactual edit (a node or edge deletion) followed by retraining. Every state
reports the model's prediction, its confidence, per-node and per-edge relevance
scores, and confusion-matrix counts.

This module turns that free text into structured objects so the faithfulness
scorer can check an LLM narrative against the ground truth the log actually
contains -- which nodes ranked highest, whether a deletion truly flipped the
prediction, and which direction the confidence moved.

Assumption: node names contain no ``-`` (edges are written ``A-B``). True for the
KIRC/Synthetic datasets; revisit if a dataset uses hyphenated identifiers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Delimiter line between states: a run of '#'.
_DELIM = re.compile(r"^#{3,}\s*$")

_DATASET = re.compile(r"Dataset selected:\s*(.+)")
_CONFUSION = re.compile(r"TN:\s*(\d+),\s*FP:\s*(\d+),\s*FN:\s*(\d+),\s*TP:\s*(\d+)")
_SENS_SPEC = re.compile(r"Sensitivity:\s*(-?[\d.]+)%?,\s*Specificity:\s*(-?[\d.]+)%?")
_PATIENT = re.compile(
    r"True label\s*=\s*(-?\d+).*?Predicted label\s*=\s*(-?\d+)"
    r".*?confidence\s*=\s*(-?[\d.]+)"
)
_NODE = re.compile(r"^Node\s+(\S+):\s*(-?[\d.]+)\s*$", re.MULTILINE)
_EDGE = re.compile(
    r"^(\S+)-(\S+):\s*IG=(-?[\d.]+),\s*Saliency=(-?[\d.]+)\s*$", re.MULTILINE
)
_NODE_DELETED = re.compile(r"Node deleted:\s*(\S+)")
_EDGE_DELETED = re.compile(r"Edge deleted between nodes:\s*(\S+)\s+and\s+(\S+)")


@dataclass
class GraphState:
    """One graph in the log: the original, or the result of one counterfactual edit."""

    step_index: int
    action: tuple | None  # None, ("node_deleted", name), or ("edge_deleted", a, b)
    true_label: int | None
    predicted_label: int | None
    confidence: float | None
    node_relevance: dict[str, float] = field(default_factory=dict)
    edge_relevance: dict[tuple[str, str], dict[str, float]] = field(default_factory=dict)
    confusion: dict[str, int] = field(default_factory=dict)
    sensitivity: float | None = None
    specificity: float | None = None

    def top_nodes(self, k: int = 3) -> list[str]:
        """The k highest-relevance node names, most important first."""
        ranked = sorted(self.node_relevance.items(), key=lambda kv: kv[1], reverse=True)
        return [name for name, _ in ranked[:k]]

    def metric_inconsistencies(self, tol: float = 1.0) -> list[str]:
        """Report serialised metrics that disagree with the confusion matrix.

        Every log in the released corpus carries ``Sensitivity: 0.75%`` where the
        matrix gives 75%: the fraction was formatted with a percent sign, a
        hundredfold error in the text the narrator is asked to explain. Nothing
        caught it because the faithfulness audit never reads these numbers.

        Returns one message per disagreeing field, empty when consistent.
        """
        problems: list[str] = []
        c = self.confusion
        pairs = (("sensitivity", self.sensitivity, "TP", "FN"),
                 ("specificity", self.specificity, "TN", "FP"))
        for name, stated, hit_key, miss_key in pairs:
            if stated is None or hit_key not in c or miss_key not in c:
                continue
            denom = c[hit_key] + c[miss_key]
            if denom == 0:
                continue
            expected = 100.0 * c[hit_key] / denom
            if abs(stated - expected) > tol:
                extra = ""
                if abs(stated * 100.0 - expected) <= tol:
                    extra = " (looks like a fraction written with a % sign)"
                problems.append(
                    f"{name} serialised as {stated}% but the confusion matrix "
                    f"gives {expected:.1f}%{extra}")
        return problems


@dataclass
class PredictionChange:
    """What one counterfactual edit did to the prediction."""

    action: tuple
    prev_predicted: int | None
    new_predicted: int | None
    prev_confidence: float | None
    new_confidence: float | None

    @property
    def flipped(self) -> bool:
        return (
            self.prev_predicted is not None
            and self.new_predicted is not None
            and self.prev_predicted != self.new_predicted
        )

    @property
    def confidence_delta(self) -> float | None:
        if self.prev_confidence is None or self.new_confidence is None:
            return None
        return self.new_confidence - self.prev_confidence


@dataclass
class ParsedLog:
    dataset: str | None
    states: list[GraphState]

    def node_vocabulary(self) -> set[str]:
        """Every node name that appears anywhere in the log."""
        vocab: set[str] = set()
        for st in self.states:
            vocab.update(st.node_relevance)
            for a, b in st.edge_relevance:
                vocab.update((a, b))
            if st.action and st.action[0] == "node_deleted":
                vocab.add(st.action[1])
            elif st.action and st.action[0] == "edge_deleted":
                vocab.update(st.action[1:])
        return vocab

    def prediction_changes(self) -> list[PredictionChange]:
        """One entry per edit, pairing each state with the one before it."""
        changes = []
        for prev, cur in zip(self.states, self.states[1:]):
            if cur.action is None:
                continue
            changes.append(
                PredictionChange(
                    action=cur.action,
                    prev_predicted=prev.predicted_label,
                    new_predicted=cur.predicted_label,
                    prev_confidence=prev.confidence,
                    new_confidence=cur.confidence,
                )
            )
        return changes


def _first(pattern: re.Pattern, text: str):
    m = pattern.search(text)
    return m if m else None


def _parse_block(block: str, index: int) -> GraphState:
    action = None
    if (m := _NODE_DELETED.search(block)) is not None:
        action = ("node_deleted", m.group(1))
    elif (m := _EDGE_DELETED.search(block)) is not None:
        action = ("edge_deleted", m.group(1), m.group(2))

    true_label = predicted = None
    confidence = None
    if (m := _first(_PATIENT, block)) is not None:
        true_label, predicted = int(m.group(1)), int(m.group(2))
        confidence = float(m.group(3))

    confusion = {}
    if (m := _first(_CONFUSION, block)) is not None:
        confusion = {
            "TN": int(m.group(1)), "FP": int(m.group(2)),
            "FN": int(m.group(3)), "TP": int(m.group(4)),
        }

    sensitivity = specificity = None
    if (m := _first(_SENS_SPEC, block)) is not None:
        sensitivity, specificity = float(m.group(1)), float(m.group(2))

    node_relevance = {name: float(score) for name, score in _NODE.findall(block)}
    edge_relevance = {
        (a, b): {"IG": float(ig), "Saliency": float(sal)}
        for a, b, ig, sal in _EDGE.findall(block)
    }

    return GraphState(
        step_index=index,
        action=action,
        true_label=true_label,
        predicted_label=predicted,
        confidence=confidence,
        node_relevance=node_relevance,
        edge_relevance=edge_relevance,
        confusion=confusion,
        sensitivity=sensitivity,
        specificity=specificity,
    )


def parse_clarus_log(text: str) -> ParsedLog:
    """Parse a CLARUS log into an ordered list of graph states."""
    if not text or not text.strip():
        raise ValueError("empty CLARUS log")

    blocks, current = [], []
    for line in text.splitlines():
        if _DELIM.match(line):
            if current:
                blocks.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current))

    dataset = None
    if (m := _first(_DATASET, text)) is not None:
        dataset = m.group(1).strip()

    states = [_parse_block(b, i) for i, b in enumerate(blocks) if b.strip()]
    return ParsedLog(dataset=dataset, states=states)
