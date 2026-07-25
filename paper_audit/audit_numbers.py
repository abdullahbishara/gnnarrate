"""Verify every quantitative claim in the manuscript against its source data.

Catches the failure mode that matters most: a number that was correct when written
and became stale when the experiment was rerun. Each check names the claim, the
value in the text, and the value recomputed from the released artefacts.
"""

from __future__ import annotations

import csv
import json
import pathlib
import re

from _paths import DATA, RESULTS as RES, full_text, require_tex
TEX = require_tex()



tex = re.sub(r"(?<!\\)%.*", "", full_text())
ok, bad = [], []


def check(label, claimed, actual, tol=0.0051):
    """Compare a claimed value in the text against a recomputed one."""
    if claimed is None:
        bad.append(f"{label}: NOT FOUND in text")
        return
    good = abs(claimed - actual) <= tol
    (ok if good else bad).append(
        f"{label}: text={claimed} data={actual}" + ("" if good else "   <-- MISMATCH"))


def find(pattern, cast=float):
    """First match, cast. Multi-group patterns hand the cast all groups."""
    m = re.search(pattern, tex)
    if not m:
        return None
    return cast(m.groups() if m.re.groups > 1 else m.group(1))


# ---------- source data ----------
per_model = {r["config"]: r for r in csv.DictReader(
    open(RES / "per_model.csv", newline="", encoding="utf-8"))}
hedge = json.loads((RES / "hedging.json").read_text(encoding="utf-8"))
census = json.loads((RES / "claim_census.json").read_text(encoding="utf-8"))
thresh = json.loads((RES / "threshold_sensitivity.json").read_text(encoding="utf-8"))
emphasis = {r["config"]: r for r in json.loads(
    (RES / "emphasis.json").read_text(encoding="utf-8"))}
repeat = json.loads((DATA / "repeatability" / "repeatability.json").read_text(encoding="utf-8"))
occl = json.loads((RES / "occlusion_vs_retrain.json").read_text(encoding="utf-8"))
direction = json.loads(
    (DATA / "results_subnet_cf" / "direction_llm_judge.json").read_text(encoding="utf-8"))

# ---------- corpus size ----------
total_n = sum(int(r["n"]) for r in per_model.values())
# The abstract reports every audited narrative (model comparison + architecture
# experiment + prompt variants); the results section reports the ten-model
# comparison alone. Each is checked against its own scope.
arch_total = sum(
    len(list((DATA / "results_arch" / f"{a}{s}").glob("narrative_*.txt")))
    for a in ("gcn", "gin", "gat") for s in ("", "_kimi"))
variant_total = sum(
    len(list((DATA / "experiments" / v).glob("narrative_*.txt")))
    for v in ("opus_terse", "kimi_terse"))
check("corpus size (abstract, all audited)",
      find(r"evaluates (\d+) narratives", int), total_n + arch_total + variant_total, 0)
check("corpus size (results, 10-model)", find(r"a total of (\d+) audited", int), total_n, 0)

# ---------- Table II: every row ----------
NAME = {"Opus 4.8 (no bio.\\ prompt)": "opus_nobio", "Opus 4.8": "opus_default",
        "Opus 5": "opus5",
        "Sonnet 5": "sonnet_default", "DeepSeek-V3": "deepseek", "GLM-4.6": "glm",
        "Llama-3.3-70B": "llama", "Kimi K2": "kimi", "Qwen2.5-72B": "qwen",
        "Haiku 4.5": "haiku_default"}
for line in tex.splitlines():
    if "&" not in line or r"\\" not in line or "[" not in line:
        continue
    label = line.split("&")[0].strip()
    cfg = NAME.get(label)
    if not cfg:
        continue
    c = per_model[cfg]
    cells = [x.strip() for x in line.replace(r"\\", "").split("&")]
    if len(cells) < 5:
        continue
    n_txt = re.search(r"(\d+)", cells[2])
    check(f"Table II {label} n", int(n_txt.group(1)) if n_txt else None, int(c["n"]), 0)
    # Point estimate AND both interval bounds for recall and grounding.
    for idx, key in ((3, "recall"), (4, "grounding_precision")):
        nums = re.findall(r"(\d\.\d+)", cells[idx].replace(r"\textbf{", ""))
        lo_key = "recall_lo" if key == "recall" else "precision_lo"
        hi_key = "recall_hi" if key == "recall" else "precision_hi"
        if len(nums) >= 3:
            check(f"Table II {label} {key}", float(nums[0]), float(c[key]))
            check(f"Table II {label} {key} lo", float(nums[1]), float(c[lo_key]))
            check(f"Table II {label} {key} hi", float(nums[2]), float(c[hi_key]))
        else:
            check(f"Table II {label} {key}", None, float(c[key]))
    # The remaining three columns: fabrication, claim rate, hallucination rate.
    fab = re.search(r"(\d+\.\d+)", cells[5])
    check(f"Table II {label} fab", float(fab.group(1)) if fab else None,
          round(float(c["fabricated_per_narrative"]), 2), 0.006)
    for idx, key in ((6, "pct_making_a_claim"), (7, "pct_with_unsupported_claim")):
        m = re.search(r"(\d+)", cells[idx].replace(r"\textbf{", ""))
        check(f"Table II {label} {key}", float(m.group(1)) if m else None,
              round(float(c[key]) * 100), 0.6)

# ---------- scale table (Opus 4.8, full cohort) ----------
o = per_model["opus_default"]
check("scale: top-3 recall", find(r"Top-3 recall\s*&\s*(\d\.\d+)"), float(o["recall"]))
check("scale: grounding", find(r"Grounding precision\s*&\s*(\d\.\d+)"), float(o["grounding_precision"]))
check("prose: names 92.7%", find(r"it names (\d+\.\d+)\\% of the three"), 100 * float(o["recall"]), 0.06)
check("prose: grounding 48.0%", find(r"fewer than half — (\d+\.\d+)\\%"),
      100 * float(o["grounding_precision"]), 0.06)
check("scale: fabricated per narrative", find(r"Fabricated genes per narrative\s*&\s*(\d\.\d+)"),
      round(float(o["fabricated_per_narrative"]), 3), 0.0006)
check("scale: claim rate", find(r"Narratives asserting a claim\s*&\s*(\d+)\\%"),
      round(float(o["pct_making_a_claim"]) * 100), 0.6)
check("scale: unsupported rate",
      find(r"\\geq 1\$ unsupported claim\s*&\s*(?:\\textbf\{)?(\d+)"),
      round(float(o["pct_with_unsupported_claim"]) * 100), 0.6)
# Percentage of narratives naming an off-graph gene (distinct from the per-narrative rate).
_fabpct = 100 * sum(1 for r in csv.DictReader(
    open(RES / "per_narrative.csv", newline="", encoding="utf-8"))
    if r["config"] == "opus_default" and float(r["fabricated"]) > 0) / int(o["n"]) \
    if (RES / "per_narrative.csv").exists() else None
if _fabpct is not None:
    check("prose: off-graph gene rate",
          find(r"absent from the patient graph in only (\d+\.\d+)\\%"), _fabpct, 0.06)

# ---------- hedging ----------
check("hedging: overall pct", find(r"(\d+\.\d+)\\% of flagged claims are hedged"),
      hedge["hedged_pct"], 0.06)
hm = {r["config"]: r for r in hedge["per_config"]}
check("hedging: Opus hedged pct", find(r"Opus~4\.8 hedges (\d+\.\d+)\\%"),
      hm["opus_default"]["hedged_pct"], 0.06)
check("hedging: Qwen hedged pct", find(r"hedges only (\d+\.\d+)\\% of its unsupported"),
      hm["qwen"]["hedged_pct"], 0.06)

# ---------- census ----------
check("census: coverage pct", find(r"\((\d+\.\d+)\\%\) are gene--disease links"),
      census["coverage_pct"], 0.06)
# Match the thousands digit rather than hard-coding it: baking "1" or "6" into
# the pattern makes the check fail silently the moment a total crosses a
# thousand boundary, which is exactly when it most needs to fire.
check("census: checked count",
      find(r"corpus, (\d)\{,\}(\d+) of", lambda m: int(m[0] + m[1])),
      census["total_checked"], 0)
check("census: total assertions",
      find(r"of (\d)\{,\}(\d+) \(", lambda m: int(m[0] + m[1])),
      census["total_checked"] + census["total_unchecked"], 0)

# ---------- graph size, stated by every log's own header ----------
sizes = {m.group(1) for p in sorted((DATA / "clarus_logs_kirc").glob("*.txt"))
         for m in [re.search(r"top \d+ of (\d+) genes", p.read_text(encoding="utf-8"))]
         if m}
if len(sizes) == 1:
    check("cohort: genes per full network",
          find(r"contain (\d)\{,\}(\d+) genes per patient", lambda m: int(m[0] + m[1])),
          int(next(iter(sizes))), 0)

# ---------- threshold: every value quoted in the sweep sentence ----------
tmap = {r["threshold"]: r["mean"] for r in thresh}
check("threshold tau=0", find(r"falls from (\d\.\d+) at \$\\tau = 0\$"), tmap[0.0])
check("threshold tau=0.01", find(r"to (\d\.\d+) at \$\\tau = 0\.01\$"), tmap[0.01])
check("threshold tau=0.05", find(r"(\d\.\d+) at\n\$0\.05\$"), tmap[0.05])
check("threshold tau=0.10", find(r"(\d\.\d+) at \$0\.10\$"), tmap[0.1])
check("threshold tau=0.20", find(r"(\d\.\d+) at \$0\.20\$"), tmap[0.2])

# ---------- hedging: every row of the table ----------
HEDGE_ROWS = {"Opus 4.8": "opus_default", "Sonnet 5": "sonnet_default",
              "Haiku 4.5": "haiku_default", "Opus 5": "opus5",
              "Kimi K2": "kimi", "Qwen2.5-72B": "qwen"}
hedge_tbl = re.search(r"\\label\{tab:hedging\}(.*?)\\end\{tabular\}", tex, re.S)
hbody = hedge_tbl.group(1) if hedge_tbl else ""
for label, cfg in HEDGE_ROWS.items():
    row = re.search(rf"^{re.escape(label)}\s*&(.*?)\\\\", hbody, re.M)
    if not row or cfg not in hm:
        continue
    nums = re.findall(r"\d+\.?\d*", row.group(1).replace(r"\textbf{", ""))
    if len(nums) >= 4:
        check(f"hedging {label} flagged", float(nums[0]), hm[cfg]["flagged"], 0)
        check(f"hedging {label} hedged", float(nums[1]), hm[cfg]["hedged"], 0)
        check(f"hedging {label} pct", float(nums[3]), hm[cfg]["hedged_pct"], 0.06)
check("hedging total flagged (table)", find(r"\\textbf\{(\d+)\} & \\textbf\{\d+\} & \\textbf\{\d+\}", int),
      hedge["total_flagged"], 0)

# ---------- census breakdown ----------
tot_unchecked = census["total_unchecked"]
kinds = {k: sum(r[k] for r in census["per_config"]) for k in
         ("pathway", "prognosis", "offgraph_gene")}
check("census pathway pct", find(r"mechanistic roles \((\d+\.\d+)\\% of the"),
      100 * kinds["pathway"] / tot_unchecked, 0.06)
check("census offgraph pct", find(r"off-graph genes \((\d+\.\d+)\\%\)"),
      100 * kinds["offgraph_gene"] / tot_unchecked, 0.06)

# ---------- exposure percentages quoted inline, not just in the table ----------
# The prose gave Qwen as (34%, 26%) while the table and the data said 35% / 27%:
# a table cell can be right while the sentence beside it drifts.
INLINE = {
    "Qwen2.5-72B": ("qwen", r"Qwen2\.5-72B \((\d+)\\%, (\d+)\\%\)"),
    "Sonnet 5": ("sonnet_default", r"Sonnet~5 \((\d+)\\%, (\d+)\\%\)"),
    "Opus w/ instruction": ("opus_default", r"instruction \((\d+)\\%, (\d+)\\%\)"),
}
for label, (cfg, pat) in INLINE.items():
    got = find(pat, lambda m: [int(x) for x in m])
    if got and cfg in per_model:
        check(f"inline claims% {label}", got[0],
              round(float(per_model[cfg]["pct_making_a_claim"]) * 100), 0)
        check(f"inline halluc% {label}", got[1],
              round(float(per_model[cfg]["pct_with_unsupported_claim"]) * 100), 0)

# ---------- full-graph counterfactual flips and the random-gene control ----------
_fg = DATA / "results_arch" / "fullgraph_cf_diagnosis.json"
if _fg.exists():
    fg = json.loads(_fg.read_text(encoding="utf-8"))
    for arch, pat in (("gcn", r"class for (\d+\.\d+)\\% of GCN patients"),
                      ("gin", r"(\d+\.\d+)\\%\s*\n?of GIN"),
                      ("gat", r"and (\d+\.\d+)\\% of GAT")):
        if arch in fg:
            check(f"fullgraph flip {arch.upper()}", find(pat),
                  fg[arch]["top1_flip_pct"], 0.06)
    _rand = {a: fg[a]["random_gene_flip_pct"] for a in fg}
    check("fullgraph random-gene control",
          find(r"for any of the three \((\d+\.\d+)\\%"),
          max(_rand.values()), 0.06)
    check("fullgraph control n",
          find(r"\$n = (\d+)\$ each", int), min(fg[a]["n"] for a in fg), 0)

# ---------- discrimination metrics, from the platform's own recomputation ----------
_auroc = DATA / "results_arch" / "auroc_auprc.csv"
if _auroc.exists():
    _rows = {r["architecture"]: r for r in csv.DictReader(
        open(_auroc, newline="", encoding="utf-8"))
        if r.get("dataset") == "kirc_random_nodes_ui"}
    for arch, pat in (("gcn", r"AUROC (\d\.\d+) \(GCN\)"),
                      ("gin", r"(\d\.\d+) \(GIN\)"),
                      ("gat", r"(\d\.\d+) \(GAT\)")):
        if arch in _rows:
            check(f"AUROC {arch.upper()}", find(pat), float(_rows[arch]["auroc"]), 0.0006)
    _ap = find(r"AUPRC (\d\.\d+), (\d\.\d+) and (\d\.\d+)",
               lambda m: [float(x) for x in m])
    if _ap:
        for i, arch in enumerate(("gcn", "gin", "gat")):
            if arch in _rows:
                check(f"AUPRC {arch.upper()}", _ap[i],
                      float(_rows[arch]["auprc"]), 0.0006)
    _base = find(r"positive base\nrate of (\d\.\d+)")
    if _base is not None and "gcn" in _rows:
        check("AUPRC baseline", _base, float(_rows["gcn"]["auprc_baseline"]), 0.006)

# ---------- cohort composition, recomputed from the TCGA barcodes ----------
_bc = DATA / "kirc_barcodes.tsv"
if _bc.exists():
    _KIRC_TSS = {"3Z", "6D", "A3", "AK", "AS", "B0", "B2", "B4", "B8", "BP", "CB",
                 "CJ", "CW", "CZ", "DV", "DW", "EU", "GK", "MM", "MW", "T7", "G6"}
    _BRCA_TSS = {"A1", "A2", "A7", "A8", "AC", "AN", "AO", "AQ", "AR", "B6", "BH",
                 "C8", "D8", "E2", "E9", "EW", "GI", "GM", "HN", "LL", "LQ", "OL",
                 "PE", "S3", "UU", "V7", "W8", "WT", "XX", "Z7", "JL", "AZ", "OK", "EK"}
    _rows = [l.split("\t") for l in
             _bc.read_text(encoding="utf-8").strip().split("\n")[1:]]
    _tum = sum(1 for b, l in _rows if l == "1")
    _ctrl = [b for b, l in _rows if l == "0"]
    _second = sum(1 for b in _ctrl if len(b) == 13)
    _brca = sum(1 for b in _ctrl if len(b) == 12 and b.split("-")[1] in _BRCA_TSS)
    _luad = len(_ctrl) - _second - _brca
    check("cohort: total samples",
          find(r"of its (\d+) samples", int), len(_rows), 0)
    check("cohort: KIRC tumours",
          find(r"samples, (\d+) are KIRC tumours", int), _tum, 0)
    check("cohort: controls",
          find(r"and the (\d+) controls", int), len(_ctrl), 0)
    check("cohort: second samples",
          find(r"comprise (\d+) second samples", int), _second, 0)
    check("cohort: breast",
          find(r"with (\d+) breast", int), _brca, 0)
    check("cohort: lung",
          find(r"and (\d+) lung\s*\n?cancer cases", int), _luad, 0)

# ---------- cohort purity: the renal-subset robustness check ----------
_cp = RES / "cohort_purity.json"
if _cp.exists():
    cp = json.loads(_cp.read_text(encoding="utf-8"))
    n_all = len(cp)
    mean_all = sum(r["grounding_all"] for r in cp) / n_all
    mean_kid = sum(r["grounding_kidney"] for r in cp) / n_all
    check("purity: mean all", find(r"is\n?(\d\.\d+) on the full corpus"), mean_all, 0.0006)
    check("purity: mean renal",
          find(r"and (\d\.\d+) on the renal subset"), mean_kid, 0.0006)
    check("purity: renal n",
          find(r"renal subset alone: (\d+) of the 127", int),
          max(r["n_kidney"] for r in cp), 0)
    deltas = [r["delta"] for r in cp]
    check("purity: min delta",
          find(r"between \$-(\d\.\d+)\$", lambda s: -float(s)), min(deltas), 0.0006)
    check("purity: max delta",
          find(r"and\n?\$\+(\d\.\d+)\$", float), max(deltas), 0.0006)

# ---------- architecture table: the paper's strongest claim ----------
# This table went unverified while every weaker table was checked, and a cell
# had drifted from the data. Check every cell, and the derived spread with it.
ARCH_FILES = {"Opus 4.8": "architecture_comparison_opus.json",
              "Kimi K2": "architecture_comparison_kimi.json"}
arch_tbl = re.search(r"\\label\{tab:architecture\}(.*?)\\end\{tabular\}", tex, re.S)
abody = arch_tbl.group(1) if arch_tbl else ""
for label, fname in ARCH_FILES.items():
    path = DATA / "results_arch" / fname
    if not path.exists():
        continue
    per = {r["arch"]: r["grounding_precision"]
           for r in json.loads(path.read_text(encoding="utf-8"))}
    row = re.search(rf"^{re.escape(label)}\s*&(.*?)\\\\", abody, re.M)
    if not row:
        bad.append(f"architecture table: no row for {label}   <-- MISMATCH")
        continue
    cells = [c.strip() for c in row.group(1).split("&")]
    for i, arch in enumerate(("gcn", "gin", "gat")):
        got = re.search(r"(\d\.\d+)", cells[i])
        check(f"arch {label}/{arch.upper()}",
              float(got.group(1)) if got else None, per[arch], 0.0005)
    spread = re.search(r"(\d\.\d+)", cells[3])
    check(f"arch {label}/spread",
          float(spread.group(1)) if spread else None,
          max(per.values()) - min(per.values()), 0.0005)

# ---------- attribution quality: every cell of the new table ----------
_aq_path = DATA / "results_arch" / "attribution_quality_ci.json"
if _aq_path.exists():
    aq = json.loads(_aq_path.read_text(encoding="utf-8"))
    aq_tbl = re.search(r"\\label\{tab:attrquality\}(.*?)\\end\{tabular\}", tex, re.S)
    qbody = aq_tbl.group(1) if aq_tbl else ""
    for label, key in (("GCN", "gcn"), ("GIN", "gin"), ("GAT", "gat")):
        row = re.search(rf"^{re.escape(label)}\s*&(.*?)\\\\", qbody, re.M)
        if not row or key not in aq:
            continue
        cells = [c.strip() for c in row.group(1).split("&")]
        v = aq[key]
        fp = re.search(r"(\d\.\d+)", cells[0].replace(r"\textbf{", ""))
        check(f"attrquality {label}/Fid+",
              float(fp.group(1)) if fp else None, v["fidelity_plus"]["mean"], 0.0005)
        lo_hi = re.findall(r"(\d\.\d+)", cells[0].replace(r"\textbf{", ""))
        if len(lo_hi) == 3:
            check(f"attrquality {label}/Fid+ lo", float(lo_hi[1]),
                  v["fidelity_plus"]["lo"], 0.0005)
            check(f"attrquality {label}/Fid+ hi", float(lo_hi[2]),
                  v["fidelity_plus"]["hi"], 0.0005)
        dist = re.search(r"(\d+)", cells[2].replace(r"\textbf{", ""))
        check(f"attrquality {label}/distinct",
              int(dist.group(1)) if dist else None, v["distinct_genes_in_topk"], 0)
        jac = re.search(r"(\d\.\d+)", cells[3].replace(r"\textbf{", ""))
        check(f"attrquality {label}/jaccard",
              float(jac.group(1)) if jac else None, v["mean_pairwise_jaccard"], 0.0005)

# ---------- modality language ----------
modality = json.loads((RES / "modality_language.json").read_text(encoding="utf-8"))
_ts, _es = modality["transcriptomic_sentences"], modality["epigenomic_sentences"]
check("modality: committed sentences",
      find(r"Of the (\d+) sentences that commit to a modality", int), _ts + _es, 0)
check("modality: transcriptomic count",
      find(r"modality, (\d+) \(9", int), _ts, 0)
check("modality: transcriptomic share",
      find(r"\((\d+\.\d+)\\%\) are\ntranscriptomic"),
      modality["transcriptomic_share_of_modality_sentences"], 0.06)
check("modality: epigenomic count",
      find(r"against (\d+) epigenomic", int), _es, 0)
check("modality: pct transcriptomic only",
      find(r"Some (\d+\.\d+)\\% of narratives use transcriptomic"),
      modality["pct_transcriptomic_only"], 0.06)
check("modality: pct both or agnostic",
      find(r"only (\d+\.\d+)\\% either name both"),
      modality["pct_both_or_agnostic"], 0.06)
# The claim that no log names a modality is what makes the finding a pipeline
# defect rather than a model one, so verify it against the logs themselves.
_logs = sorted((DATA / "clarus_logs_kirc").glob("*.txt"))
_with_modality = sum(
    1 for p in _logs
    if re.search(r"methyl|mRNA|expression|epigen|modalit", p.read_text(encoding="utf-8"),
                 re.I))
check("modality: logs naming a modality",
      0 if re.search(r"across\s+all\s+127\s+logs,\s+not\s+one\s+contains\s+a\s+"
                     r"modality\s+term", tex) else None, _with_modality, 0)

# ---------- emphasis: mean across configurations ----------
import statistics as _st
check("emphasis mean rho", find(r"and \$(\d\.\d+)\$ averaged over all configurations"),
      _st.fmean(v["mean_spearman"] for v in emphasis.values()), 0.006)

# ---------- emphasis ----------
check("emphasis: opus rho", find(r"Spearman \$\\rho = (\d\.\d+)\$ for this"),
      emphasis["opus_default"]["mean_spearman"], 0.006)

# ---------- repeatability ----------
check("repeat: deepseek SD", find(r"0\.461 \(SD (\d\.\d+)\)"), repeat["deepseek"]["sd"], 0.002)
check("repeat: haiku SD", find(r"0\.440 \(SD (\d\.\d+)\)"), repeat["haiku"]["sd"], 0.002)

# ---------- occlusion vs retrain ----------
check("occlusion: agreement", find(r"the two agree on 29\s*\n?\((\d+\.\d+)\\%\)"),
      100 * occl["agreement"], 0.06)
check("occlusion: occ flips", find(r"giving (\w+) flips under occlusion",
                                   lambda s: {"four": 4, "three": 3}.get(s, -1)),
      occl["occlusion_flips"], 0)

# ---------- direction ----------
check("direction accuracy", find(r"(\d+\.\d+)\\% of the\s*\n?time"),
      100 * direction["summary"]["direction_accuracy"], 0.06)

# ---------- architecture experiment ----------
inter = json.loads((RES / "interaction.json").read_text(encoding="utf-8"))
grid = inter["grid"]
# Scope the search to the architecture table; several model names also appear as
# row labels in the cross-model table, which would otherwise match first.
arch_tbl = re.search(r"\\label\{tab:architecture\}(.*?)\\end\{tabular\}", tex, re.S)
arch_body = arch_tbl.group(1) if arch_tbl else ""
for llm in ("opus", "kimi"):
    label = {"opus": "Opus 4.8", "kimi": "Kimi K2"}[llm]
    row = re.search(rf"^{re.escape(label)}\s*&(.*?)\\\\", arch_body, re.M)
    if not row:
        bad.append(f"Table arch {label}: row NOT FOUND")
        continue
    vals = re.findall(r"(\d\.\d+)", row.group(1).replace(r"\textbf{", ""))
    for idx, arch in enumerate(("gcn", "gin", "gat")):
        cell = grid.get(f"{llm}|{arch}")
        if cell and idx < len(vals):
            check(f"Table arch {label}/{arch.upper()}", float(vals[idx]), cell["grounding"])
check("architecture spread (arch fixed narrator)",
      find(r"moves grounding precision by (\d\.\d+) on average"),
      inter["mean_spread_across_architectures"])
check("narrator spread (narrator fixed arch)",
      find(r"architecture fixed moves it by (\d\.\d+)"),
      inter["mean_spread_across_narrators"])

# ---------- ablation table (full cohort, both Opus 4.8 conditions) ----------
nb, df = per_model["opus_nobio"], per_model["opus_default"]
abl = re.search(r"\\label\{tab:ablation\}(.*?)\\end\{tabular\}", tex, re.S)
abody = abl.group(1) if abl else ""
row = re.search(r"Grounding precision[^&]*&([^&]*)&([^\\]*)", abody)
if row:
    off = re.findall(r"(\d\.\d+)", row.group(1))
    on = re.findall(r"(\d\.\d+)", row.group(2))
    if len(off) >= 3 and len(on) >= 3:
        for i, key in enumerate(("grounding_precision", "precision_lo", "precision_hi")):
            check(f"ablation off {key}", float(off[i]), float(nb[key]))
            check(f"ablation on {key}", float(on[i]), float(df[key]))
check("ablation caption n", find(r"Prompt ablation over the full cohort \(\$n = (\d+)\$\)", int),
      int(nb["n"]), 0)

# ---------- mitigation table (full cohort) ----------
mit = json.loads((RES / "mitigation_full.json").read_text(encoding="utf-8")) \
    if (RES / "mitigation_full.json").exists() else None
if mit:
    check("mitigation flagged before", find(r"Symbolic filtering\s*&\s*(\d+) \$"), mit["before"], 0)
    check("mitigation symbolic recall", find(r"\(100\\%\)\s*&\s*(\d\.\d+)"), mit["symbolic_recall"], 0.002)

# ---------- hedging: asserted column and totals ----------
for label, cfg in HEDGE_ROWS.items():
    row = re.search(rf"^{re.escape(label)}\s*&(.*?)\\\\", hbody, re.M)
    if row and cfg in hm:
        nums = re.findall(r"\d+\.?\d*", row.group(1).replace(r"\textbf{", ""))
        if len(nums) >= 3:
            check(f"hedging {label} asserted", float(nums[2]), hm[cfg]["asserted"], 0)
tot = re.search(r"\\textbf\{All ten\}(.*?)\\\\", hbody, re.S)
if tot:
    tn = re.findall(r"\d+\.?\d*", tot.group(1).replace(r"\textbf{", ""))
    if len(tn) >= 4:
        check("hedging total flagged", float(tn[0]), hedge["total_flagged"], 0)
        check("hedging total hedged", float(tn[1]), hedge["total_hedged"], 0)
        check("hedging total asserted", float(tn[2]),
              hedge["total_flagged"] - hedge["total_hedged"], 0)

# ---------- repeatability: every per-run value quoted in prose ----------
for cfg, pat in (("deepseek", r"DeepSeek-V3 gave ([\d., and]+)\(SD"),
                 ("kimi", r"Kimi~K2 gave ([\d., and]+)\(SD")):
    m = re.search(pat, tex)
    if m and cfg in repeat:
        vals = [float(x) for x in re.findall(r"\d\.\d+", m.group(1))]
        for i, v in enumerate(vals):
            if i < len(repeat[cfg]["per_run"]):
                check(f"repeat {cfg} run{i+1}", v, repeat[cfg]["per_run"][i], 0.002)
hk = repeat.get("haiku", {})
if hk:
    check("repeat haiku min", find(r"differently, spanning (\d\.\d+) to"), min(hk["per_run"]), 0.002)
    check("repeat haiku max", find(r"spanning \d\.\d+ to (\d\.\d+)"), max(hk["per_run"]), 0.002)

# ---------- architecture spread column ----------
for llm, key in (("Opus 4.8", "opus"), ("Kimi K2", "kimi")):
    row = re.search(rf"^{re.escape(llm)}\s*&(.*?)\\\\", arch_body, re.M)
    if row:
        v = re.findall(r"(\d\.\d+)", row.group(1).replace(r"\textbf{", ""))
        if len(v) >= 4:
            gs = [grid[f"{key}|{a}"]["grounding"] for a in ("gcn", "gin", "gat")
                  if f"{key}|{a}" in grid]
            check(f"arch {llm} spread", float(v[3]), max(gs) - min(gs))

# ---------- terse prompt variant ----------
terse = json.loads((RES / "terse_variant.json").read_text(encoding="utf-8")) \
    if (RES / "terse_variant.json").exists() else None
if terse:
    m = re.search(r"--- (\d+) to (\d+) characters for Opus~4\.8, (\d+) to\n(\d+) for Kimi", tex)
    if m:
        for i, cfg in enumerate(("opus_default", "opus_terse", "kimi", "kimi_terse")):
            check(f"terse chars {cfg}", float(m.group(i + 1)), terse[cfg]["mean_chars"], 0.6)
    m2 = re.search(r"exposure moved from (\d+)\\% to (\d+)\\% for Opus and (\d+)\\% to (\d+)\\%", tex)
    if m2:
        for i, cfg in enumerate(("opus_default", "opus_terse", "kimi", "kimi_terse")):
            check(f"terse halluc {cfg}", float(m2.group(i + 1)), terse[cfg]["pct_halluc"], 0.6)

# ---------- assorted prose figures ----------
check("emphasis exact-order pct", find(r"exactly in\n(\d+\.\d+)\\% of narratives"),
      emphasis["opus_default"]["pct_exact_order"], 0.06)
lex = json.loads((DATA / "results_subnet_cf" / "direction.json").read_text(encoding="utf-8"))
check("lexical heuristic direction", find(r"scored the same narratives at (\d\.\d+)"),
      lex["summary"]["direction_accuracy_overall"], 0.006)
check("census prognosis pct", find(r"prognosis or subtype \((\d+\.\d+)\\%\)"),
      100 * kinds["prognosis"] / tot_unchecked, 0.06)
if mit:
    check("mitigation claim-level recall", find(r"\(100\\%\)\s*&\s*(\d\.\d+)\s*&\s*90"),
          mit["claim_level_recall"], 0.002)

# ---------- prose comparisons in the cross-model discussion ----------
ds = per_model["deepseek"]
m = re.search(r"versus\n(\d\.\d+) \[(\d\.\d+), (\d\.\d+)\]\); the weakest", tex)
if m:
    for i, key in enumerate(("grounding_precision", "precision_lo", "precision_hi")):
        check(f"prose DeepSeek {key}", float(m.group(i + 1)), float(ds[key]))

# ---------- setup figures that come from the data or the code ----------
import pickle as _pickle

from _paths import KIRC_PICKLE as _ds_path, PACKAGE as _PKG

# The cohort size is checked only when the platform checkout is available, since
# the dataset is far too large to vendor into this repository.
if _ds_path is not None and _ds_path.exists():
    try:
        _g = _pickle.load(open(_ds_path, "rb"))[0]
        check("cohort: genes per patient",
              find(r"contain 1\{,\}(\d+) genes per patient", lambda s: int("1" + s)),
              len(_g.node_labels), 0)
    except Exception:
        pass
_stats_src = (_PKG / "stats.py").read_text(encoding="utf-8")
_nboot = re.search(r"n_boot: int = (\d+)", _stats_src)
if _nboot:
    check("bootstrap resamples",
          find(r"with 2\{,\}(\d+) resamples", lambda s: int("2" + s)), int(_nboot.group(1)), 0)

# ---------- report ----------
import os
print(f"VERIFIED {len(ok)} numeric claims against source data\n")
if bad:
    print(f"{len(bad)} PROBLEM(S):")
    for b in bad:
        print("  " + b)
else:
    print("no discrepancies found")

# audit_coverage.py parses this to learn which literals are already checked.
if os.environ.get("AUDIT_VERBOSE"):
    print("\n--- checked values ---")
    for line in ok:
        print("  " + line)
