"""Provider-agnostic LLM client for generating explanations.

Supports OpenAI and Groq. Keys are read from the environment -- never pass them
as literals, and never commit them.
"""

from __future__ import annotations

import os
from typing import Literal

Provider = Literal["openai", "groq"]

DEFAULT_MODELS: dict[Provider, str] = {
    "openai": "gpt-4o",
    "groq": "llama3-70b-8192",
}

_ENV_VARS: dict[Provider, str] = {
    "openai": "OPENAI_API_KEY",
    "groq": "GROQ_API_KEY",
}


def _build_client(provider: Provider):
    """Instantiate the SDK client for `provider`, reading its key from the env."""
    env_var = _ENV_VARS[provider]
    api_key = os.environ.get(env_var)
    if not api_key:
        raise RuntimeError(
            f"{env_var} is not set. Copy .env.example to .env and add your key, "
            f"or export {env_var} in your shell."
        )

    if provider == "openai":
        from openai import OpenAI

        return OpenAI(api_key=api_key)

    from groq import Groq

    return Groq(api_key=api_key)


def explain_model_prediction(
    prompt: str,
    provider: Provider = "openai",
    model: str | None = None,
    temperature: float = 1.0,
) -> str:
    """Send `prompt` to the configured LLM and return the explanation text.

    Args:
        prompt: Output of `generate_gnn_explanation_prompt`.
        provider: Which API to call.
        model: Model id. Defaults to the provider's entry in DEFAULT_MODELS.
        temperature: Sampling temperature.

    Returns:
        The explanation, stripped of surrounding whitespace.
    """
    if provider not in DEFAULT_MODELS:
        raise ValueError(
            f"Unknown provider {provider!r}; expected one of {list(DEFAULT_MODELS)}"
        )

    client = _build_client(provider)
    completion = client.chat.completions.create(
        model=model or DEFAULT_MODELS[provider],
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return completion.choices[0].message.content.strip()
