from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models.enums import ApplicationStage, EmailStatus
from app.schemas.users import EmailInput, InputModel

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Key = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
Subject = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)]


class TemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: Key
    name: Name
    stage: ApplicationStage | None = None
    subject: Subject
    body: Body
    is_active: bool = True
    requires_confirmation: bool = True

    @model_validator(mode="after")
    def confirmation(self) -> Self:
        if not self.requires_confirmation and self.key != "cv_received":
            raise ValueError("Mẫu này phải được xác nhận trước khi gửi.")
        if any(char in self.subject for char in "\r\n\x00"):
            raise ValueError("Tiêu đề phải nằm trên một dòng.")
        return self


class TemplatePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # key is immutable, including the special cv_received confirmation exception.
    name: Name | None = None
    stage: ApplicationStage | None = None
    subject: Subject | None = None
    body: Body | None = None
    is_active: bool | None = None
    requires_confirmation: bool | None = None

    @model_validator(mode="after")
    def no_nulls(self) -> Self:
        for field in self.model_fields_set - {"stage"}:
            if getattr(self, field) is None:
                raise ValueError("Không được để trống trường này.")
        return self


class TemplateRead(TemplateCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    updated_at: datetime


class TemplateList(BaseModel):
    items: list[TemplateRead]
    total: int


class PreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    application_id: UUID
    subject: Subject | None = None
    body: Body | None = None


class PreviewRead(BaseModel):
    subject: str
    body: str
    body_html: str


class PreviewChoice(BaseModel):
    id: UUID
    candidate_name: str
    job_title: str


class PreviewChoices(BaseModel):
    items: list[PreviewChoice]
    total: int = Field(ge=0)


class MessageCreate(InputModel):
    application_id: UUID
    template_id: UUID | None = None
    to_email: str = Field(min_length=3, max_length=254)
    subject: Subject
    # This is already rendered text, never evaluated as a template again.
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100000)]

    @field_validator("to_email")
    @classmethod
    def recipient(cls, value: str) -> str:
        value = EmailInput(email=value).email
        if any(char in value for char in '<>,;:"()\\'):
            raise ValueError("Chỉ nhập một địa chỉ email.")
        return value

    @field_validator("subject")
    @classmethod
    def single_line(cls, value: str) -> str:
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Tiêu đề phải nằm trên một dòng.")
        return value


class SuggestedEmail(MessageCreate):
    body_html: str
    has_calendar: bool = False


class MessagePreviewInput(InputModel):
    application_id: UUID
    template_id: UUID


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    application_id: UUID | None
    template_id: UUID | None
    to_email: str
    subject: str
    body_html: str
    status: EmailStatus
    sent_at: datetime | None
    scheduled_for: datetime | None
    error: str | None
    created_at: datetime


class MessageList(BaseModel):
    items: list[MessageRead]
    total: int


class SendTemplateChoice(BaseModel):
    id: UUID
    name: str


class SendTemplateChoices(BaseModel):
    items: list[SendTemplateChoice]
