"""Find LaTeX commands mangled by Python escape interpretation.

Editing a .tex file through a non-raw Python string, or through a shell heredoc,
turns the backslash of a command into a control character: ``\\ref`` becomes
CR + ``ef``, ``\\begin`` becomes BACKSPACE + ``egin``, ``\\frac`` becomes
FORMFEED + ``rac``. The surviving letters read as ordinary words, so the damage
survives proofreading, but the document will not compile.

Most of these control characters have no legitimate place in LaTeX source at all,
so their mere presence is the finding. Tab and newline are legitimate, so those
are matched against the command names they would have eaten.
"""

from __future__ import annotations

import re
import sys

from _paths import require_tex

path = require_tex()
raw = path.read_text(encoding="utf-8", newline="")
problems: list[str] = []

NAMES = {"\r": "\\r", "\t": "\\t", "\b": "\\b", "\f": "\\f",
         "\a": "\\a", "\v": "\\v", "\x00": "\\0"}

# These never belong in a .tex file. Their presence is itself the bug, whatever
# follows them.
ALWAYS_WRONG = ["\r", "\b", "\f", "\a", "\v", "\x00"]

# Tab and newline are legitimate, so only flag them where they sit immediately
# before the tail of a command whose backslash they would have replaced.
SUSPECT_TAILS = {
    "\t": ["extbf", "extit", "extsc", "extrm", "ext", "op", "imes", "abular",
           "ableofcontents", "extwidth", "hanks", "itle"],
    "\n": ["ewcommand", "ewpage", "ewline", "oindent", "ormalsize", "umber",
           "ewtheorem", "otag"],
}


def report(idx: int, label: str, ctrl: str) -> None:
    line = raw[:idx].count("\n") + 1
    ctx = raw[max(0, idx - 50):idx + 30]
    for c, n in NAMES.items():
        ctx = ctx.replace(c, f"<{n}>")
    problems.append(f"L{line}: {label}\n      ...{ctx.strip()}...")


for ctrl in ALWAYS_WRONG:
    # On Windows the file is stored CRLF, so a CR that introduces a newline is
    # normal. Only a CR standing on its own is the signature of an eaten "\r".
    pat = "\r(?!\n)" if ctrl == "\r" else re.escape(ctrl)
    for m in re.finditer(pat, raw):
        tail = re.match(r"[a-zA-Z]+", raw[m.end():])
        guess = f" -- looks like '\\{tail.group(0)}'" if tail else ""
        report(m.start(), f"control character {NAMES[ctrl]} in LaTeX source{guess}",
               ctrl)

for ctrl, tails in SUSPECT_TAILS.items():
    for t in tails:
        for m in re.finditer(re.escape(ctrl) + t + r"\b", raw):
            report(m.start(),
                   f"{NAMES.get(ctrl, ctrl)!r}+'{t}' -- should be '\\{t}'", ctrl)

# Healed damage. Once a mangled file is read with universal newlines and written
# back in text mode, a lone CR is silently promoted to a real line break: the
# control character disappears but the command stays destroyed, and the tail is
# left stranded at the start of a line. That stranded tail is the only evidence
# remaining, so match it directly.
TAILS = ["ef", "egin", "nd", "rac", "extbf", "extit", "ext", "ootnote", "ewline",
         "ewcommand", "oindent", "ightarrow", "ormalsize", "efeq", "abel", "ite"]
for m in re.finditer(r"(?m)^(" + "|".join(TAILS) + r")(?=[{\[])", raw):
    report(m.start(), f"line starts with '{m.group(1)}' -- a healed '\\{m.group(1)}'"
                      " whose backslash was eaten by an escape", "")

print(f"escape damage: {len(problems)} problem(s)\n")
for p in problems:
    print("  - " + p)
if not problems:
    print("  no mangled LaTeX commands found")
sys.exit(1 if problems else 0)
