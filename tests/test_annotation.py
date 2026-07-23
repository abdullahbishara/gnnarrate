import csv
import pathlib

from gnnarrate.annotation import (
    compute_agreement,
    export_claims_for_annotation,
    extract_claims,
)
from gnnarrate.benchmark import NarrativeRecord
from gnnarrate.clarus_log import parse_clarus_log
from gnnarrate.grounding import DiseaseAssociations

SAMPLE = (
    pathlib.Path(__file__).parent.parent / "examples" / "sample_clarus_log.txt"
).read_text(encoding="utf-8")

ASSOC = DiseaseAssociations.from_dict(
    {"MGAT3": 0.42, "MGAT4B": 0.0, "MGAT5": 0.0, "MGAT5B": 0.0},
    disease="kidney cancer",
    terms=["kidney", "cancer"],
)

NARRATIVE = (
    "MGAT3 is implicated in kidney cancer. MGAT5 causes kidney cancer. "
    "MGAT3 had the highest relevance score."
)


def test_extract_claims_labels_only_disease_sentences():
    log = parse_clarus_log(SAMPLE)
    claims = extract_claims(log, NARRATIVE, ASSOC)
    labels = {(c["gene"], c["auto_label"]) for c in claims}
    assert ("MGAT3", "supported") in labels       # associated in the KB
    assert ("MGAT5", "unsupported") in labels      # not associated
    # The "relevance score" sentence has no disease term -> not a claim.
    assert all("relevance" not in c["sentence"] for c in claims)


def test_export_writes_annotatable_csv(tmp_path):
    log = parse_clarus_log(SAMPLE)
    rec = NarrativeRecord("p0", log, NARRATIVE, model="opus")
    path = tmp_path / "claims.csv"
    n = export_claims_for_annotation([rec], ASSOC, path)
    assert n >= 2
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["expert_label"] == ""           # blank for the expert to fill
    assert {"gene", "auto_label", "sentence", "ot_score"} <= set(rows[0])


def test_agreement_accuracy_and_kappa():
    rows = [
        {"auto_label": "supported", "expert_label": "supported"},
        {"auto_label": "unsupported", "expert_label": "unsupported"},
        {"auto_label": "unsupported", "expert_label": "supported"},  # disagreement
        {"auto_label": "supported", "expert_label": ""},             # unlabeled -> ignored
    ]
    result = compute_agreement(rows)
    assert result["n_labeled"] == 3
    assert abs(result["accuracy"] - 2 / 3) < 1e-9
    assert result["cohen_kappa"] is not None


def test_agreement_with_no_labels():
    result = compute_agreement([{"auto_label": "supported", "expert_label": ""}])
    assert result["n_labeled"] == 0
    assert result["accuracy"] is None
