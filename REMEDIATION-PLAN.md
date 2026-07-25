# Remediation plan

**Status: not ready for JBHI submission.** This plan is the route back to
submittable, not a defence of the current manuscript.

Prepared 25 July 2026. All rejection-level findings from the independent review
are accepted. Cosmetic manuscript repair is deliberately scheduled last, after
the corrected results are frozen.

## The deadline question, stated plainly

The Knowledge Graphs and Multimodal Data Fusion special issue closes **31 August
2026**. The critical path below is roughly fourteen weeks. **That deadline is
unreachable and should be abandoned rather than met with a patched manuscript.**

Three routes remain, in order of preference:

1. **JBHI as a regular submission.** JBHI accepts regular papers year-round with
   no deadline. Same journal, same audience, no schedule pressure. This is the
   recommended route.
2. **A later special issue.** *Multimodal Large Language Models for Precision and
   Preventive Healthcare* closes 31 October 2026 — still inside the critical
   path, so only viable if WP2 and WP6 finish early. Fit is weaker than the
   current target.
3. Hold for a 2027 call.

Nothing below assumes a deadline. Dates are the earliest defensible completion
given the dependencies, not targets to compress.

## Critical path

```
WP7 licensing ──────────────────────────────(external, start now)────────────┐
WP0 units ─→ WP1 folds ─→ WP2 retrain ─→ WP3 narratives ─→ WP4 counterfactuals ┤
WP5 annotation (parallel, human-bound) ──────────────────────────────────────┤
WP6 verifier (parallel, research) ───────────────────────────────────────────┤
                                                                              ↓
                                                    WP8 release → WP9 layout → freeze
```

---

## WP0 — Correct the log units and index utilities

| | |
|---|---|
| **Deliverable** | Regenerated explanation logs with sensitivity/specificity as percentages, plus a shared barcode↔index utility used by every downstream script. |
| **Inputs** | `generate_corpus_kirc.py`, `generate_corpus_arch.py`, `test_set_metrics_dict.pkl`, `kirc_barcodes.tsv`. |
| **Command** | Patch `fmt_metrics()` in both generators; `python generate_corpus_kirc.py`; `python generate_corpus_arch.py {gcn,gin,gat} 60`. |
| **Acceptance** | No log contains `0.75%` or `0.74%`; every log states 75% / 74%. A unit test asserts sensitivity in [0,100] and consistent with the confusion matrix. |
| **Sections** | §IV-B Explanation Logs; §V-A. |
| **Depends on** | Nothing. |
| **Complete by** | **2 Aug 2026** |

Note: this invalidates every existing narrative, because the corpus is
regenerated from corrected logs. That is the reason WP3 exists.

## WP1 — Participant-grouped folds

| | |
|---|---|
| **Deliverable** | Five participant-grouped, class-stratified folds in which no TCGA participant appears in more than one partition, with a leakage assertion that fails loudly. |
| **Inputs** | `kirc_barcodes.tsv` (455 participants over 506 records), current `split_indexes`. |
| **Command** | New `experiments/make_grouped_folds.py` using `StratifiedGroupKFold`, group = first 12 barcode characters. |
| **Acceptance** | For every fold and every architecture: 0 participants shared between train, validation and test. Current splits fail this with 16 train–test, 7 validation–test and 9 train–validation overlaps. |
| **Sections** | §IV-A Cohort; §IV-E Statistical Reporting; §VI-C Threats. |
| **Depends on** | WP0 (shared index utility). |
| **Complete by** | **14 Aug 2026** |

## WP2 — Multi-seed retraining on leak-free folds

| | |
|---|---|
| **Deliverable** | GCN, GIN and GAT trained on 5 folds × 5 seeds = 75 checkpoints, with per-checkpoint metrics, raw probabilities and calibration. |
| **Inputs** | WP1 folds; `model_factory.py`; `gnn_train_test_methods.py`. |
| **Command** | New `experiments/train_grouped.py --arch {gcn,gin,gat} --folds 5 --seeds 5`, CPU torch 2.9.1. |
| **Acceptance** | Raw per-sample probabilities persisted for every checkpoint; AUROC/AUPRC reported as mean ± SD across seeds, not single values; accuracy re-reported post-leakage-removal (expect it to fall from 0.78–0.87). |
| **Sections** | §IV-A; §V-H controls; Table VI; §VI-C. |
| **Depends on** | WP1. |
| **Complete by** | **11 Sep 2026** |

This is the compute bottleneck. Budget slippage here before anywhere else.

## WP3 — Regenerate the narrative corpus

| | |
|---|---|
| **Deliverable** | Full corpus regenerated from corrected logs and leak-free checkpoints, with provider, model snapshot, decoding parameters, seed and request ID persisted per narrative. |
| **Inputs** | WP0 logs, WP2 checkpoints, `gnnarrate/llm.py`, API credit. |
| **Command** | `python examples/run_model_comparison.py --record-metadata`; `python examples/run_architecture_experiment.py`. |
| **Acceptance** | Every narrative has a sidecar JSON with model snapshot and request metadata; ≥3 independent generations per patient/configuration so LLM sampling enters the intervals. |
| **Sections** | §IV-D Models Evaluated; §V-C to §V-G; all result tables. |
| **Depends on** | WP0, WP2. |
| **Complete by** | **25 Sep 2026** |

Cost: roughly 3× the previous corpus. Estimate before starting, not during.

## WP4 — Matched counterfactual controls

| | |
|---|---|
| **Deliverable** | Counterfactual analysis in which edited retraining is compared against **unedited retraining under the same seed**, not against the original checkpoint. |
| **Inputs** | WP2 checkpoints; `compare_occlusion_retrain.py`; full row-level output. |
| **Command** | Extend `compare_occlusion_retrain.py` to emit matched pairs and probability deltas; ≥20 random-gene controls per patient, matched on degree and rank. |
| **Acceptance** | Reported flip counts use the matched comparator. Current data show 4/30 for unedited-retrain-vs-original but only **1/30** for edited-vs-unedited — the manuscript's interpretation does not survive. Random controls report an interval, not a bare 0/30. |
| **Sections** | §IV-C Counterfactual Logs; §V-B; §VI-C. |
| **Depends on** | WP2. |
| **Complete by** | **2 Oct 2026** |

## WP5 — Expert biological annotation

| | |
|---|---|
| **Deliverable** | Blinded annotations from two domain readers over a stratified sample of ≥200 claims, with Cohen's κ, and verifier precision, recall and calibration against them. |
| **Inputs** | `data/annotation/annotate_*.html`, `answer_key.json`, extended categories for polarity, disease identity and phenotype. |
| **Command** | `python examples/make_annotation_task.py --annotator {abdullah,alfarraj} --n 200 --categories extended`; score with `score_annotation.py`. |
| **Acceptance** | κ reported; verifier precision/recall against human labels reported; the phenotype category is explicitly annotated so the false-phenotype rate is measured rather than regex-estimated. |
| **Sections** | §III-D; §V-A; §VI-A; abstract. |
| **Depends on** | Nothing — **can start immediately**. Claim identity does not depend on which narrative produced it, so calibration transfers to the regenerated corpus. |
| **Complete by** | **22 Aug 2026** |

Start this first. It is the only task gated on human availability rather than
compute, and it is the single largest credibility gain.

## WP6 — Relation-, polarity-, disease- and class-aware verifier

| | |
|---|---|
| **Deliverable** | A verifier that extracts subject, relation, polarity/negation, disease ontology ID and predicted-class direction, replacing sentence-level co-occurrence. |
| **Inputs** | Open Targets with disease IDs and evidence provenance; HGNC alias table; the WP5 annotations as ground truth. |
| **Command** | New `gnnarrate/grounding_v2.py` plus a scispaCy or equivalent relation layer; `python examples/threshold_sensitivity.py` re-run over calibrated thresholds. |
| **Acceptance** | Precision/recall against WP5 labels beats the current heuristic by a pre-registered margin; direct and indirect Open Targets evidence reported separately; thresholds justified rather than τ=0; coverage above the current 28.2% and stated explicitly. |
| **Sections** | §III-C Biomedical Groundedness; §V-A; §V-I; §VI-A. |
| **Depends on** | WP5 for ground truth. |
| **Complete by** | **30 Sep 2026** |

This is a research task, not an engineering one. It is the finding the reviewer
called the single strongest reason to reject, and it is where the paper's
novelty ultimately rests.

## WP7 — Licensing clearance (start immediately)

| | |
|---|---|
| **Deliverable** | A legally releasable artefact, by one of: written permission from HCI-KDD; replacement of the reused CLARUS code; or a release containing only original modules with the upstream dependency documented. |
| **Inputs** | `LICENSING_STATUS.md`, `ATTRIBUTION.md`. |
| **Command** | Written request to A. Saranti / A. Holzinger; failing a reply within 4 weeks, take path 3. |
| **Acceptance** | Either written permission on file, or a release that provably contains no upstream CLARUS code. The combined work is GPL-3.0 in either case, because GNN-SubNet is GPL-3.0. |
| **Sections** | §IV-F Reproducibility; Acknowledgment. |
| **Depends on** | Nothing — **longest lead time and outside our control**. |
| **Complete by** | **Request sent 27 Jul 2026; decision point 24 Aug 2026** |

CLARUS carries **no licence at all** — all rights reserved. The reviewer's
request to deposit "the modified CLARUS platform" cannot be met lawfully unless
permission is granted. A previous attempt to contact the authors went
unanswered, so plan for path 3 and treat permission as upside.

## WP8 — Immutable reproducibility release

| | |
|---|---|
| **Deliverable** | A DOI-bearing Zenodo deposit: narratives with metadata, corrected logs, association cache with release version and provenance, participant-grouped splits, raw probabilities, all counterfactual rows, prompts, checksums, and a one-command reproduction target. |
| **Inputs** | Frozen WP2–WP6 outputs; WP7 decision. |
| **Command** | `make release` producing a manifest with SHA-256 per file; deposit to Zenodo; cite the DOI in the manuscript. |
| **Acceptance** | A clean clone plus the deposit regenerates every table without local data. The present repository tracks **zero** files under `data/`, so §IV-F is currently false and must not be restored until this passes. |
| **Sections** | §IV-F; footnote repository reference. |
| **Depends on** | WP2–WP6 frozen; WP7. |
| **Complete by** | **20 Oct 2026** |

## WP9 — Dependency and platform hygiene

| | |
|---|---|
| **Deliverable** | Zero high-severity advisories in the released artefact, with a documented audit. |
| **Inputs** | `npm audit`, `pip-audit` over the platform. |
| **Command** | `npm audit fix`; `pip-audit -r requirements.txt`; pin transitive versions. |
| **Acceptance** | Nine currently reported high-severity vulnerabilities resolved or documented with justification. |
| **Sections** | §IV-F. |
| **Depends on** | Nothing; run in parallel. |
| **Complete by** | **30 Aug 2026** |

## WP10 — Layout and presentation repair (last)

| | |
|---|---|
| **Deliverable** | A submission that compiles cleanly with no overfull boxes and a readable supplement. |
| **Inputs** | Frozen results from WP2–WP6. |
| **Command** | Convert Tables II and VI to `table*` or redesign; add `\bibliography` to `supplementary.tex` so citations stop rendering as `[?]`; page-break the supplement; re-run `paper_audit/*`. |
| **Acceptance** | No overfull box above 5pt; no `[?]` citations; `check_tikz` and `check_jbhi` pass; page count re-estimated after the corrected results change the text. |
| **Sections** | Whole document. |
| **Depends on** | **Everything.** Deliberately last — the tables will change. |
| **Complete by** | **28 Oct 2026** |

---

## Summary

| WP | Deliverable | Done by | Blocks |
|---|---|---|---|
| WP5 | Expert annotation | 22 Aug | WP6 |
| WP7 | Licensing decision | 24 Aug | WP8 |
| WP0 | Corrected log units | 2 Aug | WP1, WP3 |
| WP9 | Dependency remediation | 30 Aug | — |
| WP1 | Participant-grouped folds | 14 Aug | WP2 |
| WP2 | Multi-seed retraining | 11 Sep | WP3, WP4 |
| WP3 | Regenerated narratives | 25 Sep | WP8 |
| WP6 | Relation-aware verifier | 30 Sep | WP8 |
| WP4 | Matched counterfactuals | 2 Oct | WP8 |
| WP8 | Immutable release | 20 Oct | WP10 |
| WP10 | Layout repair | 28 Oct | — |

**Earliest defensible submission: early November 2026**, as a JBHI regular
paper. The status remains *not ready for JBHI submission* until WP0–WP8 are
complete.

## What survives unchanged

The reruns will move numbers, but three findings rest on structure rather than
on the leaked splits and should survive:

- **Faithfulness and groundedness dissociate.** Measured per narrative against
  its own log; leakage affects the classifier, not whether a narrative reports
  its log correctly.
- **Explanations are near-invariant across patients.** GAT draws its top five
  from seven genes over sixty patients; that is a property of the explainer.
- **No attribution is computed over node features**, so modality cannot reach
  the narrator. This is a code fact, independent of any split.

The architecture ceiling result and every rate — grounding precision,
hallucination exposure, fabrication — must be treated as unestablished until
WP2 and WP6 land.
