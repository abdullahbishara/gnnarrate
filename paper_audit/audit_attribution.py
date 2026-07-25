"""Check the manuscript credits upstream work correctly -- in both directions.

Two failures are possible and both happened. The manuscript can *under*-credit,
by using a dataset or component without citing its source: the KIRC benchmark
came from GNN-SubNet and was not cited anywhere. It can also *over*-credit, by
handing an upstream project work that is not theirs: the acknowledgement gave
CLARUS "the GNN architectures, attribution methods and counterfactual
machinery", when the platform's own ATTRIBUTION.md records the attention model,
the edge-weight operators, the model factory and the occlusion counterfactual
generator as original to this work. Over-crediting is the more expensive
mistake, because it signs away the contribution a result rests on.

ATTRIBUTION.md in the platform checkout is the ground truth for both. This check
is skipped when that checkout is not present.

    GNNARRATE_PLATFORM=/path/to/platform python paper_audit/audit_attribution.py
"""

from __future__ import annotations

import re
import sys

from _paths import PAPER, PLATFORM, require_tex

if PLATFORM is None:
    print("GNNARRATE_PLATFORM not set -- skipping attribution audit")
    raise SystemExit(0)

attrib = PLATFORM / "ATTRIBUTION.md"
if not attrib.exists():
    print(f"no ATTRIBUTION.md at {attrib} -- skipping")
    raise SystemExit(0)

md = attrib.read_text(encoding="utf-8")
tex = re.sub(r"(?<!\\)%.*", "", require_tex().read_text(encoding="utf-8"))
bib = (PAPER / "submission" / "references.bib").read_text(encoding="utf-8")
problems: list[str] = []

# --- 1. every upstream project is cited ------------------------------------
# Upstream sections are "### n. Name", each carrying a first author we can look
# for in the bibliography.
upstream = md.split("## Original contributions")[0]
for block in re.split(r"^### ", upstream, flags=re.M)[1:]:
    # Console encodings here are not always UTF-8; keep the label printable.
    name = block.split("\n", 1)[0].strip().encode("ascii", "replace").decode()
    authors = re.search(r"\*\*Authors:\*\*\s*(.+)", block)
    if not authors:
        continue
    surname = authors.group(1).split(",")[0].strip().split()[-1]
    in_bib = re.search(rf"author\s*=\s*\{{[^}}]*{re.escape(surname)}", bib, re.I)
    if not in_bib:
        problems.append(f"upstream '{name}': no bib entry with author {surname}")
        continue
    key = re.search(r"@\w+\{([^,]+),(?:(?!@)[\s\S])*?" + re.escape(surname), bib, re.I)
    if key and not re.search(rf"\\cite\{{[^}}]*\b{re.escape(key.group(1))}\b",
                             tex):
        problems.append(
            f"upstream '{name}' is in the bibliography ({key.group(1)}) "
            f"but never cited in the manuscript")

# --- 2. nothing original is handed to an upstream project ------------------
# Pull the component nouns this work claims, then look for them inside a
# sentence that also assigns credit upstream.
original = md.split("## Original contributions", 1)[-1]
CLAIMED = {
    "GAT": r"\bGAT\b|graph attention",
    "edge-weight operators": r"GINConvEW|GATConvEW|edge-weight (?:message-passing )?operator",
    "model factory": r"model factory",
    "counterfactual generator": r"counterfactual generator",
    "evaluation harness": r"evaluation harness|multi-architecture harness",
}
claimed_here = {k: v for k, v in CLAIMED.items()
                if re.search(v.split("|")[0], original, re.I)}

# Crediting a whole category is the failure that actually occurred: the
# acknowledgement gave away "the GNN architectures", which silently includes the
# attention model, rather than naming GCN and GIN. Umbrella nouns are therefore
# flagged in a credit sentence whenever this work claims something inside them.
UMBRELLA = {
    r"(?<!GCN and )(?<!GCN/)\bGNN architectures\b|\barchitectures are theirs\b":
        "names the architectures as a group, which includes the attention model",
    r"\bcounterfactual (?:infrastructure|machinery)\b":
        "names the counterfactual component as a whole, which includes the "
        "occlusion generator",
    r"\battribution methods\b(?![^.]*GNNExplainer)":
        "names the attribution methods as a group, which relies on the "
        "edge-weight operators added here",
}

CREDIT = re.compile(
    r"(are theirs|is theirs|derive from|derives from|taken from|inherited from|"
    r"follow the CLARUS|provided by CLARUS|from the CLARUS platform)", re.I)
for sentence in re.split(r"(?<=[.!?])\s+", tex):
    if not CREDIT.search(sentence):
        continue
    flat = re.sub(r"\s+", " ", sentence).strip()
    for label, pattern in claimed_here.items():
        if re.search(pattern, sentence, re.I):
            problems.append(
                f"'{label}' is an original contribution but appears in a sentence "
                f"crediting upstream: ...{flat[:150]}...")
    for pattern, why in UMBRELLA.items():
        if re.search(pattern, sentence, re.I):
            problems.append(f"over-broad credit -- {why}: ...{flat[:150]}...")

print(f"attribution: {len(problems)} problem(s)\n")
for p in problems:
    print("  - " + p)
if not problems:
    print("  every upstream project is cited, and no original contribution is "
          "credited upstream")
sys.exit(1 if problems else 0)
