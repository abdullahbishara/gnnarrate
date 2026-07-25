"""Word count per section, to target compression where the bulk actually is."""

import pathlib
import re

from _paths import require_tex
t = require_tex().read_text(encoding="utf-8")
t = re.sub(r"(?<!\\)%.*", "", t)
body = t.split(r"\begin{abstract}", 1)[-1].split(r"\bibliographystyle", 1)[0]

# Split on section/subsection headings, keeping the heading text.
parts = re.split(r"\\(sub)?section\*?\{([^}]*)\}", body)
# parts: [pre, sub?, title, content, sub?, title, content, ...]
rows, i = [], 1
pre = parts[0]
while i + 2 < len(parts) + 1 and i + 2 <= len(parts):
    is_sub, title, content = parts[i], parts[i + 1], parts[i + 2] if i + 2 < len(parts) else ""
    c = re.sub(r"\\begin\{tabular\}.*?\\end\{tabular\}", " ", content, flags=re.S)
    c = re.sub(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", " ", c, flags=re.S)
    c = re.sub(r"\\[a-zA-Z]+\*?", " ", c)
    c = re.sub(r"[{}$&\\_^~]", " ", c)
    w = len(re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", c))
    rows.append(("  " if is_sub else "", title.strip(), w))
    i += 3

total = sum(r[2] for r in rows)
for indent, title, w in rows:
    bar = "#" * (w // 40)
    print(f"{indent}{title[:44]:<46}{w:>6}  {bar}")
print(f"\n{'TOTAL':<46}{total:>6}")

n_tab = len(re.findall(r"\\begin\{table", body))
n_fig = len(re.findall(r"\\begin\{figure", body))
print(f"\nfloats: {n_tab} tables, {n_fig} figures "
      f"(~{n_tab*0.33 + n_fig*0.45:.1f} column-pages)")
