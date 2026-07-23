"""Provider-agnostic LLM client for generating and revising explanations.

Supports Anthropic (default: Claude Opus 4.8), OpenAI, and Groq. Keys are read
from the environment -- never pass them as literals, and never commit them.
"""

from __future__ import annotations

import os
from typing import Literal

Provider = Literal["anthropic", "openai", "groq"]

DEFAULT_MODELS: dict[Provider, str] = {
    "anthropic": "claude-opus-4-8",
    "openai": "gpt-4o",
    "groq": "llama3-70b-8192",
}

_ENV_VARS: dict[Provider, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "groq": "GROQ_API_KEY",
}


def _build_client(provider: Provider):
    """Instantiate the SDK client for `provider`, reading its key from the env.

    The key is checked before the SDK is imported, so a missing-key error is
    raised even when the provider's package isn't installed.
    """
    env_var = _ENV_VARS[provider]
    api_key = os.environ.get(env_var)
    if not api_key:
        raise RuntimeError(
            f"{env_var} is not set. Copy .env.example to .env and add your key, "
            f"or export {env_var} in your shell."
        )

    if provider == "anthropic":
        from anthropic import Anthropic

        return Anthropic(api_key=api_key)
    if provider == "openai":
        from openai import OpenAI

        return OpenAI(api_key=api_key)

    from groq import Groq

    return Groq(api_key=api_key)


def explain_model_prediction(
    prompt: str,
    provider: Provider = "anthropic",
    model: str | None = None,
    temperature: float = 1.0,
    max_tokens: int = 1024,
) -> str:
    """Send `prompt` to the configured LLM and return the explanation text.

    Args:
        prompt: Output of `generate_gnn_explanation_prompt` (or a revision prompt).
        provider: Which API to call. Default "anthropic" (Claude Opus 4.8).
        model: Model id. Defaults to the provider's entry in DEFAULT_MODELS.
        temperature: Sampling temperature. Note Anthropic's valid range is 0..1.
        max_tokens: Response cap (Anthropic requires it; ignored by the others here).

    Returns:
        The explanation, stripped of surrounding whitespace.
    """
    if provider not in DEFAULT_MODELS:
        raise ValueError(
            f"Unknown provider {provider!r}; expected one of {list(DEFAULT_MODELS)}"
        )

    client = _build_client(provider)
    model = model or DEFAULT_MODELS[provider]

    if provider == "anthropic":
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return completion.choices[0].message.content.strip()
