from __future__ import annotations

import json

import respx
from httpx import Response

from agent.config import Settings
from agent.model_client import (
    DeterministicModelClient,
    ProviderModelClient,
    _parse_json_text,
)
from agent.model_outputs import MvpScopeOutput


def test_llm_fast_fallback_uses_shorter_live_limits() -> None:
    settings = Settings(
        _env_file=None,
        allow_idea_aware_partial=True,
        llm_fast_fallback=True,
        llm_timeout_seconds=300,
        llm_max_retries=3,
        llm_poll_max_seconds=600,
        llm_live_attempt_timeout_seconds=75,
        llm_fast_fallback_max_retries=0,
        llm_fast_fallback_poll_max_seconds=90,
    )

    assert settings.llm_fast_fallback_active is True
    assert settings.llm_effective_timeout_seconds == 75
    assert settings.llm_effective_max_retries == 0
    assert settings.llm_effective_poll_max_seconds == 90


def test_parse_json_text_salvages_markdown_fence() -> None:
    assert _parse_json_text('```json\n{"ok": true}\n```') == {"ok": True}


async def test_deterministic_model_client_returns_schema_output() -> None:
    client = DeterministicModelClient(mode="mock")

    result = await client.complete_structured(
        purpose="scope_mvp",
        model="mock-model",
        prompt="Build a study planner for students.",
        response_model=MvpScopeOutput,
    )

    assert result.mode == "mock"
    assert result.output.core_features


@respx.mock
async def test_provider_model_client_posts_gemini_structured_request() -> None:
    settings = Settings(
        _env_file=None,
        adapter_mode="live",
        allow_idea_aware_partial=False,
        gemini_api_key="fake-gemini",
        gemini_base_url="https://gemini.test/v1",
        llm_model="gemini-2.5-flash",
    )
    route = respx.post(
        "https://gemini.test/v1/models/gemini-2.5-flash:generateContent"
    ).mock(
        return_value=Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": (
                                        '{"target_users":"students",'
                                        '"user_personas":["student"],'
                                        '"core_features":["planner","tasks","dashboard"],'
                                        '"success_criteria":["user completes plan"],'
                                        '"mode":"live",'
                                        '"decision_trace":["planned"]}'
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
        )
    )

    result = await ProviderModelClient(settings).complete_structured(
        purpose="scope_mvp",
        model=settings.llm_model_name,
        prompt="Build a study planner.",
        response_model=MvpScopeOutput,
    )

    assert result.mode == "live"
    posted = json.loads(route.calls.last.request.content)
    assert posted["generationConfig"]["responseMimeType"] == "application/json"
    assert "responseSchema" in posted["generationConfig"]
    assert posted["systemInstruction"]["parts"][0]["text"]


async def test_provider_model_client_degrades_when_key_missing() -> None:
    settings = Settings(
        _env_file=None,
        adapter_mode="live",
        allow_idea_aware_partial=True,
        gemini_api_key=None,
    )

    result = await ProviderModelClient(settings).complete_structured(
        purpose="scope_mvp",
        model=settings.llm_model_name,
        prompt="Build a study planner for students.",
        response_model=MvpScopeOutput,
    )

    assert result.mode == "degraded"
    assert "GEMINI_API_KEY" in (result.fallback_reason or "")
