"""Pre-compile validator for the manuscript.

Catches the errors that cost an Overleaf compile cycle (missing citations,
dangling refs, unbalanced environments) and flags leftover placeholders that must
not reach a reviewer.

    python check_manuscript.py
"""

from __future__ import annotations

import pathlib
import re
import sys

from _paths import DATA, RESULTS as RES, require_tex
TEX = require_tex()
from _paths import PAPER
BIB = PAPER / "submission" / "references.bib"


def strip_comments(text: str) -> str:
    """Remove % comments (but keep \\%)."""
    return re.sub(r"(?<!\\)%.*", "", text)


def main() -> int:
    tex = strip_comments(TEX.read_text(encoding="utf-8"))
    bib = BIB.read_text(encoding="utf-8")
    problems: list[str] = []

    # --- citations resolve ---
    bib_keys = set(re.findall(r"@\w+\s*\{\s*([^,\s]+)", bib))
    cited: set[str] = set()
    for group in re.findall(r"\\cite[tp]?\*?(?:\[[^\]]*\])*\{([^}]*)\}", tex):
        cited.update(k.strip() for k in group.split(",") if k.strip())
    missing = sorted(cited - bib_keys)
    if missing:
        problems.append(f"CITED BUT NOT IN .bib ({len(missing)}): {', '.join(missing)}")
    unused = sorted(bib_keys - cited)

    # --- refs resolve ---
    labels = set(re.findall(r"\\label\{([^}]*)\}", tex))
    refs: set[str] = set()
    for group in re.findall(r"\\(?:eq|c|C)?ref\{([^}]*)\}", tex):
        refs.update(k.strip() for k in group.split(",") if k.strip())
    dangling = sorted(refs - labels)
    if dangling:
        problems.append(f"REF WITHOUT LABEL ({len(dangling)}): {', '.join(dangling)}")

    # --- environments balance ---
    begins = re.findall(r"\\begin\{([^}*]+)\*?\}", tex)
    ends = re.findall(r"\\end\{([^}*]+)\*?\}", tex)
    for env in set(begins) | set(ends):
        if begins.count(env) != ends.count(env):
            problems.append(
                f"UNBALANCED ENV '{env}': {begins.count(env)} begin, {ends.count(env)} end"
            )

    # --- braces balance (rough) ---
    depth = 0
    for ch in re.sub(r"\\[{}]", "", tex):
        depth += (ch == "{") - (ch == "}")
    if depth != 0:
        problems.append(f"BRACE IMBALANCE: net {depth:+d}")

    # --- placeholders ---
    # Blocking only if they survive comment-stripping, i.e. they reach the PDF.
    # Ones inside % comments are listed separately as remaining work.
    raw = TEX.read_text(encoding="utf-8")
    patterns = [
        (r"\bTODO\b", "TODO"),
        (r"\bTBD\b", "TBD"),
        (r"\bXXX\b", "XXX"),
        (r"\bFIXME\b", "FIXME"),
        (r"\?\?\?", "???"),
        (r"\[To be completed[^\]]*\]", "to-be-completed text"),
    ]
    pending = 0
    for pat, name in patterns:
        visible = re.findall(pat, tex)
        if visible:
            problems.append(f"PLACEHOLDER IN OUTPUT: {name} x{len(visible)}")
        pending += len(re.findall(pat, raw)) - len(visible)
    if pending:
        print(f"note: {pending} placeholder marker(s) in LaTeX comments "
              f"(not printed; tracked work)\n")

    # --- report ---
    print(f"citations: {len(cited)} cited, {len(bib_keys)} in .bib, {len(unused)} unused")
    print(f"labels:    {len(labels)} defined, {len(refs)} referenced")
    print(f"envs:      {len(set(begins))} distinct")
    if unused:
        print(f"  (unused bib entries, harmless: {', '.join(unused[:8])}"
              f"{'...' if len(unused) > 8 else ''})")
    print()

    if problems:
        print("PROBLEMS:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("OK - no blocking problems found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
