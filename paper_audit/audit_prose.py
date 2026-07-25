"""Consistency checks the numeric audits cannot see.

Numbers can be compared to a CSV. Prose cannot, so these look for the specific
ways a manuscript drifts out of joint while it is being revised: a cross-reference
that points at the wrong section, a term that acquires a second spelling, a
promise in the contributions with no matching result, a caption describing a
column the table no longer has, and grammar left behind by search-and-replace.
"""

from __future__ import annotations

import re
import sys

from _paths import full_text, require_tex

require_tex()
tex = full_text()
body = re.sub(r"(?<!\\)%.*", "", tex)
problems: list[str] = []


def flag(msg: str) -> None:
    problems.append(msg)


# --- 1. cross-references point at the section they claim ------------------
labels: dict[str, str] = {}
current = None
for m in re.finditer(r"\\(?:sub)?section\*?\{([^}]*)\}|\\label\{(sec:[^}]*)\}", body):
    if m.group(1):
        current = m.group(1)
    elif m.group(2) and current:
        labels[m.group(2)] = current

# "Section~\ref{x} <verb>" phrasings that name a topic; check the topic words
# plausibly appear in that section's title.
for m in re.finditer(r"Section~\\ref\{(sec:[^}]+)\}", body):
    key = m.group(1)
    if key not in labels:
        flag(f"cross-reference to undefined section label: {key}")

# A labelled float or section nobody points at is usually a reference that was
# lost during editing, not a deliberate choice.
all_labels = set(re.findall(r"\\label\{([^}]*)\}", body))
all_refs: set[str] = set()
for g in re.findall(r"\\(?:eq|c|C)?ref\{([^}]*)\}", body):
    all_refs.update(x.strip() for x in g.split(","))
# Supplementary tables are cited as "Table S1" in prose, not by \ref, because
# they live in a separate document. Treat them as referenced when the main text
# actually mentions their S-number.
from _paths import SUPP as _SUPP
supp_labels: set[str] = set()
if _SUPP.exists():
    supp_src = _SUPP.read_text(encoding="utf-8")
    supp_labels = set(re.findall(r"\\label\{([^}]*)\}", supp_src))
    n_cited = len(re.findall(r"Table~S\d", body))
    if n_cited < len(supp_labels):
        flag(f"{len(supp_labels)} supplementary tables but only {n_cited} "
             f"'Table~S<n>' citations in the main text")
for orphan in sorted(all_labels - all_refs - supp_labels):
    flag(f"label defined but never referenced: {orphan}")

# --- 1b. spelled-out counts agree with the data ---------------------------
# The manuscript said "nine configurations" in four places and "ten" in five,
# describing the same table, after a tenth configuration was added late. A
# spelled-out count is invisible to the numeric audit, so check it here.
WORD = {"seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
try:
    import csv as _csv

    from _paths import RESULTS as _RES
    n_configs = len(list(_csv.DictReader(
        open(_RES / "per_model.csv", newline="", encoding="utf-8"))))
except Exception:                                   # data not present; skip
    n_configs = None

if n_configs is not None:
    for m in re.finditer(r"\b(" + "|".join(WORD) + r")\b[ \n]+"
                         r"(?:LLM |model |independent )?configurations", body, re.I):
        got = WORD[m.group(1).lower()]
        if got != n_configs:
            ctx = re.sub(r"\s+", " ", body[max(0, m.start() - 60):m.end() + 40]).strip()
            flag(f"count word says {got} configurations, data has {n_configs}: ...{ctx}...")

# --- 1c. the configuration tables list every configuration ----------------
# Table I listed nine rows while the text beside it said ten, because a model
# added late was never appended. Count the body rows of each table that
# enumerates configurations and compare with the data.
if n_configs is not None:
    for label in ("tab:models", "tab:crossmodel"):
        m = re.search(rf"\\label\{{{label}\}}(.*?)\\end\{{tabular\}}", body, re.S)
        if not m:
            continue
        # Splitting at the first \midrule already drops the header, so any
        # remaining fragment holding a column separator is a body row. Do not
        # filter on \textbf: data rows use it to bold the best value per column.
        after_head = m.group(1).split(r"\midrule", 1)[-1]
        rows = [r for r in after_head.split(r"\\") if "&" in r and r.strip()]
        if len(rows) != n_configs:
            flag(f"{label} lists {len(rows)} configuration rows, data has {n_configs}")

# --- 2. terminology is spelled one way ------------------------------------
VARIANTS = [
    ("neuro-symbolic", "neurosymbolic"),
    ("knowledge base", "knowledgebase"),
    ("counterfactual", "counter-factual"),
    ("multimodal", "multi-modal"),
    ("gene--disease", "gene-disease"),
]
for canonical, variant in VARIANTS:
    if re.search(rf"\b{re.escape(variant)}\b", body, re.I):
        n = len(re.findall(rf"\b{re.escape(variant)}\b", body, re.I))
        # gene-disease appears legitimately inside figure labels and axis text
        if variant == "gene-disease" and n <= 3:
            continue
        flag(f"terminology: '{variant}' used {n}x alongside '{canonical}'")

# --- 3. every contribution has a matching result --------------------------
contrib = re.search(r"\\subsection\{Contributions\}(.*?)\\end\{enumerate\}", body, re.S)
if contrib:
    items = re.findall(r"\\item \\textbf\{([^}]*)\}", contrib.group(1))
    results = body.split(r"\section{Results}", 1)[-1]
    KEY = {
        "separation of faithfulness": ["faithful", "grounded"],
        "automatic neuro-symbolic audit": ["verifier", "grounding"],
        "benchmark over a clinical cohort": ["Table~\\ref{tab:crossmodel}", "127"],
        "causal account": ["ablation"],
        "attribution source": ["architecture"],
        "evaluation of mitigation": ["mitigation", "filtering"],
    }
    for item in items:
        hit = next((v for k, v in KEY.items() if k.lower() in item.lower()), None)
        if hit and not any(h in results for h in hit):
            flag(f"contribution with no matching result: {item[:50]}")

# --- 4. table captions match the columns actually present -----------------
for m in re.finditer(r"\\caption\{(.*?)\}\s*\\label\{(tab:[^}]+)\}(.*?)\\end\{tabular\}",
                     body, re.S):
    caption, label, tbl = m.group(1), m.group(2), m.group(3)
    n_cols = len(re.findall(r"&", tbl.split(r"\\")[0])) + 1 if r"\\" in tbl else 0
    cap_n = re.search(r"\$n = (\d+)\$|\(n = (\d+)\)", caption)
    if cap_n:
        stated = int(cap_n.group(1) or cap_n.group(2))
        rows_n = re.findall(r"&\s*(\d{2,3})\s*&", tbl)
        if rows_n and all(int(v) != stated for v in rows_n):
            flag(f"{label}: caption says n={stated}, rows show {sorted(set(rows_n))}")

# --- 5. leftovers from search-and-replace ---------------------------------
GRAMMAR = [
    (r"\b(\w+)\s+\1\b", "doubled word"),
    (r"architectures\s+configurations", "dangling word after edit"),
    (r"\ba\s+[aeiou]\w+\b(?<!\ba unique)(?<!\ba user)", None),   # weak, skip reporting
    (r",\s*,", "double comma"),
    (r"\s+\.", "space before full stop"),
    (r"\(\s*\)", "empty parentheses"),
]
for pat, name in GRAMMAR:
    if name is None:
        continue
    for m in re.finditer(pat, body):
        ctx = body[max(0, m.start() - 40):m.end() + 40].replace("\n", " ")
        flag(f"{name}: ...{ctx.strip()}...")

# --- 6. abstract claims appear in the body --------------------------------
abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", body, re.S)
if abstract:
    for phrase, where in [("three GNN architectures", "architecture"),
                          ("prompt ablation", "ablation"),
                          ("symbolic filtering", "filtering")]:
        if phrase in abstract.group(1) and where not in body.split(
                r"\section{Results}", 1)[-1].lower():
            flag(f"abstract mentions '{phrase}' with no matching results content")

# --- report ---------------------------------------------------------------
print(f"prose consistency: {len(problems)} problem(s)\n")
for p in problems:
    print("  - " + p)
if not problems:
    print("  no cross-reference, terminology, caption or grammar problems found")
sys.exit(1 if problems else 0)
