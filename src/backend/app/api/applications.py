from uuid import UUID

from fastapi import APIRouter, Request, Response

from app.api.cv_files import client_ip
from app.api.dependencies import DB, Config, CurrentUser
from app.schemas.applications import ApplicationCreate
from app.schemas.core import AiFeedbackRead, ApplicationRead, CandidateRead
from app.schemas.pipeline import MoveInput, MoveResponse
from app.schemas.profile import (
    ApplicationDetail,
    CandidatePatch,
    FeedbackInput,
    NoteInput,
    ProfileActivity,
)
from app.services import applications, email_messages, pipeline, profile

router = APIRouter(tags=["applications"])


@router.post("/applications/{application_id}/move", response_model=MoveResponse)
def move(
    application_id: UUID,
    body: MoveInput,
    response: Response,
    session: DB,
    actor: CurrentUser,
    settings: Config,
):
    response.headers["Cache-Control"] = "no-store"
    application = pipeline.move(session, actor, application_id, **body.model_dump(), commit=False)
    draft, notice = email_messages.suggestion(
        session, actor, application_id, body.to_stage, settings
    )
    session.commit()
    return MoveResponse(application=application, suggested_email=draft, email_notice=notice)


@router.post("/applications/{application_id}/undo", response_model=ApplicationRead)
def undo(application_id: UUID, response: Response, session: DB, actor: CurrentUser):
    response.headers["Cache-Control"] = "no-store"
    return pipeline.undo(session, actor, application_id)


@router.get("/applications/{application_id}", response_model=ApplicationDetail)
def detail(
    application_id: UUID, request: Request, response: Response, session: DB, actor: CurrentUser
):
    response.headers["Cache-Control"] = "no-store"
    return profile.detail(session, actor, application_id, client_ip(request))


@router.post("/applications/{application_id}/ai-feedback", response_model=AiFeedbackRead)
def feedback(
    application_id: UUID, body: FeedbackInput, response: Response, session: DB, actor: CurrentUser
):
    response.headers["Cache-Control"] = "no-store"
    return profile.feedback(session, actor, application_id, body)


@router.post(
    "/applications/{application_id}/notes", response_model=ProfileActivity, status_code=201
)
def note(
    application_id: UUID, body: NoteInput, response: Response, session: DB, actor: CurrentUser
):
    response.headers["Cache-Control"] = "no-store"
    return profile.add_note(session, actor, application_id, body.text)


@router.patch("/candidates/{candidate_id}", response_model=CandidateRead)
def patch_candidate(
    candidate_id: UUID, body: CandidatePatch, response: Response, session: DB, actor: CurrentUser
):
    response.headers["Cache-Control"] = "no-store"
    return profile.patch_candidate(session, actor, candidate_id, body)


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
