from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.pipeline import StageLabel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    db: Literal["ok"] = "ok"
    redis: Literal["ok"] = "ok"


class PublicConfigResponse(BaseModel):
    hiring_unit_label: str
    stages: list[StageLabel]


class MailboxStatus(BaseModel):
    enabled: bool
    last_read_at: datetime | None = None
    last_error: (
        Literal[
            "IMAP_NOT_CONFIGURED",
            "IMAP_READ_FAILED",
            "IMAP_MESSAGE_TOO_LARGE",
            "IMAP_STATUS_UNAVAILABLE",
        ]
        | None
    ) = None
