from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.logging import _MANAGED_FLAG, setup_logging
from app.main import create_app


def _managed_handlers() -> list[logging.Handler]:
    return [h for h in logging.getLogger().handlers if getattr(h, _MANAGED_FLAG, False)]


def test_setup_logging_is_idempotent() -> None:
    settings = Settings(_env_file=None)
    setup_logging(settings)
    setup_logging(settings)
    setup_logging(settings)
    assert len(_managed_handlers()) == 1  # console only, never duplicated


def test_log_level_applied_to_root() -> None:
    setup_logging(Settings(_env_file=None, log_level="DEBUG"))
    assert logging.getLogger().level == logging.DEBUG
    setup_logging(Settings(_env_file=None, log_level="ERROR"))
    assert logging.getLogger().level == logging.ERROR


def test_file_logging_creates_parent_dirs_and_writes(tmp_path: Path) -> None:
    log_file = tmp_path / "nested" / "app.log"
    setup_logging(Settings(_env_file=None, log_file=log_file))
    logging.getLogger("tests.file").info("hello file log")
    for handler in _managed_handlers():
        handler.flush()
    assert "hello file log" in log_file.read_text(encoding="utf-8")
    assert len(_managed_handlers()) == 2  # console + file
    setup_logging(Settings(_env_file=None))  # release the file handle (needed on Windows)


def test_request_is_logged_without_query_string(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    client = TestClient(create_app(settings))
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.get("/health?patient=P001")
    messages = [r.getMessage() for r in caplog.records if r.name == "app.request"]
    assert any("GET /health -> 200" in m for m in messages)
    assert not any("P001" in m for m in messages)
