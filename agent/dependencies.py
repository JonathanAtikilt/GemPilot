from __future__ import annotations

from functools import lru_cache

from fastapi import Request

from agent.config import Settings
from agent.github_oauth import GitHubConnectionService
from agent.service import AgentService
from agent.task_store import InMemoryTaskStore


@lru_cache
def build_settings() -> Settings:
    return Settings()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_task_store(request: Request) -> InMemoryTaskStore:
    return request.app.state.task_store


def get_agent_service(request: Request) -> AgentService:
    return request.app.state.agent_service


def get_github_connection_service(request: Request) -> GitHubConnectionService:
    return request.app.state.github_connection_service
