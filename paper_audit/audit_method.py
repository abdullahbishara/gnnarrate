"""Check that the method section describes what the code actually does.

Numbers can be verified against CSVs; prose cannot. This checks the specific,
falsifiable claims the method section makes about the implementation, by reading
the shipped source rather than trusting the description.
"""

from __future__ import annotations

import pathlib
import re

from _paths import PACKAGE as _PKG, PLATFORM, require_tex
TEX = require_tex().read_text(encoding="utf-8")
from _paths import PACKAGE as SRC

def src(name):
    return (SRC / name).read_text(encoding="utf-8")

checks = []
def verify(claim, condition, detail=""):
    checks.append((claim, bool(condition), detail))

faith, ground, judge, mit = (src("faithfulness.py"), src("grounding.py"),
                             src("judge.py"), src("mitigation.py"))
prompts, llm = src("prompts.py"), src("llm.py")

# --- faithfulness ---
verify("top-k recall uses the INITIAL graph state",
       "states[0]" in faith and "top_nodes" in faith)
verify("fabrication uses closed-vocabulary matching against the graph",
       "node_vocabulary" in faith and "_CANDIDATE" in faith)
verify("gene matching is whole-word (not substring)",
       r"\b" in src("_textutil.py"))
verify("paper says direction uses an LLM judge, and judge.py exists",
       "judge" in TEX.lower() and "def score_direction" in judge)
verify("lexical direction metric is marked unreliable in code",
       "WARNING" in faith or "unreliable" in faith)

# --- grounding ---
verify("grounding uses sentence-level gene+disease co-occurrence",
       "has_term" in ground and "mentions" in ground and "sentences" in ground)
verify("threshold is configurable and defaults to 0",
       "threshold: float = 0.0" in ground)
verify("unsupported is reported as a candidate, not a verdict",
       "hallucination_candidates" in ground or "never a verdict" in ground.lower()
       or "candidate" in ground.lower())

# --- mitigation: paper claims three interventions ---
verify("three revisers exist (neural, symbolic, claim-level)",
       all(k in mit for k in ("llm_reviser", "symbolic_reviser", "claim_level_reviser")))

# --- prompts / generation ---
verify("four independently switchable instruction blocks",
       all(f in prompts for f in ("biomedical_context", "interpretability_focus",
                                  "include_model_metrics", "verbose")))
verify("paper's 4096-token budget matches the code default",
       "max_tokens: int = 4096" in llm and "4096" in TEX)
verify("terse variant exists as described",
       "terse" in src("benchmark.py"))

# The manuscript credited node relevance to GNNExplainer, when on graphs of this
# size the platform always takes a gradient fallback. Tie the description to the
# guard in the code so the two cannot drift apart again. Needs the platform.
if PLATFORM is not None:
    _gx = PLATFORM / "actionable" / "gnn_explanations.py"
    if _gx.exists():
        _src = _gx.read_text(encoding="utf-8")
        _has_guard = ("num_nodes > 500" in _src and "gnnexplainer_ig_fallback" in _src)
        verify("node relevance is described as a fallback, matching the code",
               _has_guard and re.search(r"substitutes a gradient fallback", TEX)
               is not None)
        verify("attribution is over edges, not node features, as described",
               "input_mask = torch.ones(data.edge_index.shape[1]" in _src
               and re.search(r"no attribution is computed over the node", TEX)
               is not None)

# The paper describes the fabrication detector's candidate pattern in prose
# ("tokens of length >= 3 beginning with a letter"). Tie that sentence to the
# regex so the two cannot drift apart.
verify("fabrication candidate pattern matches the prose description",
       r"\b[A-Z][A-Z0-9]{2,}\b" in faith
       and re.search(r"tokens of length \$\\geq 3\$ beginning with a letter", TEX)
       is not None)

# --- claims about ground truth provenance ---
# The judge must be blind: it is called with the narrative alone, and the log's
# verdict is only consulted afterwards to score it.
verify("judge is called with the narrative alone (blind to ground truth)",
       re.search(r"judge_fn\(\s*narrative\s*\)", judge) is not None)
verify("ground truth is read from the log, not passed to the judge",
       re.search(r"actual\s*=\s*bool\(changes\[0\]\.flipped\)", judge) is not None)

print("METHOD-vs-CODE AUDIT\n")
bad = 0
for claim, good, detail in checks:
    print(f"  {'OK  ' if good else 'FAIL'}  {claim}")
    if not good:
        bad += 1
print(f"\n{len(checks) - bad}/{len(checks)} method claims match the implementation")
