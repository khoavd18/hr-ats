from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
BACKEND_VAR_DIR = BACKEND_ROOT / "var"
REPO_ROOT = BACKEND_ROOT.parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_env: Literal["dev", "test", "prod"] = "dev"
    secret_key: SecretStr = SecretStr("change-me")
    database_url: str = Field(
        default="postgresql+psycopg://hr:hr@localhost:5432/hr_ats", repr=False
    )
    redis_url: str = Field(default="redis://localhost:6379/0", repr=False)
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_dir: Path = Path("var/storage")
    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_access_key: SecretStr = SecretStr("")
    s3_secret_key: SecretStr = SecretStr("")
    llm_provider: Literal["fake", "anthropic", "openai", "ollama"] = "fake"
    llm_model: str = ""
    score_must_weight: float = Field(default=0.75, ge=0, le=1, allow_inf_nan=False)
    score_partial_value: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
    score_high_threshold: int = Field(default=75, ge=0, le=100)
    score_unknown_threshold: float = Field(default=0.5, gt=0, le=1, allow_inf_nan=False)
    score_min_text_length: int = Field(default=300, ge=0)
    anthropic_api_key: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    ollama_base_url: str = "http://localhost:11434"
    embedding_provider: Literal["fake", "local"] = "fake"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = Field(default=1024, gt=0)
    ocr_enabled: bool = True
    tesseract_langs: str = "vie+eng"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = "Tuyển dụng <tuyendung@example.com>"
    smtp_tls: bool = False
    email_rate_limit_per_hour: int = Field(default=200, ge=1)
    login_rate_limit_per_minute: int = Field(default=30, ge=1, le=10000)
    upload_rate_limit_per_minute: int = Field(default=20, ge=1, le=10000)
    imap_enabled: bool = False
    imap_host: str = ""
    imap_user: str = ""
    imap_password: SecretStr = SecretStr("")
    imap_folder: str = "INBOX"
    n8n_overdue_enabled: bool = False
    n8n_overdue_webhook_url: str = Field(default="", repr=False)
    n8n_overdue_webhook_key: SecretStr = SecretStr("")
    n8n_overdue_user_id: UUID | None = None
    hiring_unit_label: str = "Đơn vị tuyển"
    data_retention_months: int = Field(default=24, ge=1)
    frontend_origin: str = "http://localhost:3000"
    # Do not let an operating-system TZ override Vietnamese business-day boundaries.
    tz: Literal["Asia/Ho_Chi_Minh"] = Field(
        default="Asia/Ho_Chi_Minh", validation_alias="APP_TIMEZONE"
    )

    @model_validator(mode="after")
    def validate_production_signing_key(self) -> Self:
        key = self.secret_key.get_secret_value()
        if self.app_env == "prod" and (
            key.strip() in {"", "change-me"} or len(key.encode("utf-8")) < 32
        ):
            raise ValueError("SECRET_KEY must be non-default and at least 32 UTF-8 bytes in prod")
        return self

    @model_validator(mode="after")
    def validate_n8n_overdue(self) -> Self:
        if not self.n8n_overdue_enabled:
            return self
        url = urlsplit(self.n8n_overdue_webhook_url)
        port = url.port
        if (
            not url.hostname
            or port == 0
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or not url.path.startswith("/webhook/")
            or (
                url.scheme != "https"
                and (
                    url.scheme != "http"
                    or url.hostname not in {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
                )
            )
        ):
            raise ValueError(
                "N8N_OVERDUE_WEBHOOK_URL must be a production webhook on HTTPS or local HTTP"
            )
        key = self.n8n_overdue_webhook_key.get_secret_value()
        if not key or any(not 33 <= ord(character) <= 126 for character in key):
            raise ValueError("N8N_OVERDUE_WEBHOOK_KEY must be set to an ASCII token")
        if self.n8n_overdue_user_id is None:
            raise ValueError("N8N_OVERDUE_USER_ID must be set")
        return self

    @field_validator("storage_local_dir")
    @classmethod
    def resolve_storage_dir(cls, value: Path) -> Path:
        # Keep the default in the backend and honor existing custom paths.
        if value == Path("var/storage"):
            return BACKEND_VAR_DIR / "storage"
        return value if value.is_absolute() else REPO_ROOT / value

    @field_validator("frontend_origin")
    @classmethod
    def validate_origin(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise ValueError("FRONTEND_ORIGIN must be a single HTTP(S) origin")
        return value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
