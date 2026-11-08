from fastapi import FastAPI

from app.api import applications, auth, cv_bank, cv_files, jobs, system, users
from app.core.config import Settings, get_settings
from app.core.cors import ApiCORSMiddleware
from app.core.errors import ErrorResponse, register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    application = FastAPI(
        title="hr-ats",
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "prod" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.app_env != "prod" else None,
        responses={
            status: {"model": ErrorResponse}
            for status in (401, 403, 404, 405, 409, 422, 423, 500, 503)
        },
    )
    application.state.frontend_origin = settings.frontend_origin
    application.add_middleware(
        ApiCORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )
    register_error_handlers(application)
    application.add_middleware(RequestLoggingMiddleware)
    application.dependency_overrides[get_settings] = lambda: settings
    for router in (
        system.router,
        auth.router,
        users.router,
        cv_files.router,
        applications.router,
        jobs.router,
        cv_bank.router,
    ):
        application.include_router(router, prefix="/api/v1")
    return application


configure_logging()
app = create_app()
