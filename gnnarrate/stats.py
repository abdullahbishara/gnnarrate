"""Small statistics helpers for reporting benchmark results.

Bootstrap confidence intervals with no external dependency, so aggregate metrics
can be reported as mean +/- 95% CI instead of bare point estimates.
"""

from __future__ import annotations

import random
import statistics


def mean_ci(values, confidence: float = 0.95, n_boot: int = 2000, seed: int = 0):
    """Return (mean, lo, hi) via nonparametric bootstrap. None-safe.

    Filters out None. Returns (None, None, None) if nothing is left, and a
    degenerate (m, m, m) for a single value.
    """
    vals = [v for v in values if v is not None]
    if not vals:
        return (None, None, None)
    mean = statistics.fmean(vals)
    if len(vals) == 1:
        return (mean, mean, mean)

    rng = random.Random(seed)
    n = len(vals)
    boots = sorted(
        statistics.fmean(vals[rng.randrange(n)] for _ in range(n))
        for _ in range(n_boot)
    )
    lo = boots[int((1 - confidence) / 2 * n_boot)]
    hi = boots[int((1 + confidence) / 2 * n_boot)]
    return (mean, lo, hi)


def format_ci(values, digits: int = 3, **kw) -> str:
    """Human-readable 'mean [lo, hi]' string for a metric column."""
    m, lo, hi = mean_ci(values, **kw)
    if m is None:
        return "n/a"
    return f"{m:.{digits}f} [{lo:.{digits}f}, {hi:.{digits}f}]"
