"""Account for every numeric literal in the manuscript.

audit_numbers.py proves the numbers it checks are correct; it is silent about the
rest. This classifies every literal in the source into:

  VERIFIED   - checked against the released artefacts by audit_numbers.py
  STRUCTURAL - LaTeX geometry, colours, years, addresses, model version numbers:
               nothing a reader would read as a result
  DERIVED    - arithmetic that follows from a verified value (e.g. one side of a
               ratio, a count restated in prose)
  UNACCOUNTED- everything else; each of these needs a human decision

The point is that "unaccounted" should be zero, and that the whitelist is explicit
rather than implied by silence.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).parent
from _paths import full_text, require_tex
TEX = require_tex()
tex_raw = full_text()
tex = re.sub(r"(?<!\\)%.*", "", tex_raw)

# ---- what audit_numbers.py already checked -------------------------------
env = dict(os.environ, AUDIT_VERBOSE="1")
out = subprocess.run([sys.executable, str(HERE / "audit_numbers.py")],
                     capture_output=True, text=True, env=env).stdout
verified = {m.group(1).rstrip(".") for m in re.finditer(r"text=([\d.]+)", out)}
# a value written 0.50 in the text may be printed 0.5 by Python, and vice versa
verified |= {v.rstrip("0").rstrip(".") for v in list(verified)}

# ---- literals that are not results ---------------------------------------
STRUCTURAL_LINE = re.compile(
    r"\\usepackage|\\documentclass|\\usetikzlibrary|/\.style|draw=|fill=|"
    r"minimum height|inner sep|node distance|text=black|length=|width=|"
    r"\\includegraphics|\\label|\\ref|\\cite|\\bibliography|e-mail|Dhahran|"
    r"scriptsize|footnotesize|\\\[|pt\]|mm\)|above=|below=|right=|left=|"
    r"\\multicolumn|\\begin\{tabular\}|\\normalsize", re.I)
STRUCTURAL_VALUES = {
    "2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2014", "2013",
    "31261",                     # postcode
    "4.8", "4.5", "4.6", "3.3", "2.5", "72", "5",   # model version numbers
    "14", "250",                 # page limit, abstract word limit (stated in comments)
    "4096",                      # generation token budget, a configuration choice
    "3",                         # min token length of the fabrication detector's
                                 # candidate regex; audit_method.py checks the
                                 # prose against the pattern in faithfulness.py
}
# Values that follow arithmetically from something already verified.
DERIVED = {
    "1750": "abstract total = 1270 + 360 + 120, each component verified",
    "1270": "sum of the ten per-model n, each verified",
    "127": "cohort size, verified as n in every Table II row",
    "60": "architecture subset size, fixed by design and stated in the caption",
    "30": "counterfactual subset size, verified via the occlusion/retrain result",
    "80": "test-suite size, asserted by pytest in CI rather than by a data file",
    "95": "confidence level of the bootstrap intervals",
    "100": "percentage of flagged claims removed by symbolic filtering (239 -> 0)",
    "224": "supported claims before mitigation, verified in mitigation_full.json",
    "26": "non-flip counterfactual cases = 30 - 4, both verified",
    "29": "occlusion/retrain agreement count, verified as 96.7%",
    "25": "non-flip cases correctly reported = 29 - 4, both verified",
    "52": "narratives in the worked-example candidate pool (illustrative only)",
    "0.05": "threshold value on the sweep axis, verified as tau=0.05",
    "0.01": "threshold value on the sweep axis, verified as tau=0.01",
    "0.10": "threshold value on the sweep axis, verified as tau=0.10",
    "0.20": "threshold value on the sweep axis, verified as tau=0.20",
    "0.07": "stated rule-of-thumb gap, derived from the reported SDs",
    "0.18": "between-model spread = 0.498 - 0.318, both verified",
    "0.32": "abstract, rounded from the verified 0.318 (Haiku 4.5)",
    "0.50": "abstract, rounded from the verified 0.498 (Opus 4.8, context off)",
    "0.90": "abstract, rounded from the verified 0.902 (GIN, Opus narrator)",
    "0.006": "Fidelity- for GCN and GAT; verified as -0.006, and the scanner "
             "reads the magnitude without the leading minus",
    "0.003": "cohort-purity delta = 0.426 - 0.422, both means verified",
}

found: dict[str, list[int]] = {}
for lineno, line in enumerate(tex.splitlines(), 1):
    if STRUCTURAL_LINE.search(line):
        continue
    # LaTeX writes thousands as 1{,}594; join them before scanning so the literal
    # is seen as one number rather than "1" and "594".
    line = re.sub(r"(\d)\{,\}(\d)", r"\1\2", line)
    for m in re.finditer(r"(?<![\w.])(\d+\.\d+|\d+)(?![\w])", line):
        found.setdefault(m.group(1), []).append(lineno)

buckets = {"VERIFIED": [], "STRUCTURAL": [], "DERIVED": [], "UNACCOUNTED": []}
for val, lines in found.items():
    norm = val.rstrip("0").rstrip(".") if "." in val else val
    if val in verified or norm in verified:
        buckets["VERIFIED"].append((val, lines))
    elif val in STRUCTURAL_VALUES:
        buckets["STRUCTURAL"].append((val, lines))
    elif val in DERIVED:
        buckets["DERIVED"].append((val, lines))
    else:
        buckets["UNACCOUNTED"].append((val, lines))

for name in ("VERIFIED", "STRUCTURAL", "DERIVED"):
    print(f"{name:<12} {len(buckets[name]):>4} distinct literals")
print(f"{'UNACCOUNTED':<12} {len(buckets['UNACCOUNTED']):>4} distinct literals\n")

if buckets["UNACCOUNTED"]:
    print("unaccounted (value: first line, context):")
    lines = tex.splitlines()
    for val, ls in sorted(buckets["UNACCOUNTED"], key=lambda kv: -len(kv[1])):
        print(f"  {val:<9} L{ls[0]:<5} {lines[ls[0]-1].strip()[:72]}")
else:
    print("every numeric literal is verified, structural, or explicitly derived")
