#!/usr/bin/env python3
"""Live smoke test for Gemini, Groq, OpenAI, and idea-aware partial fallback."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")


def _key_status(name: str) -> str:
    value = os.getenv(name, "").strip()
    return f"SET ({len(value)} chars)" if value else "MISSING"


async def test_provider_text(provider: str, model: str, api_key: str) -> dict:
    from agent.llm.provider import generate_text

    try:
        text = await generate_text(
            [{"role": "user", "content": "Reply with exactly: ok"}],
            {
                "provider": provider,
                "model": model,
                "api_key": api_key,
                "max_tokens": 16,
                "timeout_seconds": 60,
            },
        )
        return {"ok": True, "sample": text.strip()[:80]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}


async def test_gemini_to_groq_fallback() -> dict:
    from agent.llm.provider import generate_json

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        return {"skipped": True, "reason": "GROQ_API_KEY missing"}

    schema = {
        "type": "object",
        "properties": {"status": {"type": "string"}},
        "required": ["status"],
    }
    try:
        payload = await generate_json(
            [{"role": "user", "content": 'Return JSON: {"status":"ok"}'}],
            schema,
            {
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "api_key": "invalid-on-purpose",
                "fallback_provider": "groq",
                "fallback_model": os.getenv("LLM_FALLBACK_MODEL", "llama-3.1-8b-instant"),
                "fallback_api_key": groq_key,
                "fallback_base_url": os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
                "max_tokens": 64,
                "timeout_seconds": 60,
            },
        )
        return {"ok": True, "payload": payload}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}


async def test_idea_aware_partial_scope() -> dict:
    from agent.config import Settings
    from agent.model_client import ProviderModelClient
    from agent.model_outputs import MvpScopeOutput

    settings = Settings(
        _env_file=None,
        adapter_mode="live",
        allow_idea_aware_partial=True,
        gemini_api_key=None,
        groq_api_key=None,
        openai_api_key=None,
    )
    client = ProviderModelClient(settings)
    result = await client.complete_structured(
        purpose="scope_mvp",
        model="gemini-2.5-flash",
        prompt="Build HealthRef, a healthcare referral app for clinics.",
        response_model=MvpScopeOutput,
    )
    return {
        "ok": result.mode in {"degraded", "partial"},
        "mode": result.mode,
        "fallback_reason": (result.fallback_reason or "")[:200],
        "has_title": bool(getattr(result.output, "title", None) or getattr(result.output, "project_title", None)),
    }


async def test_provider_model_with_live_env() -> dict:
    from agent.config import Settings
    from agent.model_client import ProviderModelClient
    from agent.model_outputs import MvpScopeOutput

    settings = Settings()
    if not settings.llm_configured:
        return {"skipped": True, "reason": "No LLM API key configured"}

    client = ProviderModelClient(settings)
    try:
        result = await client.complete_structured(
            purpose="scope_mvp",
            model=settings.llm_model_name,
            prompt="Build HealthRef, a healthcare referral coordination app.",
            response_model=MvpScopeOutput,
            max_tokens=1200,
        )
        return {
            "ok": True,
            "mode": result.mode,
            "model": result.model,
            "provider": settings.llm_provider,
            "fallback_reason": (result.fallback_reason or "")[:200] or None,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}


async def test_openai_embedding() -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"skipped": True, "reason": "OPENAI_API_KEY missing"}

    from agent.rag.embed import embed_text

    prev = os.environ.get("EMBEDDING_PROVIDER")
    os.environ["EMBEDDING_PROVIDER"] = "openai"
    os.environ["EMBEDDING_MODEL"] = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    try:
        vector = await embed_text("healthcare referral app smoke test")
        return {"ok": bool(vector), "dimensions": len(vector)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}
    finally:
        if prev is None:
            os.environ.pop("EMBEDDING_PROVIDER", None)
        else:
            os.environ["EMBEDDING_PROVIDER"] = prev


async def test_gemini_embedding() -> dict:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {"skipped": True, "reason": "GEMINI_API_KEY missing"}

    from agent.rag.embed import embed_text

    prev = os.environ.get("EMBEDDING_PROVIDER")
    os.environ["EMBEDDING_PROVIDER"] = "gemini"
    os.environ["EMBEDDING_MODEL"] = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
    try:
        vector = await embed_text("healthcare referral app smoke test")
        return {"ok": bool(vector), "dimensions": len(vector)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}
    finally:
        if prev is None:
            os.environ.pop("EMBEDDING_PROVIDER", None)
        else:
            os.environ["EMBEDDING_PROVIDER"] = prev


async def main() -> int:
    print("=== GemPilot provider + fallback live smoke test ===\n")
    print("Config:")
    print(f"  LLM_PROVIDER={os.getenv('LLM_PROVIDER', 'gemini')}")
    print(f"  ALLOW_IDEA_AWARE_PARTIAL={os.getenv('ALLOW_IDEA_AWARE_PARTIAL', 'false')}")
    print(f"  EMBEDDING_PROVIDER={os.getenv('EMBEDDING_PROVIDER', 'gemini')}")
    print(f"  GEMINI_API_KEY: {_key_status('GEMINI_API_KEY')}")
    print(f"  GROQ_API_KEY:   {_key_status('GROQ_API_KEY')}")
    print(f"  OPENAI_API_KEY: {_key_status('OPENAI_API_KEY')}")
    print()

    results: dict[str, object] = {}

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    if gemini_key:
        print("Testing Gemini text...")
        results["gemini_text"] = await test_provider_text(
            "gemini", os.getenv("LLM_MODEL", "gemini-2.5-flash"), gemini_key
        )
    else:
        results["gemini_text"] = {"skipped": True, "reason": "missing key"}

    if groq_key:
        print("Testing Groq text...")
        results["groq_text"] = await test_provider_text(
            "groq",
            os.getenv("LLM_FALLBACK_MODEL", "llama-3.1-8b-instant"),
            groq_key,
        )
    else:
        results["groq_text"] = {"skipped": True, "reason": "missing key"}

    if openai_key:
        print("Testing OpenAI text...")
        results["openai_text"] = await test_provider_text(
            "openai", os.getenv("OPENAI_LLM_MODEL", "gpt-4.1-mini"), openai_key
        )
    else:
        results["openai_text"] = {"skipped": True, "reason": "missing key"}

    print("Testing Gemini -> Groq JSON fallback (invalid Gemini key)...")
    results["gemini_groq_fallback"] = await test_gemini_to_groq_fallback()

    print("Testing idea-aware partial (no API keys)...")
    results["idea_aware_partial"] = await test_idea_aware_partial_scope()

    print("Testing ProviderModelClient with current .env...")
    results["provider_model_live"] = await test_provider_model_with_live_env()

    print("Testing Gemini embeddings...")
    results["gemini_embedding"] = await test_gemini_embedding()

    print("Testing OpenAI embeddings...")
    results["openai_embedding"] = await test_openai_embedding()

    print("\n=== Results ===")
    print(json.dumps(results, indent=2))

    failures = [
        name
        for name, payload in results.items()
        if isinstance(payload, dict) and payload.get("ok") is False
    ]
    if failures:
        print(f"\nFAILED: {', '.join(failures)}")
        return 1

    print("\nAll runnable checks passed (skipped items are OK if keys are missing).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
