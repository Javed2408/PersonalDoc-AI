from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
)


@pytest.fixture
def make_settings(tmp_path: Path) -> Callable[..., Settings]:
    """Settings pointing at a per-test temporary data directory, never backend/data."""

    def factory(**overrides) -> Settings:
        return Settings(_env_file=None, data_dir=tmp_path / "data", **overrides)

    return factory


@pytest.fixture
def make_client(make_settings) -> Iterator[Callable[..., TestClient]]:
    clients: list[TestClient] = []

    def factory(**overrides) -> TestClient:
        client = TestClient(create_app(make_settings(**overrides)))
        client.__enter__()  # run lifespan startup
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


@pytest.fixture
def settings(make_settings) -> Settings:
    return make_settings()


def upload(client: TestClient, filename: str = "report.pdf", content: bytes = MINIMAL_PDF,
           content_type: str = "application/pdf"):
    return client.post("/api/documents/upload", files={"file": (filename, content, content_type)})
