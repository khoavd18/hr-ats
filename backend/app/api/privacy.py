from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import DB, Config, CurrentUser
from app.api.jobs import Page, PageSize, no_store
from app.schemas.privacy import (
    AuditList,
    ConsentInput,
    DataRequestInput,
    DataRequestList,
    DataRequestRead,
    RetentionList,
    RetentionRead,
)
from app.schemas.users import InputModel
from app.services import privacy
from app.storage import build_storage

router = APIRouter(tags=["privacy"], dependencies=[Depends(no_store)])


class Pages(InputModel):
    page: Page = 1
    page_size: PageSize = 20


class RetentionFilters(Pages):
    state: Literal["expiring", "expired", "all"] = "expiring"
    q: Annotated[str, Query(max_length=200)] = ""


class AuditFilters(Pages):
    actor_id: UUID | None = None
    action: Annotated[str, Query(max_length=100)] = ""
    entity: Annotated[str, Query(max_length=100)] = ""
    system: bool = False


@router.post("/candidates/{candidate_id}/consent", response_model=RetentionRead)
def consent(candidate_id: UUID, body: ConsentInput, session: DB, actor: CurrentUser):
    return privacy.record_consent(session, actor, candidate_id, body)


@router.get("/settings/retention", response_model=RetentionList)
def retention(session: DB, actor: CurrentUser, filters: Annotated[RetentionFilters, Query()]):
    return privacy.retention_list(session, actor, **filters.model_dump())


@router.get("/data-requests", response_model=DataRequestList)
def requests(session: DB, actor: CurrentUser, filters: Annotated[Pages, Query()]):
    return privacy.list_requests(session, actor, **filters.model_dump())


@router.post("/data-requests", response_model=DataRequestRead, status_code=201)
def create(body: DataRequestInput, session: DB, actor: CurrentUser):
    return privacy.create_request(session, actor, body)


@router.post("/data-requests/{request_id}/execute", response_model=DataRequestRead)
def execute(request_id: UUID, session: DB, actor: CurrentUser, settings: Config):
    return privacy.execute_request(session, actor, request_id, build_storage(settings))


@router.get("/audit-log", response_model=AuditList)
def audit(session: DB, actor: CurrentUser, filters: Annotated[AuditFilters, Query()]):
    return privacy.list_audit(session, actor, **filters.model_dump())
