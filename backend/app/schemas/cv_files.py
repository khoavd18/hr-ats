from uuid import UUID

from pydantic import BaseModel

from app.core.errors import ErrorDetail
from app.models.enums import ProcessingStatus
from app.schemas.core import CvFileRead


class CvFileStatusRead(CvFileRead):
    processing_error: ErrorDetail | None = None
    application_id: UUID | None = None
    ai_status: ProcessingStatus | None = None


class CvUploadResult(BaseModel):
    index: int
    cv_file: CvFileRead | None = None
    duplicate: bool = False
    error: ErrorDetail | None = None


class CvUploadResponse(BaseModel):
    items: list[CvUploadResult]
