from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from agent.config import Settings
from agent.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, adapter_mode="mock")


@pytest.fixture
def app(settings: Settings):
    return create_app(settings=settings)


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
