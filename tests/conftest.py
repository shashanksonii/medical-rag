"""Shared pytest fixtures.

Tests build ``Settings`` with ``_env_file=None`` so a developer's local ``.env``
can never change test results.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, environment="testing", app_name="Test API")


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))
