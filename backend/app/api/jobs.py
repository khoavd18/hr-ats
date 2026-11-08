from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.api.dependencies import DB, Config, CurrentUser
from app.models.enums import JobStatus
from app.schemas.core import HiringUnitRead
from app.schemas.jobs import (
    HiringUnitCreate,
    HiringUnitList,
    HiringUnitPatch,
    JobCreate,
    JobList,
    JobMembersInput,
    JobOptions,
    JobPatch,
    JobResponse,
)
from app.services import jobs


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(tags=["jobs"], dependencies=[Depends(no_store)])
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get("/hiring-units", response_model=HiringUnitList)
def list_units(session: DB, actor: CurrentUser, page: Page = 1, page_size: PageSize = 20):
    return jobs.list_units(session, actor, page, page_size)


@router.post("/hiring-units", response_model=HiringUnitRead, status_code=201)
def create_unit(data: HiringUnitCreate, session: DB, actor: CurrentUser):
    return jobs.save_unit(session, actor, data)


@router.patch("/hiring-units/{unit_id}", response_model=HiringUnitRead)
def update_unit(unit_id: UUID, data: HiringUnitPatch, session: DB, actor: CurrentUser):
    return jobs.save_unit(session, actor, data, unit_id)


@router.get("/jobs/options", response_model=JobOptions)
def options(session: DB, actor: CurrentUser):
    return jobs.options(session, actor)


@router.get("/jobs", response_model=JobList)
def list_jobs(
    session: DB,
    actor: CurrentUser,
    page: Page = 1,
    page_size: PageSize = 20,
    status: JobStatus | None = None,
    owner_id: UUID | None = None,
    q: Annotated[str, Query(max_length=200)] = "",
):
    return jobs.list_jobs(session, actor, page, page_size, status, owner_id, q)


@router.post("/jobs", response_model=JobResponse, status_code=201)
def create_job(data: JobCreate, session: DB, actor: CurrentUser, settings: Config):
    return jobs.save_job(session, actor, data, settings)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: UUID, session: DB, actor: CurrentUser):
    return jobs.response(session, jobs.get_job(session, actor, job_id))


@router.patch("/jobs/{job_id}", response_model=JobResponse)
def update_job(job_id: UUID, data: JobPatch, session: DB, actor: CurrentUser, settings: Config):
    return jobs.save_job(session, actor, data, settings, job_id)


@router.put("/jobs/{job_id}/members", response_model=JobResponse)
def replace_members(job_id: UUID, data: JobMembersInput, session: DB, actor: CurrentUser):
    return jobs.replace_members(session, actor, job_id, data.user_ids)
