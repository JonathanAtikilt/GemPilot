from __future__ import annotations

import pytest

from agent.llm.provider import MissingLLMApiKeyError, _resolve_options


def test_resolve_options_defaults_to_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    options = _resolve_options()

    assert options.provider == "gemini"
    assert options.model == "gemini-2.5-flash"
    assert options.api_key == "test-gemini"


def test_resolve_options_uses_groq_when_primary_key_is_missing(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("ALLOW_IDEA_AWARE_PARTIAL", "true")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_FALLBACK_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")

    options = _resolve_options()

    assert options.provider == "groq"
    assert options.model == "llama-3.1-8b-instant"
    assert options.api_key == "test-groq"


def test_resolve_options_reports_missing_primary_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(MissingLLMApiKeyError, match="Missing OPENAI_API_KEY"):
        _resolve_options()
