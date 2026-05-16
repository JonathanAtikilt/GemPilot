from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent.config import Settings
from agent.dependencies import build_settings
from agent.rag.routes import router as rag_router
from agent.routers.agent import router as agent_router
from agent.routers.health import router as health_router
from agent.service import AgentService
from agent.task_store import InMemoryTaskStore

load_dotenv()


def create_app(
    *,
    settings: Settings | None = None,
    task_store: InMemoryTaskStore | None = None,
) -> FastAPI:
    active_settings = settings or build_settings()
    active_task_store = task_store or InMemoryTaskStore()
    active_service = AgentService(active_task_store, active_settings)

    app = FastAPI(title="MVPilot Agent Backend")
    app.state.settings = active_settings
    app.state.task_store = active_task_store
    app.state.agent_service = active_service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(agent_router)
    app.include_router(rag_router, prefix="/rag", tags=["rag"])
    return app


app = create_app()
