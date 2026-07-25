"""Integrity audit of every generated artefact.

Checks the failure modes that silently corrupt results: empty or truncated
narratives, logs that do not parse, derived files older than the narratives they
summarise, and corpora that are incomplete without saying so.

    python examples/audit_artefacts.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from gnnarrate.clarus_log import parse_clarus_log

DATA = pathlib.Path("data")
TERMINAL = tuple(".!?\"')*]:0123456789%")
problems: list[str] = []


def newest(p: pathlib.Path, pattern="*") -> float:
    files = list(p.glob(pattern))
    return max((f.stat().st_mtime for f in files), default=0.0)


print("=== narrative corpora ===")
corpora = [("experiments", 127), ("results_arch", 60)]
for root, target in corpora:
    base = DATA / root
    if not base.exists():
        continue
    for d in sorted(x for x in base.iterdir() if x.is_dir()):
        files = sorted(d.glob("narrative_*.txt"))
        if not files:
            continue
        empty = [f.name for f in files if not f.read_text(encoding="utf-8").strip()]
        short = [f.name for f in files
                 if 0 < len(f.read_text(encoding="utf-8").strip()) < 200]
        cut = [f.name for f in files
               if f.read_text(encoding="utf-8").rstrip()[-1:] not in TERMINAL]
        flag = ""
        if empty:
            problems.append(f"{d.name}: {len(empty)} EMPTY narratives"); flag += " EMPTY"
        if short:
            problems.append(f"{d.name}: {len(short)} suspiciously short"); flag += " SHORT"
        if cut:
            flag += f" {len(cut)}?end"
        variant = d.name.endswith("_terse")
        expected = 60 if (root == "results_arch" or variant) else target
        status = "ok " if len(files) >= expected else "LOW"
        if len(files) < expected:
            problems.append(f"{d.name}: {len(files)}/{expected} narratives")
        print(f"  {status} {d.name:<18} {len(files):>4}/{expected}{flag}")

print("\n=== log corpora parse cleanly? ===")
for d in sorted(x for x in DATA.iterdir() if x.is_dir() and x.name.startswith("clarus_logs")):
    subdirs = [x for x in d.iterdir() if x.is_dir()] or [d]
    for sub in subdirs:
        logs = sorted(sub.glob("*.txt"))
        if not logs:
            continue
        bad = 0
        for f in logs:
            try:
                parse_clarus_log(f.read_text(encoding="utf-8"))
            except Exception:
                bad += 1
        label = f"{d.name}/{sub.name}" if sub is not d else d.name
        print(f"  {'ok ' if not bad else 'BAD'} {label:<30} {len(logs):>4} logs, {bad} unparseable")
        if bad:
            problems.append(f"{label}: {bad} logs fail to parse")

print("\n=== derived artefacts newer than their inputs? ===")
narr_mtime = max(newest(DATA / "experiments" / d, "narrative_*.txt")
                 for d in ("opus_default", "opus5", "glm", "qwen"))
derived = ["results_comparison/per_model.csv", "results_comparison/hedging.json",
           "results_comparison/threshold_sensitivity.json",
           "results_comparison/claim_census.json", "results_comparison/emphasis.json",
           "results_comparison/interaction.json",
           "results_comparison/modality_language.json"]
figs = pathlib.Path("../gnnarrate-paper/submission/figures")
derived_paths = [DATA / d for d in derived] + list(figs.glob("*.pdf"))
for f in derived_paths:
    if not f.exists():
        problems.append(f"{f.name}: MISSING"); print(f"  MISSING {f.name}"); continue
    stale = f.stat().st_mtime < narr_mtime
    if stale:
        problems.append(f"{f.name}: STALE (older than the narratives)")
    print(f"  {'STALE' if stale else 'ok   '} {f.name}")

print("\n" + ("=" * 46))
if problems:
    print(f"{len(problems)} PROBLEM(S):")
    for p in problems:
        print(f"  - {p}")
else:
    print("no integrity problems found")
