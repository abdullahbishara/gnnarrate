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

1. **JBHI as a regular submission.** Same journal and audience without a
   deadline, and the recommended route — **but treat this as unverified until
   confirmed with the JBHI Author Portal or editorial office** that regular
   submissions are currently open and under what requirements. Do not state it
   categorically to anyone until that confirmation is in hand.
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
                                          WP8 release → WP10 layout → freeze
(WP9 dependency hygiene runs in parallel throughout and gates release, not layout.)
```

---

## WP0 — Correct the log units and index utilities

| | |
|---|---|
| **Deliverable** | Corrected metric serialisation in all four generators, plus a validator and tests. Log *regeneration* is deferred to WP3. |
| **Inputs** | `generate_corpus_{kirc,arch,,kirc_cf}.py`, `test_set_metrics_dict.pkl`, `kirc_barcodes.tsv`. |
| **Command** | `_as_percent()` helper in all four generators (**done**); `gnnarrate.clarus_log.GraphState.metric_inconsistencies()` (**done**); `pytest tests/test_metric_units.py` (**done, 5 tests**). |
| **Acceptance** | The validator flags a fraction written with a percent sign and passes on correct percentages; a test asserts the *current* corpus still fails, so the defect cannot be silently forgotten before WP3 flips it. |
| **Sections** | §IV-B Explanation Logs; §V-A. |
| **Depends on** | Nothing. |
| **Complete by** | **Code and tests complete 26 Jul 2026**; corrected logs emitted as part of WP3. |

**The fix and its tests land now; the final logs are generated after WP2**,
against the leak-free checkpoints, so the corpus is built once rather than
twice. The four generators are patched and a validator plus five tests are in
place; the released corpus still carries the defect and a test asserts that,
so it cannot be forgotten. Regenerating now would be wasted work, because WP2
changes the checkpoints the logs describe.

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
| **Acceptance** | Raw per-sample probabilities persisted for every checkpoint; AUROC/AUPRC reported as mean ± SD across seeds, not single values; accuracy re-reported post-leakage-removal — **expected to change rather than necessarily to fall**, since grouped folds also alter class balance and training-set size. |
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
| **Deliverable** | Two stages. **(a) Protocol and pilot** on the current corpus: annotation categories, instructions, qualification criteria, ethics determination, and a pilot of ~50 claims to test the instrument. **(b) Final blinded validation** drawn from the *frozen regenerated* corpus, ≥200 claims, with Cohen's κ and verifier precision, recall and calibration. |
| **Inputs** | `data/annotation/`, extended categories for polarity, disease identity, class direction and phenotype; documented annotator expertise; ethics determination. |
| **Command** | `python examples/make_annotation_task.py --annotator {…} --n {50 pilot, 200 final} --categories extended`; score with `score_annotation.py`. |
| **Acceptance** | κ reported with CI; verifier precision/recall against human labels; phenotype annotated explicitly so its rate is *measured*, not regex-estimated; **a held-out annotation set reserved and not used while developing WP6**. |
| **Sections** | §III-D; §V-A; §VI-A; abstract. |
| **Depends on** | Pilot: nothing, starts now. **Final validation depends on WP3**, because the frozen corpus is what must be validated. |
| **Complete by** | Protocol + ethics request **1 Aug 2026**; pilot **22 Aug 2026**; **final validation after WP3 freezes**. |

**Correction to an earlier draft of this plan.** It claimed annotation of the
current corpus would validate the verifier on the regenerated one, because
"claim identity does not depend on which narrative produced it". That is wrong.
Retraining and corrected prompts change *which* claims appear and in what
proportions, so the distribution and the claim types both shift. The pilot
establishes and de-risks the instrument; **only the frozen regenerated corpus
can furnish the validation figure that goes in the paper.**

Annotators must be qualified domain readers with their expertise documented, an
institutional ethics determination must be obtained if required, and a held-out
portion must never be seen during WP6 development, or the verifier is tuned on
its own test set.

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
| **Deliverable** | Written clearance from KFUPM legal / technology transfer covering one specific release configuration, supported by a file-level provenance matrix. |
| **Inputs** | `LICENSING_STATUS.md`, `ATTRIBUTION.md`, `PROVENANCE-MATRIX.md`, upstream `GNN_Counterfactuals` tree at the fork commit. |
| **Command** | `python build_provenance_matrix.py`; diff every CLAIMED ORIGINAL file against upstream; submit matrix plus draft letter to the institution. |
| **Acceptance** | **Written institutional clearance on file.** Our own conclusion that a configuration is lawful is explicitly *not* sufficient. |
| **Sections** | §IV-F Reproducibility; Acknowledgment. |
| **Depends on** | Nothing — **longest lead time, outside our control, start immediately**. |
| **Complete by** | Matrix built (done); letter drafted (done); **submitted to institution 29 Jul 2026**; decision point **when clearance is received**, not on a date we choose. |

CLARUS carries **no licence at all**, so default copyright reserves all rights
and there is no automatic permission to reproduce, distribute or make derivative
works. GNN-SubNet is GPL-3.0, whose obligations depend on *how* its code is
combined with ours rather than on the mere fact of use.

**The "release only our original modules" fallback is not automatically
lawful** and must not be treated as a safe default. It is only available if
those modules are demonstrably separable and contain no copied or adapted CLARUS
code. Four questions must go to institutional review, not be answered by us:

1. whether the original modules are legally separable from CLARUS;
2. whether a clean-room reimplementation is required instead;
3. whether GNN-SubNet code is incorporated, or only its data used — the GPL
   consequence differs sharply between the two;
4. which GPL obligations attach to each proposed release configuration.

The provenance matrix already shows why this cannot be settled informally: of
226 source files, **11 carry an original-authorship header, 94 carry HCI-KDD
headers, and 121 carry no header at all**. Over half the tree is of
undetermined origin, and a header is in any case evidence of what someone typed,
not of what was copied. **No fallback bundle may be published until the
provenance diff and the legal review are complete.**

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

**Provisional scenario, not a commitment: not before November 2026.** Licensing
clearance, the ethics determination, expert availability and the WP6 research
outcome are each uncertain and any one of them can move this date. No submission
date should be quoted externally until WP7 clears and WP5's pilot has run.

The status remains *not ready for JBHI submission* until **WP0–WP10** are
complete — including WP9 and WP10, not WP0–WP8.

**The regular-submission route must be confirmed, not assumed.** Before relying
on it, check with the JBHI Author Portal or editorial office that regular
submissions are currently open, and under what requirements; this plan treats
that as unverified.

## What survives, and what must be retested

Exactly **one** finding is a stable fact about the code rather than about a
particular set of checkpoints:

- **No attribution is computed over the node features.** Relevance is computed
  over a mask on the edges and summed to nodes, so mRNA and methylation never
  enter the explanation. True by inspection of `gnn_explanations.py`,
  independent of any split, seed or checkpoint.

Everything else is a **hypothesis to retest** after participant-grouped,
multi-seed retraining, including two that an earlier draft of this plan wrongly
listed as safe:

- **Faithfulness/groundedness dissociation.** New checkpoints produce new
  attributions and therefore new claims; the dissociation may narrow, widen or
  reverse.
- **Near-invariant explanations.** GAT's seven-gene top-five is a property of
  *these* checkpoints. Retraining may change the degeneracy entirely.
- **The architecture ceiling result**, and every rate: grounding precision,
  hallucination exposure, fabrication, modality language.

Accuracy is **expected to change** rather than necessarily to fall: removing 16
train–test participant overlaps removes an optimistic bias, while grouped folds
also alter class balance and training-set size, and the net effect is not
predictable in advance.
