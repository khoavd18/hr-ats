from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import DB, Config, CurrentUser
from app.api.jobs import Page, PageSize, no_store
from app.models.enums import CandidateSource
from app.schemas.cv_bank import CandidateBrief, CandidateList, MergeInput
from app.schemas.users import InputModel
from app.services import cv_bank

router = APIRouter(tags=["cv-bank"], dependencies=[Depends(no_store)])


class SearchFilters(InputModel):
    q: Annotated[str, Query(max_length=200)] = ""
    skills: Annotated[str, Query(max_length=1000)] = ""
    min_years: Annotated[Decimal | None, Query(ge=0, le=9999.99)] = None
    location: Annotated[str, Query(max_length=200)] = ""
    source: CandidateSource | None = None
    page: Page = 1
    page_size: PageSize = 20


@router.get("/candidates", response_model=CandidateList)
def search(session: DB, actor: CurrentUser, filters: Annotated[SearchFilters, Query()]):
    return cv_bank.search(session, actor, **filters.model_dump())


@router.get("/candidates/search/semantic", response_model=CandidateList)
def semantic(
    session: DB, actor: CurrentUser, settings: Config, filters: Annotated[SearchFilters, Query()]
):
    return cv_bank.search(session, actor, **filters.model_dump(), semantic=True, settings=settings)


@router.get("/jobs/{job_id}/suggestions", response_model=CandidateList)
def suggestions(
    job_id: UUID, session: DB, actor: CurrentUser, limit: Annotated[int, Query(ge=1, le=50)] = 50
):
    return cv_bank.suggestions(session, actor, job_id, limit)


@router.post("/candidates/{candidate_id}/merge", response_model=CandidateBrief)
def merge(candidate_id: UUID, body: MergeInput, session: DB, actor: CurrentUser):
    return cv_bank.merge(session, actor, candidate_id, body.into_id)
