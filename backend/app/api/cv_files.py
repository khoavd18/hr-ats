from ipaddress import ip_address
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from python_multipart.exceptions import MultipartParseError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException

from app.api.dependencies import DB, Config, CurrentUser
from app.core.errors import AppError, ErrorDetail
from app.schemas.core import CvFileRead
from app.schemas.cv_files import CvUploadResponse, CvUploadResult
from app.services import cv_files
from app.services.cv_validation import MAX_FILE_BYTES, MAX_FILES
from app.storage import Storage, build_storage

router = APIRouter(prefix="/cv-files", tags=["cv-files"])


def storage_dependency(settings: Config) -> Storage:
    return build_storage(settings)


FileStorage = Annotated[Storage, Depends(storage_dependency)]


def client_ip(request: Request) -> str | None:
    try:
        return str(ip_address(request.client.host)) if request.client else None
    except ValueError:
        return None


@router.post(
    "",
    response_model=CvUploadResponse,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["files"],
                        "properties": {
                            "files": {
                                "type": "array",
                                "minItems": 1,
                                "maxItems": MAX_FILES,
                                "items": {"type": "string", "format": "binary"},
                            },
                            "job_id": {"type": "string", "format": "uuid"},
                        },
                    },
                }
            },
        }
    },
)
async def upload_files(
    request: Request, session: DB, actor: CurrentUser, storage: FileStorage
) -> CvUploadResponse:
    try:
        form = await request.form(max_files=MAX_FILES, max_fields=1, max_part_size=1024)
    except (HTTPException, MultipartParseError):
        raise AppError(
            "INVALID_UPLOAD_BATCH", "Mỗi lần tải từ 1 đến 50 tệp và tối đa một Job.", 422
        ) from None
    try:
        files = form.getlist("files")
        if (
            not 1 <= len(files) <= MAX_FILES
            or not all(isinstance(file, UploadFile) for file in files)
            or set(form) - {"files", "job_id"}
        ):
            raise AppError("VALIDATION_ERROR", "Dữ liệu tải tệp không hợp lệ.", 422)
        raw_job = form.get("job_id")
        try:
            job_id = UUID(raw_job) if isinstance(raw_job, str) else None
            if raw_job is not None and not isinstance(raw_job, str):
                raise ValueError
        except ValueError:
            raise AppError("VALIDATION_ERROR", "Vị trí tuyển dụng không hợp lệ.", 422) from None
        await run_in_threadpool(cv_files.check_upload_scope, session, actor, job_id)
        results = []
        for index, file in enumerate(files):
            assert isinstance(file, UploadFile)
            data = await file.read(MAX_FILE_BYTES + 1)
            try:
                result = await run_in_threadpool(
                    cv_files.upload_file,
                    session,
                    actor,
                    storage,
                    data=data,
                    filename=file.filename or "cv",
                    job_id=job_id,
                    index=index,
                )
            except AppError as error:
                session.rollback()
                result = CvUploadResult(
                    index=index, error=ErrorDetail(code=error.code, message=error.message)
                )
            results.append(result)
        return CvUploadResponse(items=results)
    finally:
        await form.close()


@router.get("/{cv_file_id}", response_model=CvFileRead)
def file_status(
    cv_file_id: UUID, request: Request, response: Response, session: DB, actor: CurrentUser
) -> CvFileRead:
    cv_file = cv_files.get_file(session, actor, cv_file_id)
    snapshot = CvFileRead.model_validate(cv_file)
    cv_files.record_access(session, actor, cv_file, "view", client_ip(request))
    response.headers["Cache-Control"] = "no-store"
    return snapshot


@router.get(
    "/{cv_file_id}/download",
    response_class=Response,
    responses={
        200: {
            "content": {
                mime: {"schema": {"type": "string", "format": "binary"}}
                for mime in (
                    "application/pdf",
                    "image/jpeg",
                    "image/png",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            }
        }
    },
)
def download(
    cv_file_id: UUID, request: Request, session: DB, actor: CurrentUser, storage: FileStorage
) -> Response:
    cv_file, data = cv_files.download_file(session, actor, storage, cv_file_id, client_ip(request))
    extension = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}.get(
        cv_file.mime_type, "docx"
    )
    return Response(
        content=data,
        media_type=cv_file.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="cv-{cv_file.id}.{extension}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
