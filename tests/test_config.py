from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.environment == "development"
    assert s.debug is False
    assert s.host == "127.0.0.1"
    assert s.port == 8000
    assert s.log_level == "INFO"
    assert s.log_file is None
    assert s.data_dir == Path("data")


def test_environment_variables_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDRAG_PORT", "9100")
    monkeypatch.setenv("MEDRAG_ENVIRONMENT", "production")
    monkeypatch.setenv("MEDRAG_DEBUG", "true")
    s = Settings(_env_file=None)
    assert s.port == 9100
    assert s.environment == "production"
    assert s.debug is True


def test_env_file_is_read(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("MEDRAG_APP_NAME=From Env File\nMEDRAG_LOG_LEVEL=debug\n", encoding="utf-8")
    s = Settings(_env_file=env_file)
    assert s.app_name == "From Env File"
    assert s.log_level == "DEBUG"


def test_log_level_is_normalised_to_upper_case() -> None:
    assert Settings(_env_file=None, log_level=" warning ").log_level == "WARNING"


def test_invalid_log_level_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, log_level="LOUD")


def test_invalid_environment_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="staging")


@pytest.mark.parametrize("port", [0, 65536, -1])
def test_invalid_port_rejected(port: int) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, port=port)


def test_blank_log_file_means_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDRAG_LOG_FILE", "")
    assert Settings(_env_file=None).log_file is None


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()
    assert get_settings() is get_settings()
    get_settings.cache_clear()
