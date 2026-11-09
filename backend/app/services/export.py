"""Job ranking workbook export with the same eligibility and ordering as T14."""

import io
import re
import unicodedata
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.applications import Application
from app.models.candidates import Candidate
from app.models.enums import AiLevel, ApplicationStage, ProcessingStatus
from app.models.users import User
from app.services.applications import accessible_job
from app.services.audit import record_audit
from app.services.ranking import visible_applications

LEVELS = {
    AiLevel.high: "Cao",
    AiLevel.medium: "Trung bình",
    AiLevel.low: "Thấp",
    AiLevel.insufficient: "Chưa đủ thông tin",
}
STAGES = {
    ApplicationStage.new: "Mới",
    ApplicationStage.screening: "Sàng lọc",
    ApplicationStage.submitted: "Đã trình",
    ApplicationStage.interview: "Phỏng vấn",
    ApplicationStage.offer: "Đề nghị tuyển dụng",
    ApplicationStage.hired: "Đã nhận việc",
    ApplicationStage.rejected: "Từ chối",
    ApplicationStage.withdrawn: "Đã rút",
}
HEADERS = [
    "Họ tên",
    "Email",
    "Số điện thoại",
    "Mức AI",
    "Điểm",
    "Lý do",
    "Kỹ năng",
    "Số năm kinh nghiệm",
    "Bước tuyển dụng",
    "Ngày nhận",
]


def _excel_text(value: str | None) -> str:
    """Prevent user supplied text from becoming an Excel formula."""
    value = value or ""
    return f"'{value}" if value.lstrip().startswith(("=", "+", "-", "@")) else value


def _slug(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-") or "job"


def export_job(session: Session, actor: User, job_id: UUID, ip: str | None) -> tuple[bytes, str]:
    job = accessible_job(session, actor, job_id)
    query = visible_applications().where(Application.job_id == job.id)
    level_order = case(
        (Application.ai_status != ProcessingStatus.done, 4),
        (Application.ai_level == AiLevel.high, 0),
        (Application.ai_level == AiLevel.medium, 1),
        (Application.ai_level == AiLevel.low, 2),
        else_=3,
    )
    rows = session.execute(
        query.with_only_columns(Application, Candidate).order_by(
            level_order,
            Application.ai_score.desc().nulls_last(),
            Application.created_at.desc(),
            Application.id,
        )
    ).all()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Ứng viên"
    sheet.append(HEADERS)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.freeze_panes = "A2"
    widths = [26, 32, 20, 22, 12, 60, 42, 22, 26, 18]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[chr(64 + index)].width = width

    for application, candidate in rows:
        reasons = "; ".join(str(reason) for reason in (application.ai_reasons or []))
        received = application.created_at.astimezone(ZoneInfo(get_settings().tz)).date()
        sheet.append(
            [
                _excel_text(candidate.full_name),
                _excel_text(candidate.email),
                _excel_text(candidate.phone),
                LEVELS.get(application.ai_level, "Chưa đủ thông tin")
                if application.ai_status == ProcessingStatus.done
                else "Chưa đánh giá",
                application.ai_score,
                _excel_text(reasons),
                _excel_text(", ".join(candidate.skills or [])),
                float(candidate.years_experience)
                if candidate.years_experience is not None
                else None,
                STAGES[application.stage],
                received,
            ]
        )
    for cell in sheet["J"][1:]:
        cell.number_format = "yyyy-mm-dd"

    record_audit(
        session,
        actor_id=actor.id,
        action="candidate.export",
        entity="job",
        entity_id=job.id,
        ip=ip,
        details={"record_count": len(rows), "job_id": str(job.id)},
    )
    output = io.BytesIO()
    workbook.save(output)
    session.commit()
    today = datetime.now(ZoneInfo(get_settings().tz)).date().isoformat()
    return output.getvalue(), f"ung-vien-{_slug(job.title)}-{today}.xlsx"
