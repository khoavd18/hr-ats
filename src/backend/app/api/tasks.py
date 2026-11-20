from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response
from pydantic import AwareDatetime
from sqlalchemy import func, select

from app.api.dependencies import DB, CurrentUser
from app.models import Application, Candidate, Job
from app.models.enums import TaskStatus
from app.schemas.tasks import (
    Overview,
    TaskApplicationChoice,
    TaskApplicationOptions,
    TaskCreate,
    TaskList,
    TaskPatch,
    TaskRead,
)
from app.services import tasks
from app.services.overview import overview
from app.services.ranking import visible_applications

router = APIRouter(tags=["tasks"])


@router.get("/tasks", response_model=TaskList)
def list_tasks(
    response: Response,
    session: DB,
    actor: CurrentUser,
    mine: bool = True,
    status: TaskStatus | None = None,
    due_before: AwareDatetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    response.headers["Cache-Control"] = "no-store"
    return tasks.list_tasks(session, actor, mine, status, due_before, page, page_size)


@router.post("/tasks", response_model=TaskRead, status_code=201)
def create_task(body: TaskCreate, response: Response, session: DB, actor: CurrentUser):
    response.headers["Cache-Control"] = "no-store"
    return tasks.create_task(session, actor, body)


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def patch_task(task_id: UUID, body: TaskPatch, response: Response, session: DB, actor: CurrentUser):
    response.headers["Cache-Control"] = "no-store"
    return tasks.patch_task(session, actor, task_id, body)


@router.get("/tasks/application-options", response_model=TaskApplicationOptions)
def application_options(
    response: Response,
    session: DB,
    actor: CurrentUser,
    job_id: UUID,
    q: Annotated[str, Query(max_length=200)] = "",
    page: Annotated[int, Query(ge=1)] = 1,
):
    from app.services.applications import accessible_job

    response.headers["Cache-Control"] = "no-store"
    accessible_job(session, actor, job_id)
    query = (
        visible_applications()
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.job_id == job_id, Candidate.full_name.icontains(q.strip(), autoescape=True)
        )
    )
    rows = session.execute(
        query.with_only_columns(
            Application.id, Application.job_id, Candidate.full_name.label("name")
        )
        .order_by(Candidate.full_name, Application.id)
        .offset((page - 1) * 20)
        .limit(20)
    )
    return TaskApplicationOptions(
        items=[TaskApplicationChoice.model_validate(r._mapping) for r in rows],
        total=session.scalar(select(func.count()).select_from(query.subquery())) or 0,
    )


@router.get("/overview", response_model=Overview)
def get_overview(response: Response, session: DB, actor: CurrentUser):
    response.headers["Cache-Control"] = "no-store"
    return overview(session, actor)
