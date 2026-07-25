"""Check the manuscript against IEEE JBHI submission requirements."""

import pathlib
import re

from _paths import require_tex
t = require_tex().read_text(encoding="utf-8")
t_nc = re.sub(r"(?<!\\)%.*", "", t)

print("=== JBHI checks ===\n")

# Abstract: max 250 words, no abbreviations/footnotes/equations
m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", t_nc, re.S)
abs_txt = re.sub(r"\\[a-zA-Z]+\*?", " ", m.group(1))
abs_txt = re.sub(r"[{}$\\]", " ", abs_txt)
words = re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", abs_txt)
print(f"Abstract: {len(words)} words  (limit 250)  "
      f"{'OK' if len(words) <= 250 else 'OVER LIMIT'}")
if re.search(r"\$", m.group(1)):
    print("  WARNING: abstract contains math ($...$) -- JBHI disallows equations")
if re.search(r"\\footnote", m.group(1)):
    print("  WARNING: abstract contains a footnote -- JBHI disallows")

# Document class
dc = re.search(r"\\documentclass\[([^\]]*)\]\{(\w+)\}", t_nc)
print(f"\nClass: {dc.group(2)} [{dc.group(1)}]  "
      f"{'OK' if dc.group(2)=='IEEEtran' and 'journal' in dc.group(1) else 'CHECK'}")

# Keywords
print(f"IEEEkeywords block: {'present' if 'IEEEkeywords' in t_nc else 'MISSING'}")
print(f"IEEEPARstart (first-para drop cap): "
      f"{'present' if 'IEEEPARstart' in t_nc else 'MISSING'}")

# ORCIDs. A transposed digit names the wrong person and looks fine, so verify
# the ISO 7064 MOD 11-2 check digit rather than only the presence of the field.
orcids = re.findall(r"ORCID:\s*(\d{4}-\d{4}-\d{4}-\d{3}[\dXx])", t_nc)
pending = len(re.findall(r"ORCID:\s*TODO", t_nc))


def _orcid_ok(o: str) -> bool:
    d = o.replace("-", "")
    total = 0
    for ch in d[:15]:
        total = (total + int(ch)) * 2
    expect = (12 - total % 11) % 11
    return ("X" if expect == 10 else str(expect)) == d[15].upper()


print("\nORCIDs in author block:")
if not orcids and not pending:
    print("  MISSING -- JBHI requires ORCID for all authors")
for o in orcids:
    print(f"  {o}  {'valid check digit' if _orcid_ok(o) else 'INVALID CHECK DIGIT'}")
if pending:
    print(f"  {pending} still a TODO placeholder -- supply before submitting")

# Floats
print(f"\nFigures: {len(re.findall(r'begin\{figure', t_nc))}  "
      f"Tables: {len(re.findall(r'begin.table', t_nc))}")

# Length estimate
body = t_nc.split(r"\begin{abstract}", 1)[-1].split(r"\bibliographystyle", 1)[0]
body = re.sub(r"\\begin\{tabular\}.*?\\end\{tabular\}", " ", body, flags=re.S)
body = re.sub(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", " ", body, flags=re.S)
body = re.sub(r"\\[a-zA-Z]+\*?", " ", body)
body = re.sub(r"[{}$&\\_^~]", " ", body)
bw = len(re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", body))
# IEEEtran two-column ~ 950-1000 words/page of pure prose
prose_pages = bw / 975
float_pages = 6 * 0.33 + 3 * 0.45      # tables ~1/3 col-page, figures ~0.45
refs_pages = 28 / 45                    # ~45 refs per page
est = prose_pages + float_pages + refs_pages
print(f"\nLength estimate: ~{bw} body words")
print(f"  prose ~{prose_pages:.1f}pp + floats ~{float_pages:.1f}pp + refs ~{refs_pages:.1f}pp")
print(f"  ESTIMATE ~{est:.0f} pages  (limit 14)")
print(f"\n  NOTE: JBHI charges mandatory overlength fees above 8 pages:")
over = max(0, est - 8)
fee = 0
if est > 8:
    p910 = min(2, est - 8); fee += p910 * 250
    if est > 10: fee += (est - 10) * 350
print(f"  at ~{est:.0f} pages the mandatory charge is roughly ${fee:,.0f}")
