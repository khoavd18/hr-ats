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
