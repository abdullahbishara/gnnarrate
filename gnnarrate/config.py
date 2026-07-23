"""Entry-point helpers: load a local .env and make stdout Unicode-safe.

Call these from CLI mains and app setup -- NOT at package import time, so importing
the library never reads a .env and tests stay hermetic.
"""

from __future__ import annotations

import sys


def load_env() -> None:
    """Populate os.environ from a local .env, if python-dotenv is installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def use_utf8_stdout() -> None:
    """Let stdout print non-ASCII (arrows, etc.) on Windows cp1252 consoles."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
