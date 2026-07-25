"""Locate the manuscript and the artefacts the audits read.

The audits verify a manuscript that lives outside this repository, so the paths
are resolved here rather than hard-coded in each script. Every one can be
overridden by an environment variable, and each falls back to the layout used
during development.

    GNNARRATE_PAPER      directory holding submission/main.tex
    GNNARRATE_PLATFORM   the CLARUS platform checkout (optional; only the cohort
                         size check needs it, and that check is skipped if absent)
"""

from __future__ import annotations

import os
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent

#: This repository's package source and generated artefacts.
PACKAGE = REPO / "gnnarrate"
DATA = REPO / "data"
RESULTS = DATA / "results_comparison"

#: The manuscript. Defaults to a sibling ``gnnarrate-paper`` checkout.
PAPER = pathlib.Path(os.environ.get("GNNARRATE_PAPER", REPO.parent / "gnnarrate-paper"))
TEX = PAPER / "submission" / "main.tex"
#: Detail tables live in a separate document so they do not count against the
#: page limit. Content checks must read both; the page estimate must not.
SUPP = PAPER / "submission" / "supplementary.tex"
FIGURES = PAPER / "submission" / "figures"


def full_text() -> str:
    """Manuscript plus supplementary, for checks that follow a table anywhere."""
    text = TEX.read_text(encoding="utf-8")
    if SUPP.exists():
        text += "\n" + SUPP.read_text(encoding="utf-8")
    return text

#: The CLARUS platform, used only to confirm the cohort size quoted in the paper.
_platform = os.environ.get("GNNARRATE_PLATFORM")
PLATFORM = pathlib.Path(_platform) if _platform else None
KIRC_PICKLE = (
    PLATFORM / "data/output/KIRC_RANDOM/kirc_random_pytorch/kirc_random_nodes_ui_pytorch.pkl"
    if PLATFORM else None
)


def require_tex() -> pathlib.Path:
    """Return the manuscript path, with a useful message when it is missing."""
    if not TEX.exists():
        raise SystemExit(
            f"manuscript not found at {TEX}\n"
            f"set GNNARRATE_PAPER to the directory containing submission/main.tex"
        )
    return TEX
