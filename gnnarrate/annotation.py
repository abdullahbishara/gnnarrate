"""Expert-validation harness for the gene-disease grounding.

The grounding scorer labels each gene-disease claim supported/unsupported using
Open Targets. That is a *proxy* for correctness -- a knowledge base is incomplete,
so "unsupported" is not the same as "false". To validate the proxy, this module
exports the individual claims to a CSV for a domain expert to label by hand, then
computes how well the automatic labels agree with the expert's (accuracy + Cohen's
kappa). This is the ~50-100 claim check that turns the numbers from suggestive into
validated.
"""

from __future__ import annotations

import csv
import random

from ._textutil import has_term, mentions, sentences
from .clarus_log import ParsedLog
from .grounding import DiseaseAssociations

FIELDS = ["item_id", "gene", "sentence", "auto_label", "ot_score", "expert_label"]


def extract_claims(log: ParsedLog, narrative: str, associations: DiseaseAssociations,
                   extra_terms=None) -> list[dict]:
    """Every gene-disease claim in the narrative, with the auto label and OT score."""
    vocab = log.node_vocabulary()
    terms = list(associations.terms) + list(extra_terms or [])
    claims = []
    for sentence in sentences(narrative):
        if not (terms and has_term(sentence, terms)):
            continue
        for gene in sorted(vocab):
            if mentions(gene, sentence):
                claims.append({
                    "gene": gene,
                    "sentence": sentence.strip(),
                    "auto_label": "supported" if associations.is_associated(gene) else "unsupported",
                    "ot_score": round(associations.scores.get(gene.upper(), 0.0), 4),
                })
    return claims


def export_claims_for_annotation(records, associations, path, sample=None, seed=0) -> int:
    """Write all (optionally a random `sample` of) claims to `path` for labeling.

    Returns the number of rows written. The expert fills the empty `expert_label`
    column with "supported" or "unsupported".
    """
    rows = []
    for rec in records:
        for claim in extract_claims(rec.log, rec.narrative, associations):
            rows.append({"item_id": rec.item_id, **claim, "expert_label": ""})

    if sample and len(rows) > sample:
        rng = random.Random(seed)
        rng.shuffle(rows)
        rows = rows[:sample]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _cohen_kappa(auto: list[str], expert: list[str]) -> float | None:
    """Cohen's kappa for two label sequences. None if undefined (single class)."""
    n = len(auto)
    if n == 0:
        return None
    po = sum(a == e for a, e in zip(auto, expert)) / n
    labels = set(auto) | set(expert)
    pe = sum(
        (auto.count(k) / n) * (expert.count(k) / n) for k in labels
    )
    if pe == 1:
        return None  # both sequences a single identical class -> kappa undefined
    return (po - pe) / (1 - pe)


def compute_agreement(rows) -> dict:
    """Accuracy and Cohen's kappa between auto_label and a filled expert_label.

    `rows` is an iterable of dicts (e.g. from csv.DictReader). Rows with a blank
    expert_label are ignored.
    """
    labeled = [r for r in rows if str(r.get("expert_label", "")).strip()]
    if not labeled:
        return {"n_labeled": 0, "accuracy": None, "cohen_kappa": None}

    auto = [r["auto_label"].strip() for r in labeled]
    expert = [r["expert_label"].strip() for r in labeled]
    accuracy = sum(a == e for a, e in zip(auto, expert)) / len(labeled)
    return {
        "n_labeled": len(labeled),
        "accuracy": accuracy,
        "cohen_kappa": _cohen_kappa(auto, expert),
    }
