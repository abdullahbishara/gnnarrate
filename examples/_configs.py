"""The set of configurations the manuscript reports, defined once.

This exists because the rule was previously enforced in one place only.
``analyze_comparison.py`` excluded the length-control variants when it built the
per-model table, but the hedging, census, emphasis and threshold analyses each
globbed every directory under ``data/experiments`` and silently pooled those
variants back in. Their aggregates therefore described a population the paper
never defines, and the totals could not be reproduced from the published table.

Any analysis whose output reaches the manuscript should select its inputs from
here, so that adding an exploratory run cannot quietly move a published number.
"""

from __future__ import annotations

import pathlib

# Length-control variants: generated to test whether instructing a model to be
# brief improves grounding. They are a smaller corpus than the reported runs, so
# pooling them also skews any per-narrative rate.
VARIANTS = frozenset({"opus_terse", "kimi_terse"})


def reported_dirs(exp: pathlib.Path) -> list[pathlib.Path]:
    """Experiment directories the manuscript reports, sorted by name."""
    return sorted(d for d in exp.glob("*")
                  if d.is_dir()
                  and d.name not in VARIANTS
                  and any(d.glob("narrative_*.txt")))
