from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import DB, Config, CurrentUser
from app.api.jobs import Page, PageSize, no_store
from app.schemas.email import (
    MessageCreate,
    MessageList,
    MessagePreviewInput,
    MessageRead,
    SendTemplateChoices,
    SuggestedEmail,
)
from app.services import email_messages

router = APIRouter(
    prefix="/email-messages", tags=["email-messages"], dependencies=[Depends(no_store)]
)


@router.get("", response_model=MessageList)
def list_messages(
    application_id: UUID, session: DB, actor: CurrentUser, page: Page = 1, page_size: PageSize = 20
):
    return email_messages.list_messages(session, actor, application_id, page, page_size)


@router.get("/templates", response_model=SendTemplateChoices)
def templates(application_id: UUID, session: DB, actor: CurrentUser):
    return email_messages.template_choices(session, actor, application_id)


@router.post("/preview", response_model=SuggestedEmail)
def preview(data: MessagePreviewInput, session: DB, actor: CurrentUser, settings: Config):
    return email_messages.preview(session, actor, data.application_id, data.template_id, settings)


@router.post("", response_model=MessageRead, status_code=201)
def create(data: MessageCreate, session: DB, actor: CurrentUser):
    return email_messages.create(session, actor, data)


@router.post("/{message_id}/send", response_model=MessageRead, status_code=202)
def send(message_id: UUID, session: DB, actor: CurrentUser):
    return email_messages.send(session, actor, message_id)


@router.post("/{message_id}/cancel", response_model=MessageRead)
def cancel(message_id: UUID, session: DB, actor: CurrentUser):
    return email_messages.cancel(session, actor, message_id)
