from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import REPO_ROOT, Settings


def test_example_configuration_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    # TZ is a common OS variable (CI, containers) and would override the example file.
    monkeypatch.delenv("TZ", raising=False)
    settings = Settings(_env_file=REPO_ROOT / ".env.example")
    assert settings.llm_provider == settings.embedding_provider == "fake"
    assert settings.embedding_dim == 1024
    assert settings.smtp_port == 1025
    assert settings.smtp_from == "Tuyển dụng <tuyendung@example.com>"
    assert settings.storage_local_dir == REPO_ROOT / "var/storage"
    assert settings.tz == "Asia/Ho_Chi_Minh"


def test_settings_read_utf8_dotenv_with_environment_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv = tmp_path / "settings.env"
    dotenv.write_text('HIRING_UNIT_LABEL="Phòng tuyển dụng"\nSMTP_PORT=2025\n', encoding="utf-8")
    monkeypatch.delenv("HIRING_UNIT_LABEL", raising=False)
    monkeypatch.delenv("SMTP_PORT", raising=False)
    assert Settings(_env_file=dotenv).hiring_unit_label == "Phòng tuyển dụng"
    assert Settings(_env_file=dotenv).smtp_port == 2025
    monkeypatch.setenv("SMTP_PORT", "3025")
    assert Settings(_env_file=dotenv).smtp_port == 3025


def test_secrets_and_connection_urls_are_not_in_settings_repr() -> None:
    settings = Settings(
        secret_key="synthetic-secret-marker",
        openai_api_key="synthetic-api-marker",
        database_url="postgresql+psycopg://synthetic:synthetic-db-marker@localhost/hr_ats_test",
        redis_url="redis://:synthetic-redis-marker@localhost:6379/15",
    )
    rendered = repr(settings)
    for marker in (
        "synthetic-secret-marker",
        "synthetic-api-marker",
        "synthetic-db-marker",
        "synthetic-redis-marker",
    ):
        assert marker not in rendered


@pytest.mark.parametrize("origin", ["*", "http://localhost:3000/path", "https://user:pass@host"])
def test_cors_origin_rejects_wildcards_paths_and_credentials(origin: str) -> None:
    with pytest.raises(ValidationError):
        Settings(frontend_origin=origin)


def test_cors_origin_normalizes_trailing_slash() -> None:
    assert (
        Settings(frontend_origin="http://localhost:3000/").frontend_origin
        == "http://localhost:3000"
    )


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(llm_provider="unknown")


@pytest.mark.parametrize("key", ["", " " * 32, "change-me", "synthetic-short-key", "x" * 31])
def test_production_refuses_default_or_short_signing_keys(key: str) -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(app_env="prod", secret_key=key)


def test_production_accepts_a_sufficiently_long_synthetic_key() -> None:
    settings = Settings(app_env="prod", secret_key="synthetic-production-key-for-tests-only")
    assert settings.app_env == "prod"
