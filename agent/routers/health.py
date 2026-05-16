from __future__ import annotations

from fastapi import APIRouter, Depends

from agent.config import Settings
from agent.dependencies import get_settings
from agent.rag.env_status import rag_env_status

router = APIRouter()


@router.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    rag_status = rag_env_status()
    return {
        "status": settings.health_status,
        "adapter_mode": settings.adapter_mode,
        "mock_mode": settings.mock_mode,
        "nemotron_model": settings.nemotron_model,
        "nemotron_fast_model": settings.nemotron_fast_model,
        "nvidia_configured": settings.nvidia_configured,
        "openclaw_configured": settings.openclaw_configured,
        "openclaw_env": settings.openclaw_env,
        "supabase_configured": settings.supabase_configured,
        "rag_configured": rag_status["configured"],
        "rag_missing_env": rag_status["missing_required"],
        "rag_live_ready": settings.rag_live_ready,
        "service": "mvpilot-agent",
    }
