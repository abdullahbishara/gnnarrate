# GNNarrate

**LLM-generated narratives for graph neural network explanations in precision medicine.**

Explainable AI methods for GNNs produce numbers: relevance scores per node and per
edge, confidence deltas after a graph edit, confusion-matrix counts before and after
retraining. Those numbers are correct and largely unreadable to the clinicians and
biologists who are supposed to act on them.

GNNarrate is a narration layer. It takes the raw explanation log emitted by
[CLARUS](https://github.com/asaranti/GNN_Counterfactuals) and asks a large language
model to turn it into a two-part account for each patient: a short plain-language
summary, and a longer causal explanation that says not just *which* genes and
interactions mattered but *how* each one pushed the model toward its prediction —
including what it means when removing a single node flips the outcome.

> **This repository is an extension, not a fork.** It contains only the narration
> layer. The GNN training, counterfactual machinery, attribution methods, and web
> interface all belong to CLARUS, which you install separately. See
> [Relationship to CLARUS](#relationship-to-clarus).

---

## Example

Given a CLARUS log in which node `MGAT3` is deleted and the prediction flips:

```
Patient Information: True label = 1, Predicted label = 0, confidence = -0.36
Node MGAT3: 0.87
Node MGAT4B: 0.86
...
Node deleted: MGAT3
Patient Information: True label = 1, Predicted label = 1, confidence = 1.53
```

GNNarrate produces:

> **Patient 1 — Summary.** The model initially misclassified this patient, predicting
> class 0 with low confidence (−0.36) despite a true label of 1. Removing a single
> gene from the network corrected the prediction.
>
> **Patient 1 — Explanation.** Two genes dominated the original decision: MGAT3 and
> MGAT4B, with near-identical relevance (0.87 and 0.86). The attribution methods
> disagreed sharply on the MGAT3–MGAT4B edge — Integrated Gradients scored it 0.01
> while Saliency scored it 0.80 — suggesting the model's reliance on that connection
> was unstable rather than robust. When MGAT3 was removed, the prediction flipped to
> the correct class with high confidence (1.53), which identifies MGAT3 as actively
> misleading rather than merely uninformative for this patient…

Reproduce it:

```bash
python examples/explain_from_log.py examples/sample_clarus_log.txt
```

Add `--dry-run` to print the constructed prompt without calling an API (no key needed).

---

## Installation

```bash
git clone https://github.com/abdullahbishara/gnnarrate.git
cd gnnarrate
pip install -e .
```

Then provide an API key:

```bash
cp .env.example .env      # then edit .env
# or:
export ANTHROPIC_API_KEY=sk-ant-...
```

Anthropic (Claude Opus 4.8) is the default provider; OpenAI and Groq are
supported via `--provider openai` / `--provider groq`.

---

## Usage

### As a library

```python
from gnnarrate import generate_gnn_explanation_prompt, explain_model_prediction

prompt = generate_gnn_explanation_prompt(
    log_text=open("clarus_log.txt").read(),
    dataset_name="KIRC SubNet",
    max_sentences=8,
    verbose=True,
)
print(explain_model_prediction(prompt))
```

`generate_gnn_explanation_prompt` accepts flags to control what the model is asked
for — `biomedical_context`, `interpretability_focus`, `include_model_metrics`, and
`verbose` each add a corresponding instruction block. All are on by default except
`verbose`.

### As a Flask blueprint on an existing CLARUS instance

Two lines in the CLARUS `app.py`, with no changes to its own routes:

```python
from gnnarrate import llm_blueprint
app.register_blueprint(llm_blueprint)
```

This adds `POST /llm_prediction`:

```bash
curl -X POST http://localhost:5000/llm_prediction \
     -H 'Content-Type: application/json' \
     -d '{"llm": "<contents of a CLARUS log>"}'
```

```json
{ "explanation": "Patient 1 — Summary. …" }
```

---

## Evaluation pipeline

Beyond generating explanations, GNNarrate scores whether they can be trusted --
the core of the research contribution. Three tiers, each independently usable:

**Tier 1 — structural faithfulness** (`gnnarrate.faithfulness`). Is the narrative
faithful to the attribution log? Measures recall of the top-ranked genes, flags
genes it invents (closed-vocabulary), and checks whether it reports each
counterfactual edit's outcome correctly. Fully automatic, no external data.

```bash
python examples/score_faithfulness.py examples/sample_clarus_log.txt --demo
```

**Tier 2 — gene-disease grounding** (`gnnarrate.grounding`). When the narrative
claims a gene is linked to the patient's disease, is that supported by a
knowledge base? Since the disease is fixed per dataset, this is a lookup against
Open Targets association scores. Fetch once and cache:

```python
from gnnarrate.opentargets import search_disease, fetch_open_targets_associations
search_disease("clear cell renal carcinoma")          # -> [(MONDO id, name), ...]
assoc = fetch_open_targets_associations("MONDO_0005005")
assoc.to_tsv("data/kirc_open_targets.tsv")            # reuse offline
```

Gene Ontology encodes gene *function*, not disease links, which is why grounding
uses a gene-disease knowledge base. Knowledge bases are incomplete, so an
unsupported claim is reported as a hallucination *candidate*, never a verdict.

**Tier 3 — benchmark and mitigation** (`gnnarrate.benchmark`,
`gnnarrate.mitigation`). Score a corpus across models and prompt variants into
CSV tables, and run the mitigation loop -- feed unsupported claims back to the
model to revise, then measure the before/after drop in hallucinations.

```bash
python examples/run_benchmark.py --demo          # offline, no key
python examples/run_benchmark.py \
    --logs data/clarus_logs --associations data/kirc_open_targets.tsv \
    --disease "clear cell renal carcinoma" --models claude-opus-4-8
```

The claim-extraction and counterfactual-direction checks are documented lexical
heuristics, intended to be corroborated by a small expert validation rather than
treated as ground truth.

## Relationship to CLARUS

CLARUS is an interactive explainable-AI platform for manual counterfactuals in graph
neural networks, developed by Metsch, Saranti, Angerschmid, Pfeifer, Klemt, Holzinger,
and Hauschild, and published in the *Journal of Biomedical Informatics*. It provides
the GNN architectures, the counterfactual graph-editing workflow, the attribution
methods (GNNExplainer, Integrated Gradients, Saliency), the retraining pipeline, and
the R Shiny frontend.

- Python backend: <https://github.com/asaranti/GNN_Counterfactuals>
- R Shiny frontend: <https://github.com/JacquelineBeinecke/xAI-Shiny-App>
- Paper: <https://www.sciencedirect.com/science/article/pii/S1532046424000182>
- Hosted instance: <https://rshiny.gwdg.de/apps/clarus/>

**None of that code is redistributed here.** GNNarrate consumes CLARUS's log output
and nothing else; it treats CLARUS as an upstream system and depends on it only
through that text format. If you use GNNarrate, please cite the CLARUS paper
alongside this repository — the underlying explanations are theirs.

At the time of writing, the CLARUS repositories carry no license file. Check with
their authors before redistributing or building on that code directly.

---

## What is and isn't in scope

GNNarrate does the narration and nothing else:

| In scope | Out of scope (belongs to CLARUS) |
|---|---|
| Prompt construction from CLARUS logs | GNN training and retraining |
| Multi-patient log narration | Attribution methods |
| OpenAI / Groq client handling | Counterfactual graph editing |
| Flask blueprint for integration | Datasets and preprocessing |

**Limitations.** LLM output is not verified against the source log — the model can
misread a relevance score or overstate a biomedical link. Explanations are intended
as a readable entry point to the underlying attribution data, not as a substitute for
it, and not as clinical decision support. Any biomedical claim in the generated text
should be checked against the literature before it is relied on.

---

## Development

```bash
pip install -e ".[dev]"
pytest
```

Tests cover prompt construction and require no API key.

---

## Citation

If GNNarrate is useful in your work, please cite both this repository and CLARUS.
Machine-readable metadata is in [`CITATION.cff`](CITATION.cff).

```bibtex
@software{bishara_gnnarrate,
  author  = {Bishara, Abdullah M.},
  title   = {GNNarrate: LLM-generated narratives for graph neural network
             explanations in precision medicine},
  year    = {2026},
  url     = {https://github.com/abdullahbishara/gnnarrate}
}

@article{metsch2024clarus,
  author  = {Metsch, Jacqueline Michelle and Saranti, Anna and
             Angerschmid, Alessa and Pfeifer, Bastian and Klemt, Vanessa and
             Holzinger, Andreas and Hauschild, Anne-Christin},
  title   = {{CLARUS}: An interactive explainable {AI} platform for manual
             counterfactuals in graph neural networks},
  journal = {Journal of Biomedical Informatics},
  year    = {2024},
  url     = {https://www.sciencedirect.com/science/article/pii/S1532046424000182}
}
```

---

## License

[MIT](LICENSE) — covers the code in this repository only. CLARUS is separately
licensed by its authors.
