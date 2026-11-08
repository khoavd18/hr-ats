from uuid import UUID

from fastapi import APIRouter, Response

from app.api.dependencies import DB, CurrentUser
from app.schemas.applications import ApplicationCreate
from app.schemas.core import ApplicationRead
from app.services import applications

router = APIRouter(tags=["applications"])


@router.post("/applications", response_model=ApplicationRead, status_code=201)
def create(body: ApplicationCreate, session: DB, actor: CurrentUser, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return applications.create_application(session, actor, **body.model_dump())


@router.post(
    "/applications/{application_id}/rescore", response_model=ApplicationRead, status_code=202
)
def rescore(application_id: UUID, session: DB, actor: CurrentUser, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return applications.rescore_application(session, actor, application_id)


@router.post("/jobs/{job_id}/rescore", status_code=202)
def rescore_job(job_id: UUID, session: DB, actor: CurrentUser):
    applications.rescore_job(session, actor, job_id)
    return {"status": "pending"}
