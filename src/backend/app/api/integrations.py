from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.api.dependencies import DB, Config
from app.api.rate_limits import LimitRedis
from app.core.errors import AppError
from app.core.logging import redact
from app.core.rate_limit import check_limit
from app.models import User
from app.reports import service as reports
from app.schemas.reports import ReportInput, SummaryReport
from app.schemas.tasks import TaskCreate
from app.services import tasks
from app.services.audit import record_audit
from app.services.integration_tokens import ServiceScope, authenticate_token

router = APIRouter(prefix="/integrations", tags=["integrations"])
bearer = HTTPBearer(auto_error=False)


class CreatedTask(BaseModel):
    task_id: UUID


def require_scope(scope: ServiceScope):
    def authorize(
        credential: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        session: DB,
        settings: Config,
        redis: LimitRedis,
    ) -> User:
        if credential is None:
            raise AppError("INVALID_SERVICE_TOKEN", "Cần token dịch vụ hợp lệ.", 401)
        token, sponsor = authenticate_token(session, credential.credentials)
        token_id = token.id
        check_limit(
            redis,
            settings,
            "integration",
            str(token_id),
            settings.integration_rate_limit_per_minute,
        )
        allowed = scope in token.scopes and scope != "cv:upload"
        record_audit(
            session,
            actor_id=sponsor.id,
            action="integration.access",
            entity="integration_token",
            entity_id=token_id,
            details={"scope": scope, "authorized": allowed},
        )
        session.commit()
        if not allowed:
            raise AppError("FORBIDDEN", "Token dịch vụ không có quyền thực hiện thao tác này.", 403)
        return sponsor

    return authorize


CreateTaskSponsor = Annotated[User, Depends(require_scope("tasks:create"))]
SummarySponsor = Annotated[User, Depends(require_scope("reports:summary"))]


@router.post("/tasks", response_model=CreatedTask, status_code=201)
def create_task(body: TaskCreate, response: Response, session: DB, sponsor: CreateTaskSponsor):
    if redact({"title": body.title, "note": body.description}) != {
        "title": body.title,
        "note": body.description,
    }:
        raise AppError("VALIDATION_ERROR", "Thông tin việc không hợp lệ.", 422)
    response.headers["Cache-Control"] = "no-store"
    return CreatedTask(task_id=tasks.create_task(session, sponsor, body).id)


@router.get("/reports/summary", response_model=SummaryReport)
def summary(
    params: Annotated[ReportInput, Query()],
    response: Response,
    session: DB,
    sponsor: SummarySponsor,
):
    response.headers["Cache-Control"] = "no-store"
    return reports.summary(session, sponsor, params)


@router.post("/cv-files", dependencies=[Depends(require_scope("cv:upload"))])
def intake_without_approval() -> None:
    # The integration scope is reserved. A separate approval and intake design
    # are required before T42 can receive any file or consent data.
    raise AppError("FORBIDDEN", "Chưa bật nhận CV qua tích hợp.", 403)
