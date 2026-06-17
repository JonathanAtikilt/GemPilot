from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from agent.config import Settings
from agent.dependencies import get_settings
from agent.rag.env_status import rag_env_status

router = APIRouter()


@router.get("/health")
async def health(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    rag_status = rag_env_status()
    return {
        "status": settings.health_status,
        "adapter_mode": settings.adapter_mode,
        "mock_mode": settings.mock_mode,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model_name,
        "llm_configured": settings.llm_configured,
        "allow_idea_aware_partial": settings.allow_idea_aware_partial,
        "llm_strict_live_active": settings.llm_strict_live_active,
        "workflow_live_manifest_only": settings.workflow_live_manifest_only,
        "llm_fast_fallback_active": settings.llm_fast_fallback_active,
        "llm_effective_timeout_seconds": settings.llm_effective_timeout_seconds,
        "llm_file_manifest_timeout_seconds": settings.llm_file_manifest_timeout_seconds,
        "llm_poll_max_seconds": settings.llm_poll_max_seconds,
        "require_live_file_manifest": settings.require_live_file_manifest,
        "runtime": "langgraph",
        "registered_tools": [],
        "supabase_configured": settings.supabase_configured,
        "rag_configured": rag_status["configured"],
        "rag_missing_env": rag_status["missing_required"],
        "rag_live_ready": settings.rag_live_ready,
        "github_oauth_configured": settings.github_oauth_configured,
        "github_pat_configured": settings.github_pat_configured,
        "github_oauth_redirect_uri": settings.github_oauth_redirect_uri,
        "github_connection_store": getattr(
            request.app.state,
            "github_connection_store_mode",
            "memory",
        ),
        "service": "gempilot-agent",
    }
