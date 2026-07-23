"""Provider-layer tests. No API key and no SDK required -- the client is stubbed."""

import pytest

import gnnarrate.llm as llm_module
from gnnarrate.llm import DEFAULT_MODELS, explain_model_prediction


def test_default_provider_is_opus():
    assert DEFAULT_MODELS["anthropic"] == "claude-opus-4-8"
    assert set(DEFAULT_MODELS) == {"anthropic", "openai", "groq"}


def test_unknown_provider_rejected():
    with pytest.raises(ValueError, match="Unknown provider"):
        explain_model_prediction("hi", provider="mistral")


def test_missing_key_raises_before_sdk_import(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is not set"):
        explain_model_prediction("hi", provider="anthropic")


class _FakeAnthropicMessage:
    def __init__(self, text):
        # Real Anthropic TextBlocks carry type == "text"; the parser selects those.
        self.content = [type("Block", (), {"text": text, "type": "text"})()]


class _FakeAnthropicClient:
    def __init__(self):
        self.messages = self
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeAnthropicMessage("  grounded explanation.  ")


def test_anthropic_branch_builds_message_and_parses_text(monkeypatch):
    fake = _FakeAnthropicClient()
    monkeypatch.setattr(llm_module, "_build_client", lambda provider: fake)

    out = explain_model_prediction("PROMPT", provider="anthropic", max_tokens=256)

    assert out == "grounded explanation."          # parsed from content[0].text, stripped
    call = fake.calls[0]
    assert call["model"] == "claude-opus-4-8"       # default Opus model
    assert call["max_tokens"] == 256                # Anthropic requires max_tokens
    assert call["messages"] == [{"role": "user", "content": "PROMPT"}]


def test_anthropic_skips_non_text_blocks(monkeypatch):
    # Regression: a thinking/other block may precede the text block; the parser
    # must skip it rather than crash on content[0].text (the bug that skipped Sonnet).
    class _Msg:
        content = [
            type("Think", (), {"type": "thinking", "thinking": "reasoning..."})(),
            type("Block", (), {"type": "text", "text": "the answer"})(),
        ]

    class _Client:
        def __init__(self):
            self.messages = self

        def create(self, **kwargs):
            return _Msg()

    monkeypatch.setattr(llm_module, "_build_client", lambda provider: _Client())
    assert explain_model_prediction("PROMPT", provider="anthropic") == "the answer"


class _FakeChatClient:
    """Mimics the OpenAI/Groq chat.completions shape."""

    def __init__(self):
        choice = type("Choice", (), {
            "message": type("Msg", (), {"content": " openai text "})()
        })()
        self._resp = type("Resp", (), {"choices": [choice]})()
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, **kwargs):
        return self._resp


def test_openai_branch_uses_chat_completions(monkeypatch):
    monkeypatch.setattr(llm_module, "_build_client", lambda provider: _FakeChatClient())
    out = explain_model_prediction("PROMPT", provider="openai")
    assert out == "openai text"
