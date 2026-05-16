from __future__ import annotations

from fastapi import APIRouter, Depends

from agent.config import Settings
from agent.dependencies import get_settings

router = APIRouter()


@router.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    return {
        "status": settings.health_status,
        "adapter_mode": settings.adapter_mode,
        "mock_mode": settings.mock_mode,
        "nemotron_model": settings.nemotron_model,
        "nemotron_fast_model": settings.nemotron_fast_model,
        "nvidia_configured": settings.nvidia_configured,
        "openclaw_configured": settings.openclaw_configured,
        "service": "mvpilot-agent",
    }
