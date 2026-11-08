from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


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
    anthropic_api_key: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    ollama_base_url: str = "http://localhost:11434"
    embedding_provider: Literal["fake", "local"] = "fake"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    ocr_enabled: bool = True
    tesseract_langs: str = "vie+eng"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = "Tuyển dụng <tuyendung@example.com>"
    smtp_tls: bool = False
    imap_enabled: bool = False
    imap_host: str = ""
    imap_user: str = ""
    imap_password: SecretStr = SecretStr("")
    imap_folder: str = "INBOX"
    hiring_unit_label: str = "Đơn vị tuyển"
    data_retention_months: int = 24
    frontend_origin: str = "http://localhost:3000"
    tz: str = "Asia/Ho_Chi_Minh"

    @model_validator(mode="after")
    def validate_production_signing_key(self) -> Self:
        key = self.secret_key.get_secret_value()
        if self.app_env == "prod" and (
            key.strip() in {"", "change-me"} or len(key.encode("utf-8")) < 32
        ):
            raise ValueError("SECRET_KEY must be non-default and at least 32 UTF-8 bytes in prod")
        return self

    @field_validator("storage_local_dir")
    @classmethod
    def resolve_storage_dir(cls, value: Path) -> Path:
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
