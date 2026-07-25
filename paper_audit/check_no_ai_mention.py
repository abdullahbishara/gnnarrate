"""Confirm nothing about AI assistance appears in the rendered PDF text."""

import pathlib
import re

from _paths import require_tex
t = require_tex().read_text(encoding="utf-8")
visible = re.sub(r"(?<!\\)%.*", "", t)          # strip comments == what LaTeX prints

TERMS = ["generative ai", "ai assistant", "claude", "anthropic",
         "ai-generated", "large language model was", "chatgpt", "gpt-4"]
hits = [w for w in TERMS if w in visible.lower()]
print("AI-assistance mentions that would PRINT:", hits if hits else "NONE")

# The models under study are legitimately named in Methods -- that is science, not
# a disclosure. Show those so the distinction stays visible.
studied = sorted(set(re.findall(r"(Opus~4\.8|Sonnet~5|Haiku~4\.5|Kimi~K2|GLM-4\.6|"
                                r"DeepSeek-V3|Qwen2\.5-72B|Llama-3\.3-70B)", visible)))
print("Models named as objects of study (expected):", studied)
