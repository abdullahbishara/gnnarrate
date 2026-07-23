"""Mitigation loop: constrain a narrative to knowledge-base-supported claims.

The neuro-symbolic step. Grounding (Tier 2) flags gene-disease claims the knowledge
base does not support; this module feeds those back to revise the narrative, then
re-scores it to measure how much the hallucination count dropped -- the before/after
delta that is the paper's headline result.

The reviser is injected: tests pass a deterministic stub, production passes an
LLM-backed reviser (see `llm_reviser`). The measurement itself is pure and offline.
"""

from __future__ import annotations

import re as _re
from dataclasses import dataclass

from ._textutil import has_term, mentions, sentences
from .clarus_log import ParsedLog
from .grounding import DiseaseAssociations, GroundingReport, score_grounding


@dataclass
class MitigationResult:
    before: GroundingReport
    after: GroundingReport
    revised_narrative: str

    @property
    def hallucinations_before(self) -> int:
        return len(self.before.unsupported)

    @property
    def hallucinations_after(self) -> int:
        return len(self.after.unsupported)

    @property
    def reduction(self) -> int:
        """Net drop in unsupported claims (negative if revision made it worse)."""
        return self.hallucinations_before - self.hallucinations_after

    @property
    def reduction_rate(self) -> float | None:
        """Fraction of hallucinations removed; None when there were none to remove."""
        if self.hallucinations_before == 0:
            return None
        return self.reduction / self.hallucinations_before

    def summary(self) -> dict:
        return {
            "disease": self.before.disease,
            "hallucinations_before": self.hallucinations_before,
            "hallucinations_after": self.hallucinations_after,
            "reduction": self.reduction,
            "reduction_rate": (
                None if self.reduction_rate is None
                else round(self.reduction_rate, 3)
            ),
        }


def measure_mitigation(
    before: GroundingReport, after: GroundingReport, revised_narrative: str = ""
) -> MitigationResult:
    return MitigationResult(before=before, after=after, revised_narrative=revised_narrative)


def build_revision_prompt(
    narrative: str, unsupported_genes, disease: str
) -> str:
    """Prompt asking the model to drop/qualify unsupported gene-disease claims."""
    genes = ", ".join(unsupported_genes)
    return f"""You previously wrote this explanation of a graph neural network's prediction:

\"\"\"
{narrative.strip()}
\"\"\"

A knowledge-base check found NO evidence that the following genes are associated
with {disease}: {genes}.

Revise the explanation so it no longer asserts that these genes are linked to
{disease}. You may remove those claims or restate them as unverified. Keep every
other statement -- especially every description of the model's behavior --
unchanged. Return only the revised explanation.
"""


def mitigate(
    log: ParsedLog,
    narrative: str,
    associations: DiseaseAssociations,
    revise_fn,
) -> tuple[str, MitigationResult]:
    """Ground the narrative; if it has unsupported claims, revise and re-score.

    `revise_fn(narrative, unsupported_genes, disease) -> str`. Returns the (possibly
    unchanged) narrative and the before/after measurement.
    """
    before = score_grounding(log, narrative, associations)
    if not before.unsupported:
        return narrative, measure_mitigation(before, before, narrative)

    revised = revise_fn(narrative, before.unsupported, associations.disease)
    if not revised or not revised.strip():
        # Revision removed everything -> no claims remain, so no hallucinations.
        after = GroundingReport(
            disease=associations.disease,
            claimed_genes=[], supported=[], unsupported=[],
            associations_available=bool(associations.scores),
        )
    else:
        after = score_grounding(log, revised, associations)
    return revised, measure_mitigation(before, after, revised)


def llm_reviser(provider: str = "anthropic", model: str | None = None, temperature: float | None = None):
    """Build an LLM-backed reviser to pass into `mitigate` (needs an API key).

    Neural self-revision: asks the model to drop its own unsupported claims. In
    practice the model tends to *hedge* rather than remove, so the flagged claim
    (gene co-occurring with a disease term) often survives -- contrast with
    `symbolic_reviser`.
    """

    def _revise(narrative, unsupported_genes, disease):
        from .llm import explain_model_prediction

        prompt = build_revision_prompt(narrative, unsupported_genes, disease)
        return explain_model_prediction(
            prompt, provider=provider, model=model, temperature=temperature
        )

    return _revise


def symbolic_reviser(disease_terms):
    """Deterministically delete sentences that assert an unsupported gene-disease link.

    The symbolic guardrail. It removes exactly the sentences the grounding scorer
    flags -- an unsupported gene co-occurring with a disease term -- and keeps every
    other sentence, including supported claims and structural (attribution) mentions.
    Needs no API key, and by construction leaves zero flagged claims behind.

    Cost: when a sentence bundles supported and unsupported genes, the whole sentence
    goes, taking the supported claims with it. `claim_level_reviser` mitigates that.
    """
    terms = list(disease_terms)

    def _revise(narrative, unsupported_genes, disease):
        kept = [
            s
            for s in sentences(narrative)
            if not (has_term(s, terms) and any(mentions(g, s) for g in unsupported_genes))
        ]
        return " ".join(kept)

    return _revise


def _strip_gene_from_list(sentence: str, gene: str) -> str | None:
    """Remove `gene` from a comma/and list in `sentence`; None if not cleanly removable."""
    g = _re.escape(gene)
    for pattern in (rf",\s*{g}\b", rf"\b{g}\s*,", rf"\s+and\s+{g}\b", rf"\b{g}\s+and\s+"):
        new = _re.sub(pattern, "", sentence, count=1, flags=_re.IGNORECASE)
        if new != sentence:
            return new
    return None


def claim_level_reviser(disease_terms):
    """Remove only the unsupported gene from a flagged sentence, keeping supported ones.

    When an unsupported gene sits in a list ("A, B, and C are implicated..."), strip
    just that gene rather than deleting the whole sentence -- preserving the supported
    claims bundled alongside it. Falls back to dropping the sentence when the gene
    can't be cleanly excised.
    """
    terms = list(disease_terms)

    def _revise(narrative, unsupported_genes, disease):
        out = []
        for s in sentences(narrative):
            if not (has_term(s, terms) and any(mentions(g, s) for g in unsupported_genes)):
                out.append(s)
                continue
            revised, ok = s, True
            for g in unsupported_genes:
                if mentions(g, revised):
                    stripped = _strip_gene_from_list(revised, g)
                    if stripped is None:
                        ok = False
                        break
                    revised = stripped
            # Keep only if every unsupported gene was excised; else drop the sentence.
            if ok and not any(mentions(g, revised) for g in unsupported_genes):
                out.append(revised)
        return " ".join(out)

    return _revise
