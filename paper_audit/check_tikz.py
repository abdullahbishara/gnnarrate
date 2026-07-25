"""Static sanity check of the TikZ figure (no LaTeX needed).

Cannot prove it compiles, but catches the mistakes that usually break it:
unbalanced delimiters, statements missing a semicolon, references to undefined
nodes, and use of a TikZ library that was not loaded.
"""

import pathlib
import re

from _paths import require_tex
t = require_tex().read_text(encoding="utf-8")

#: Keys TikZ/PGF already define. Defining a node style with one of these names
#: shadows the built-in and can abort the build. `out` collides with the
#: to[out=..,in=..] path key; this check exists because that shipped unnoticed
#: until an external reviewer actually compiled the source.
RESERVED_TIKZ_KEYS = {
    "out", "in", "at", "anchor", "shift", "scale", "rotate", "pos", "sloped",
    "bend", "loop", "distance", "opacity", "name", "label",
}
_styles = set(re.findall(r"^\s*([A-Za-z@]+)\s*/\.style", t, re.M))
_clash = sorted(_styles & RESERVED_TIKZ_KEYS)
print("style names:")
if _clash:
    print(f"  RESERVED KEY REDEFINED: {', '.join(_clash)}"
          f"  -- rename; this can break the build")
else:
    print(f"  {len(_styles)} defined, none shadow a reserved TikZ key")

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

# node names defined vs referenced. Label text is scanned too unless it is
# stripped first: a label reading "$N=g(L)$" otherwise looks like a reference to
# a node called L, and the resulting warning points at a figure that is fine.
positions = re.sub(r"\$[^$]*\$", "", body)
defined = set(re.findall(r"\\node\[[^\]]*\]\s*\((\w+)\)", body))
refd = set(re.findall(r"\((\w+)(?:\.\w+)?\)", positions)) | set(
    re.findall(r"of\s+(\w+)", positions))
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
