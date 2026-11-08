import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from app.core.logging import safe_traceback

logger = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def error_response(code: str, message: str, status: int) -> JSONResponse:
    payload = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status, content=payload.model_dump())


async def handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(exc.code, exc.message, exc.status)


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    # Validation details can include the original input, so never return or log them.
    return error_response("VALIDATION_ERROR", "Dữ liệu không hợp lệ.", 422)


async def handle_http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    errors = {
        400: ("BAD_REQUEST", "Yêu cầu không hợp lệ."),
        401: ("UNAUTHORIZED", "Vui lòng đăng nhập."),
        403: ("FORBIDDEN", "Bạn không có quyền thực hiện thao tác này."),
        404: ("NOT_FOUND", "Không tìm thấy dữ liệu."),
        405: ("METHOD_NOT_ALLOWED", "Phương thức không được hỗ trợ."),
    }
    code, message = errors.get(exc.status_code, ("HTTP_ERROR", "Không thể xử lý yêu cầu."))
    response = error_response(code, message, exc.status_code)
    if exc.headers:
        response.headers.update(exc.headers)
    return response


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled application error",
        extra={"exception_type": type(exc).__name__, "stack": safe_traceback(exc.__traceback__)},
    )
    response = error_response("INTERNAL_ERROR", "Đã có lỗi xảy ra. Vui lòng thử lại sau.", 500)
    # The server-error handler runs outside CORSMiddleware; keep its response readable by the UI.
    origin = request.headers.get("origin")
    if origin and origin == request.app.state.frontend_origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(HTTPException, handle_http_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
