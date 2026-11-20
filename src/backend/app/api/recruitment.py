from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response
from pydantic import AwareDatetime

from app.api.dependencies import DB, CurrentUser
from app.schemas.recruitment import (
    InterviewCreate,
    InterviewList,
    InterviewPatch,
    InterviewRead,
    OfferCreate,
    OfferPatch,
    OfferRead,
    PlacementCreate,
    PlacementPatch,
    PlacementRead,
)
from app.services import recruitment

router = APIRouter(tags=["recruitment"])


@router.post(
    "/applications/{application_id}/interviews", response_model=InterviewRead, status_code=201
)
def create_interview(
    application_id: UUID, body: InterviewCreate, response: Response, session: DB, actor: CurrentUser
):
    response.headers["Cache-Control"] = "no-store"
    return recruitment.create_interview(session, actor, application_id, body)


@router.patch("/interviews/{interview_id}", response_model=InterviewRead)
def patch_interview(
    interview_id: UUID, body: InterviewPatch, response: Response, session: DB, actor: CurrentUser
):
    response.headers["Cache-Control"] = "no-store"
    return recruitment.patch_interview(session, actor, interview_id, body)


@router.get("/interviews", response_model=InterviewList)
def list_interviews(
    response: Response,
    session: DB,
    actor: CurrentUser,
    from_date: Annotated[date | AwareDatetime | None, Query(alias="from")] = None,
    to_date: Annotated[date | AwareDatetime | None, Query(alias="to")] = None,
    mine: bool = True,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    response.headers["Cache-Control"] = "no-store"
    return recruitment.list_interviews(session, actor, from_date, to_date, mine, page, page_size)


@router.get("/interviews/{interview_id}/ics", response_class=Response)
def calendar_file(interview_id: UUID, session: DB, actor: CurrentUser):
    return Response(
        recruitment.calendar_file(session, actor, interview_id),
        media_type="text/calendar; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="interview-{interview_id}.ics"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/applications/{application_id}/offers", response_model=OfferRead, status_code=201)
def create_offer(
    application_id: UUID, body: OfferCreate, response: Response, session: DB, actor: CurrentUser
):
    response.headers["Cache-Control"] = "no-store"
    return recruitment.create_offer(session, actor, application_id, body)


@router.patch("/offers/{offer_id}", response_model=OfferRead)
def patch_offer(
    offer_id: UUID, body: OfferPatch, response: Response, session: DB, actor: CurrentUser
):
    response.headers["Cache-Control"] = "no-store"
    return recruitment.patch_offer(session, actor, offer_id, body)


@router.post(
    "/applications/{application_id}/placement", response_model=PlacementRead, status_code=201
)
def create_placement(
    application_id: UUID, body: PlacementCreate, response: Response, session: DB, actor: CurrentUser
):
    response.headers["Cache-Control"] = "no-store"
    return recruitment.create_placement(session, actor, application_id, body)


@router.patch("/placements/{placement_id}", response_model=PlacementRead)
def patch_placement(
    placement_id: UUID, body: PlacementPatch, response: Response, session: DB, actor: CurrentUser
):
    response.headers["Cache-Control"] = "no-store"
    return recruitment.patch_placement(session, actor, placement_id, body)
