from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import DB, Config, CurrentUser
from app.api.jobs import Page, PageSize, no_store
from app.schemas.email import (
    PreviewChoices,
    PreviewInput,
    PreviewRead,
    TemplateCreate,
    TemplateList,
    TemplatePatch,
    TemplateRead,
)
from app.services import email_templates

router = APIRouter(
    prefix="/email-templates", tags=["email-templates"], dependencies=[Depends(no_store)]
)


@router.get("", response_model=TemplateList)
def list_templates(session: DB, actor: CurrentUser, page: Page = 1, page_size: PageSize = 20):
    return email_templates.list_templates(session, actor, page, page_size)


@router.get("/preview-options", response_model=PreviewChoices)
def options(
    session: DB,
    actor: CurrentUser,
    page: Page = 1,
    page_size: PageSize = 20,
    q: Annotated[str, Query(max_length=200)] = "",
):
    return email_templates.preview_choices(session, actor, page, page_size, q)


@router.post("", response_model=TemplateRead, status_code=201)
def create_template(data: TemplateCreate, session: DB, actor: CurrentUser):
    return email_templates.save_template(session, actor, data)


@router.patch("/{template_id}", response_model=TemplateRead)
def update_template(template_id: UUID, data: TemplatePatch, session: DB, actor: CurrentUser):
    return email_templates.save_template(session, actor, data, template_id)


@router.post("/{template_id}/preview", response_model=PreviewRead)
def preview(
    template_id: UUID, data: PreviewInput, session: DB, actor: CurrentUser, settings: Config
):
    return email_templates.preview(session, actor, template_id, data, settings)
