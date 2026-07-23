"""Fetch gene-disease association scores from the Open Targets Platform.

Network access required -- this module is NOT used by the test suite. Fetch once,
cache with DiseaseAssociations.to_tsv, then load offline with from_tsv.

    from gnnarrate.opentargets import search_disease, fetch_open_targets_associations
    search_disease("kidney renal clear cell carcinoma")   # -> [(efo_id, name), ...]
    assoc = fetch_open_targets_associations("EFO_0000349")
    assoc.to_tsv("data/kirc_associations.tsv")
"""

from __future__ import annotations

import json
import re
import urllib.request

from .grounding import DiseaseAssociations

_ENDPOINT = "https://api.platform.opentargets.org/api/v4/graphql"

_SEARCH_QUERY = """
query Search($q: String!) {
  search(queryString: $q, entityNames: ["disease"], page: {index: 0, size: 5}) {
    hits { id name }
  }
}
"""

_ASSOC_QUERY = """
query Assoc($efoId: String!, $index: Int!, $size: Int!) {
  disease(efoId: $efoId) {
    id
    name
    associatedTargets(page: {index: $index, size: $size}) {
      count
      rows { target { approvedSymbol } score }
    }
  }
}
"""


def _post(query: str, variables: dict, timeout: int = 30) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        _ENDPOINT, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise RuntimeError(f"Open Targets error: {payload['errors']}")
    return payload["data"]


def search_disease(name: str) -> list[tuple[str, str]]:
    """Return up to five (efo_id, name) candidates for a disease name."""
    data = _post(_SEARCH_QUERY, {"q": name})
    return [(h["id"], h["name"]) for h in data["search"]["hits"]]


def _disease_terms(name: str) -> list[str]:
    words = [w for w in re.split(r"\W+", name.lower()) if len(w) > 3]
    return sorted(set(words) | {"cancer", "tumor", "tumour", "carcinoma", "disease"})


def fetch_open_targets_associations(
    efo_id: str, page_size: int = 500, max_targets: int | None = None, threshold: float = 0.0
) -> DiseaseAssociations:
    """Fetch every target associated with `efo_id`, as gene symbol -> score."""
    scores: dict[str, float] = {}
    name = efo_id
    index = 0
    while True:
        data = _post(_ASSOC_QUERY, {"efoId": efo_id, "index": index, "size": page_size})
        disease = data["disease"]
        if disease is None:
            raise ValueError(f"No disease found for EFO id {efo_id!r}")
        name = disease["name"]
        block = disease["associatedTargets"]
        for row in block["rows"]:
            symbol = row["target"]["approvedSymbol"]
            if symbol:
                scores[symbol.upper()] = float(row["score"])
        index += 1
        if not block["rows"] or index * page_size >= block["count"]:
            break
        if max_targets and len(scores) >= max_targets:
            break

    return DiseaseAssociations(
        disease=name,
        disease_id=efo_id,
        scores=scores,
        threshold=threshold,
        terms=_disease_terms(name),
    )
