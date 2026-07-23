"""Load environment variables from a local .env for entry points.

Call this from CLI mains and app setup -- NOT at package import time, so importing
the library never reads a .env and tests stay hermetic. If python-dotenv isn't
installed, this is a no-op and keys must come from the real environment.
"""

from __future__ import annotations


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()
