from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.dependencies import DB, CurrentUser
from app.reports import service
from app.reports.export import export_report
from app.schemas.reports import (
    AgreementReport,
    FunnelReport,
    RecruitersReport,
    ReportInput,
    SummaryReport,
)

router = APIRouter(prefix="/reports", tags=["reports"])
Params = Annotated[ReportInput, Query()]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/summary", response_model=SummaryReport)
def summary(params: Params, response: Response, session: DB, actor: CurrentUser):
    response.headers["Cache-Control"] = "no-store"
    return service.summary(session, actor, params)


@router.get("/funnel", response_model=FunnelReport)
def funnel(params: Params, response: Response, session: DB, actor: CurrentUser):
    response.headers["Cache-Control"] = "no-store"
    return service.funnel(session, actor, params)


@router.get("/recruiters", response_model=RecruitersReport)
def recruiters(params: Params, response: Response, session: DB, actor: CurrentUser):
    response.headers["Cache-Control"] = "no-store"
    return service.recruiters(session, actor, params)


@router.get("/ai-agreement", response_model=AgreementReport)
def ai_agreement(params: Params, response: Response, session: DB, actor: CurrentUser):
    response.headers["Cache-Control"] = "no-store"
    return service.agreement(session, actor, params)


@router.get(
    "/export.xlsx",
    response_class=Response,
    responses={200: {"content": {XLSX: {"schema": {"type": "string", "format": "binary"}}}}},
)
def export(params: Params, session: DB, actor: CurrentUser) -> Response:
    content, filename = export_report(session, actor, params)
    return Response(
        content=content,
        media_type=XLSX,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
