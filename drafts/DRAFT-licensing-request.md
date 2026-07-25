# DRAFT — not sent

Two documents. **Neither is to be sent until reviewed**, and the institutional
request (B) should go first, because its answer determines whether A is even the
right ask.

---

## A. Draft letter to the CLARUS authors

**To:** Anna Saranti; Andreas Holzinger (HCI-KDD), cc Jacqueline Metsch
**Subject:** Permission request — redistribution of GNN_Counterfactuals-derived code

Dear Dr Saranti and Prof. Holzinger,

I am a master's student at King Fahd University of Petroleum and Minerals. My
supervisor and I have built a research prototype that extends your
`GNN_Counterfactuals` backend, the platform described in Metsch et al., *CLARUS*
(J. Biomed. Informatics 150:104600, 2024). We are preparing a manuscript for the
IEEE Journal of Biomedical and Health Informatics on verifying LLM-generated
explanations of graph neural network predictions against a curated gene–disease
knowledge base.

Our work reuses parts of your repository — the training and inference pipeline,
the GNNExplainer integration and the patient-graph preprocessing — and adds a
graph attention model, edge-weight message-passing operators, a multi-architecture
harness and an audit layer.

The repository at `github.com/asaranti/GNN_Counterfactuals` carries no licence
file, so default copyright applies and we have no permission to redistribute a
derivative work. Journal policy asks us to release code sufficient to reproduce
our results, and we would rather ask than assume.

We would be grateful if you could tell us whether you are willing to permit
redistribution of a derivative of `GNN_Counterfactuals` under GPL-3.0. We need
GPL-3.0 specifically because our work also builds on GNN-SubNet, which is
GPL-3.0 licensed.

If you would prefer that we do not redistribute your code, that is entirely
understood. In that case we would release only our own modules and document
your repository as an external dependency that users obtain directly from you.
Either way, CLARUS and GNN-SubNet are cited in the manuscript, and an
attribution file records precisely which components are yours.

I would be glad to send the manuscript draft or answer any questions.

With thanks and respect for the work,

Abdullah M. Bishara — g202415520@kfupm.edu.sa — ORCID 0009-0000-3904-5503
Dr Azzam Alfarraj — azzam@kfupm.edu.sa — ORCID 0000-0002-1142-0401
Department of Data Science and Analytics / Department of Mathematics, KFUPM

---

## B. Draft request to KFUPM legal / technology transfer

**Subject:** Licence clearance request — release of derivative research software

We are preparing a research artefact for journal publication and need written
clearance before any public release. We are **not** asking you to confirm a
conclusion we have reached; we are asking for a determination.

**Situation.** Our platform is a derivative of two upstream projects:

| Component | Source | Licence | Consequence as we understand it |
|---|---|---|---|
| CLARUS / `GNN_Counterfactuals` | github.com/asaranti/GNN_Counterfactuals | **None present** | Default copyright; no automatic right to reproduce, distribute or make derivatives |
| GNN-SubNet (KIRC benchmark data, possibly code) | github.com/pievos101/GNN-SubNet | **GPL-3.0** | Copyleft obligations depending on how the code is combined |

**Evidence attached.** `PROVENANCE-MATRIX.md`, a file-level classification of
all 226 source files: 11 carry an original-authorship header, 94 carry HCI-KDD
headers, and **121 carry no header at all**. We regard the matrix as a starting
point, not a finding: a header records what an author typed, not what was copied.

**Determinations requested.**

1. Are our original modules legally separable from the CLARUS code, such that
   they may be released alone?
2. Is a clean-room reimplementation required for any component?
3. Is GNN-SubNet code incorporated into our work, or is only its data used, and
   what GPL obligation follows in each case?
4. Which GPL obligations attach to each of these candidate configurations?
   - (a) full platform including CLARUS-derived code, under GPL-3.0;
   - (b) our original modules only, with CLARUS as a documented external
     dependency;
   - (c) narration and audit layer only, with no platform code at all.

**What we will not do without your written clearance.** Publish any bundle
containing CLARUS-derived code; describe any configuration as lawful on our own
assessment; or state in the manuscript that the artefact is publicly available.

**Timing.** The manuscript is on hold and there is no external deadline. We
would rather wait for a determination than release on an assumption.

Attachments: `PROVENANCE-MATRIX.md`, `ATTRIBUTION.md`, `LICENSING_STATUS.md`,
draft letter to the upstream authors.

---

## Sequencing note

Send **B before A**. If the institution determines that configuration (c) is
sufficient for the journal and lawful without permission, then A becomes a
courtesy rather than a dependency, and the critical path shortens accordingly.
