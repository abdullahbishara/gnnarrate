"""Static sanity check of the TikZ figure (no LaTeX needed).

Cannot prove it compiles, but catches the mistakes that usually break it:
unbalanced delimiters, statements missing a semicolon, references to undefined
nodes, and use of a TikZ library that was not loaded.
"""

import pathlib
import re

from _paths import require_tex
t = require_tex().read_text(encoding="utf-8")

m = re.search(r"\\begin\{tikzpicture\}(.*?)\\end\{tikzpicture\}", t, re.S)
if not m:
    raise SystemExit("no tikzpicture found")
body = m.group(1)

print("delimiters:")
for name, o, c in [("braces", "{", "}"), ("brackets", "[", "]"), ("parens", "(", ")")]:
    print(f"  {name:9} net {body.count(o) - body.count(c):+d}")

# statements: every \node and \draw must end in ';'
stmts = re.findall(r"\\(?:node|draw|path)\b[^;]*;", body, re.S)
n_node = len(re.findall(r"\\node\b", body))
n_draw = len(re.findall(r"\\draw\b", body))
print(f"\nstatements: {n_node} nodes, {n_draw} draws, {len(stmts)} semicolon-terminated")
if len(stmts) < n_node + n_draw:
    print("  WARNING: a \\node or \\draw may be missing its ';'")

# node names defined vs referenced
defined = set(re.findall(r"\\node\[[^\]]*\]\s*\((\w+)\)", body))
refd = set(re.findall(r"\((\w+)(?:\.\w+)?\)", body)) | set(
    re.findall(r"of\s+(\w+)", body))
refd -= {"0", "ar"}
unknown = {r for r in refd if r not in defined and not r.isdigit()}
print(f"\nnodes defined: {sorted(defined)}")
if unknown:
    print(f"  referenced but not defined: {sorted(unknown)}")
else:
    print("  all node references resolve")

# libraries used vs loaded
loaded = set()
lm = re.search(r"\\usetikzlibrary\{([^}]*)\}", t)
if lm:
    loaded = {x.strip() for x in lm.group(1).split(",")}
needs = set()
if re.search(r"\b(above|below|left|right)=.*of\b", body):
    needs.add("positioning")
if "Stealth" in body or "{Stealth" in body:
    needs.add("arrows.meta")
if re.search(r"\$\(", body):
    needs.add("calc")
print(f"\ntikz libraries loaded: {sorted(loaded)}")
print(f"  required by this figure: {sorted(needs)}")
missing = needs - loaded
print("  MISSING: " + ", ".join(sorted(missing)) if missing else "  all required libraries loaded")
