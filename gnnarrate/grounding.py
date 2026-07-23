"""Gene-disease grounding: are the narrative's disease claims supported?

Tier 1 (faithfulness.py) checks a narrative against the attribution log. This tier
checks its *biomedical* claims: when the narrative asserts that a gene is linked to
the patient's disease, is that association supported by a knowledge base?

For a CLARUS dataset the disease is fixed (e.g. KIRC = kidney renal clear cell
carcinoma), so grounding a gene-disease claim reduces to a lookup: is this gene
associated with the disease in the knowledge base? We use Open Targets association
scores (see opentargets.py), but any gene->score mapping works, so the scorer
itself stays offline and testable.

Honesty notes, carried into the paper:
- Claim extraction is a documented lexical heuristic -- a gene co-occurring with a
  disease term in a sentence -- to be corroborated by the expert validation.
- Knowledge bases are incomplete. "Not associated in the KB" means UNSUPPORTED,
  not proven false. Unsupported claims are hallucination *candidates*, never a
  final verdict.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field

from ._textutil import has_term, mentions, sentences
from .clarus_log import ParsedLog


@dataclass
class DiseaseAssociations:
    """Gene -> association score for a single disease, plus its name cue terms."""

    disease: str
    disease_id: str | None
    scores: dict[str, float]
    threshold: float = 0.0
    terms: list[str] = field(default_factory=list)

    def is_associated(self, gene: str) -> bool:
        return self.scores.get(gene.upper(), 0.0) > self.threshold

    @classmethod
    def from_dict(cls, mapping, disease, disease_id=None, threshold=0.0, terms=None):
        return cls(
            disease=disease,
            disease_id=disease_id,
            scores={k.upper(): float(v) for k, v in mapping.items()},
            threshold=threshold,
            terms=list(terms or []),
        )

    def to_tsv(self, path) -> None:
        """Cache the association scores to a TSV so they can be reloaded offline."""
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow(["gene", "score"])
            for gene, score in sorted(self.scores.items()):
                w.writerow([gene, score])

    @classmethod
    def from_tsv(cls, path, disease, disease_id=None, threshold=0.0, terms=None):
        scores = {}
        with open(path, newline="", encoding="utf-8") as f:
            r = csv.reader(f, delimiter="\t")
            next(r, None)  # header
            for row in r:
                if len(row) >= 2:
                    scores[row[0].upper()] = float(row[1])
        return cls(disease, disease_id, scores, threshold, list(terms or []))


@dataclass
class GroundingReport:
    disease: str
    claimed_genes: list[str]   # genes the narrative links to the disease
    supported: list[str]       # claimed AND associated in the KB
    unsupported: list[str]     # claimed but NOT associated -> hallucination candidates
    associations_available: bool

    @property
    def grounding_precision(self) -> float | None:
        """Of the disease links the narrative asserts, the fraction the KB backs."""
        if not self.claimed_genes:
            return None
        return len(self.supported) / len(self.claimed_genes)

    def summary(self) -> dict:
        return {
            "disease": self.disease,
            "num_claimed": len(self.claimed_genes),
            "num_supported": len(self.supported),
            "num_unsupported": len(self.unsupported),
            "grounding_precision": (
                None if self.grounding_precision is None
                else round(self.grounding_precision, 3)
            ),
            "hallucination_candidates": self.unsupported,
        }


def score_grounding(
    log: ParsedLog,
    narrative: str,
    associations: DiseaseAssociations,
    extra_disease_terms=None,
) -> GroundingReport:
    """Grade the narrative's gene-disease claims against `associations`.

    A gene is treated as *claimed* to relate to the disease when it appears in a
    sentence that also names the disease (heuristic). Each claimed gene is then
    looked up in the knowledge base.
    """
    if not narrative or not narrative.strip():
        raise ValueError("empty narrative")

    vocab = log.node_vocabulary()
    terms = list(associations.terms) + list(extra_disease_terms or [])

    claimed = set()
    for sentence in sentences(narrative):
        if terms and has_term(sentence, terms):
            for gene in vocab:
                if mentions(gene, sentence):
                    claimed.add(gene)

    claimed_genes = sorted(claimed)
    supported = [g for g in claimed_genes if associations.is_associated(g)]
    unsupported = [g for g in claimed_genes if not associations.is_associated(g)]

    return GroundingReport(
        disease=associations.disease,
        claimed_genes=claimed_genes,
        supported=supported,
        unsupported=unsupported,
        associations_available=bool(associations.scores),
    )
