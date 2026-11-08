from pydantic import BaseModel

from app.core.errors import ErrorDetail
from app.schemas.core import CvFileRead


class CvUploadResult(BaseModel):
    index: int
    cv_file: CvFileRead | None = None
    duplicate: bool = False
    error: ErrorDetail | None = None


class CvUploadResponse(BaseModel):
    items: list[CvUploadResult]
