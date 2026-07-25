# DRAFT — annotation protocol and ethics determination request

Not to be executed until reviewed. The pilot may run on the current corpus; the
**validation figure reported in the paper must come from the frozen regenerated
corpus**, because retraining and corrected prompts change which claims appear
and in what proportion.

---

## 1. Purpose

Establish, against qualified human judgement, how well the automatic verifier
identifies unsupported biomedical assertions. The current verifier is a
sentence-level co-occurrence lookup with a nonzero-score threshold. It is
polarity-blind, class-blind and disease-ambiguous, and covers 28.2% of
assertions. Nothing in the paper may describe it as measuring biomedical
correctness until this validation exists.

## 2. Design

- **Two independent annotators**, blinded to the automatic label and to each
  other until both finish.
- **Pilot:** ~50 claims from the current corpus. Purpose is to test the
  instrument — category clarity, disagreement patterns, time per claim — not to
  produce a reportable figure.
- **Final:** ≥200 claims sampled from the **frozen regenerated corpus**,
  stratified by automatic label, configuration, and cancer type of the source
  sample (KIRC / BRCA / LUAD).
- **Held-out portion:** 30% of the final set is sealed and **not consulted
  during WP6 development**. Developing the verifier against the same claims used
  to evaluate it would tune it on its own test set.

## 3. Categories

Per claim, the annotator records:

| Field | Values |
|---|---|
| Evidence for the gene–disease link | supported / not supported / unsure |
| Relation polarity | asserts association / asserts absence / hedged / not a claim |
| Disease identity | the renal disease / a different disease / ambiguous |
| Class direction | offered as evidence *for* the predicted class / *against* / unclear |
| Phenotype statement | describes the sample as cancerous / non-cancerous / not stated |

The last two exist because the current verifier is blind to both, and the
phenotype field is what converts the false-phenotype rate from a lexical
estimate into a measurement.

"Unsure" is always available and is excluded from agreement scoring. A forced
guess adds noise.

## 4. Annotator qualification

Record for each annotator: degree and field, relevant research experience,
familiarity with cancer genomics, and whether they have seen any part of this
corpus before. Report this in the paper. Two annotators is the minimum and is a
stated limitation; a third would materially strengthen it.

**Neither annotator may be the person who developed the verifier**, for the
final set. This is a conflict, not a formality.

## 5. Outputs

- Cohen's κ with confidence interval, per category.
- Verifier precision, recall and F1 against the human labels.
- Calibration: verifier agreement as a function of the Open Targets score, which
  is what would justify any threshold other than zero.
- Disagreement analysis: which claim types the verifier systematically misses.

## 6. Ethics determination request

**To:** KFUPM research ethics committee (or the delegated departmental
authority)

**Subject:** Determination request — expert annotation of machine-generated text

We ask whether the following requires ethics review, and if so under which
route.

**Activity.** Two researchers read machine-generated explanatory sentences about
cancer genomics and judge whether each asserted gene–disease link is supported
by published literature. Judgements are recorded through a local web page.

**Human subjects.** None are enrolled. The annotators are members of the research
team acting as domain experts, not as participants: we collect their *technical
judgements*, not data about them. No personal data beyond name, role and stated
expertise is recorded, and those are published as author-level qualifications.

**Patient data.** The underlying samples are de-identified TCGA records already
public under the TCGA data-use policy. Annotators see only gene symbols and
generated sentences — no barcodes, no clinical variables, no re-identifiable
information.

**Specific questions.**

1. Does expert annotation by team members constitute human-subjects research
   here, or is it methodological assessment outside that scope?
2. If external annotators are recruited later, does that change the
   determination?
3. Is consent documentation required for annotators' expertise being published?

We will not begin the final annotation until we have a determination in writing.
The pilot involves the same activity at smaller scale; please advise whether it
too should wait.

Contact: Abdullah M. Bishara (g202415520@kfupm.edu.sa), Dr Azzam Alfarraj
(azzam@kfupm.edu.sa).

---

## 7. What this does not settle

Even completed, this validates the verifier against **two readers on one
cohort**. It does not establish clinical correctness, and the paper should not
claim it does. It replaces "we assume the knowledge base is right" with "we
measured how often it agrees with domain readers, and report where it does not."
