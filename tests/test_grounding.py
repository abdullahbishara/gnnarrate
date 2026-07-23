import pathlib

import pytest

from gnnarrate.clarus_log import parse_clarus_log
from gnnarrate.grounding import DiseaseAssociations, score_grounding

SAMPLE = (
    pathlib.Path(__file__).parent.parent / "examples" / "sample_clarus_log.txt"
).read_text(encoding="utf-8")

# SYNTHETIC test fixture -- scores are arbitrary, chosen to exercise the logic,
# NOT real Open Targets values. MGAT3 "associated", the others not.
FIXTURE = DiseaseAssociations.from_dict(
    {"MGAT3": 0.42, "MGAT4B": 0.0, "MGAT5": 0.0, "MGAT5B": 0.0},
    disease="kidney renal clear cell carcinoma",
    disease_id="EFO_TEST",
    terms=["kidney", "renal", "carcinoma", "cancer", "tumor"],
)


@pytest.fixture
def log():
    return parse_clarus_log(SAMPLE)


def test_supported_disease_claim(log):
    r = score_grounding(log, "MGAT3 is strongly implicated in kidney cancer.", FIXTURE)
    assert r.claimed_genes == ["MGAT3"]
    assert r.supported == ["MGAT3"]
    assert r.unsupported == []
    assert r.grounding_precision == 1.0


def test_unsupported_claim_is_a_hallucination_candidate(log):
    r = score_grounding(log, "MGAT5 is a well-known driver of kidney cancer.", FIXTURE)
    assert r.claimed_genes == ["MGAT5"]
    assert r.unsupported == ["MGAT5"]          # not associated in the KB
    assert r.grounding_precision == 0.0
    assert r.summary()["hallucination_candidates"] == ["MGAT5"]


def test_mixed_claims_precision(log):
    r = score_grounding(
        log, "Both MGAT3 and MGAT4B are linked to renal carcinoma.", FIXTURE
    )
    assert r.claimed_genes == ["MGAT3", "MGAT4B"]
    assert r.supported == ["MGAT3"]
    assert r.unsupported == ["MGAT4B"]
    assert r.grounding_precision == 0.5


def test_non_disease_sentences_make_no_claims(log):
    # Mentions a gene, but says nothing about the disease -> not a grounding claim.
    r = score_grounding(log, "MGAT3 had the highest relevance score in the graph.", FIXTURE)
    assert r.claimed_genes == []
    assert r.grounding_precision is None


def test_empty_narrative_rejected(log):
    with pytest.raises(ValueError, match="empty"):
        score_grounding(log, "   ", FIXTURE)


def test_tsv_roundtrip(tmp_path, log):
    path = tmp_path / "assoc.tsv"
    FIXTURE.to_tsv(path)
    reloaded = DiseaseAssociations.from_tsv(
        path, disease=FIXTURE.disease, terms=FIXTURE.terms
    )
    assert reloaded.is_associated("MGAT3")
    assert not reloaded.is_associated("MGAT5")
