"""Rough body word count, to track the 14-page JBHI limit."""

import pathlib
import re

from _paths import require_tex
t = require_tex().read_text(encoding="utf-8")
t = re.sub(r"(?<!\\)%.*", "", t)                     # drop comments
body = t.split(r"\begin{abstract}", 1)[-1].split(r"\bibliographystyle", 1)[0]
body = re.sub(r"\\begin\{tabular\}.*?\\end\{tabular\}", " ", body, flags=re.S)  # drop table cells
body = re.sub(r"\\[a-zA-Z]+\*?", " ", body)          # drop commands
body = re.sub(r"[{}$&\\_^~]", " ", body)             # drop markup chars
words = re.findall(r"\b[A-Za-z][A-Za-z'\-]*\b", body)
print(f"~{len(words)} words (body, tables excluded)")
