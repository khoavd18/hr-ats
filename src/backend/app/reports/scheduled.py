"""Internal report snapshots. KPI definitions remain the T26 draft contract."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html import escape
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models import EmailMessage, User
from app.models.enums import EmailStatus
from app.models.users import UserRole
from app.reports import queries, service
from app.reports.export import ACTIVITIES
from app.schemas.reports import Metrics, ReportInput
from app.services.export import STAGES

ReportKind = Literal["daily", "weekly"]
MANAGERS = (UserRole.admin, UserRole.lead)
MISSING = "Chưa có dữ liệu"


def report_input(kind: ReportKind, now: datetime) -> ReportInput:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("An aware reporting time is required")
    day = now.astimezone(queries.VIETNAM).date()
    if kind == "daily":
        start, end = day, day + timedelta(days=1)
    elif kind == "weekly":
        end = day - timedelta(days=day.weekday())
        start = end - timedelta(days=7)
    else:
        raise ValueError("Unknown report kind")
    return ReportInput.model_validate({"from": start, "to": end})


def report_id(user_id: UUID, kind: ReportKind, start: date) -> UUID:
    digest = uuid5(NAMESPACE_URL, f"hr-ats/report/{kind}/{start.isoformat()}/{user_id}")
    return UUID(bytes=digest.bytes, version=4)


def report_marker(record_id: UUID, kind: ReportKind) -> str:
    return f"<{record_id}.report-{kind}@hr-ats.invalid>"


def report_kind(row: EmailMessage) -> ReportKind | None:
    # API drafts cannot set IDs, created_at or Message-ID. A null application
    # alone must never bypass human confirmation on candidate mail.
    if row.application_id is not None or row.template_id is not None:
        return None
    for kind in ("daily", "weekly"):
        params = report_input(kind, row.created_at)
        expected = report_id(row.created_by, kind, params.from_date)
        if row.id == expected and row.message_id == report_marker(expected, kind):
            return kind
    return None


def recipients(session: Session) -> list[User]:
    return list(
        session.scalars(
            select(User).where(User.is_active.is_(True), User.role.in_(MANAGERS)).order_by(User.id)
        )
    )


def number(value: int | float | None, *, percent: bool = False) -> str:
    if value is None:
        return MISSING
    if percent:
        return f"{value * 100:.1f}%".replace(".", ",")
    return (
        f"{value:,}".replace(",", ".")
        if isinstance(value, int)
        else f"{value:.2f}".replace(".", ",")
    )


def scalar_rows(metrics: Metrics) -> list[tuple[str, str]]:
    return [
        ("CV mới", number(metrics.new_cvs)),
        ("Đã sàng lọc", number(metrics.screened)),
        ("Đã gửi đơn vị tuyển", number(metrics.submitted)),
        ("Phỏng vấn", number(metrics.interviews.total)),
        ("Lịch đã đến giờ", number(metrics.interviews.elapsed)),
        ("Lịch sắp tới", number(metrics.interviews.upcoming)),
        ("Offer", number(metrics.offers)),
        ("Nhận việc", number(metrics.placements)),
        ("Thời gian tuyển trung vị (ngày)", number(metrics.time_to_fill.days)),
        ("Số mẫu thời gian tuyển", number(metrics.time_to_fill.sample_count)),
        ("Mẫu thời gian tuyển không hợp lệ", number(metrics.time_to_fill.excluded_count)),
        ("Phí placement đã biết (VND)", number(metrics.placement_revenue.amount)),
        ("Placement có phí", number(metrics.placement_revenue.known_count)),
        ("Placement chưa có phí", number(metrics.placement_revenue.missing_count)),
        ("Đồng ý AI", number(metrics.ai_agreement.agree)),
        ("Không đồng ý AI", number(metrics.ai_agreement.disagree)),
        ("Số phản hồi AI", number(metrics.ai_agreement.total)),
        ("Tỉ lệ đồng thuận AI", number(metrics.ai_agreement.rate, percent=True)),
    ]


def metric_rows(metrics: Metrics) -> list[tuple[str, str]]:
    rows = scalar_rows(metrics)
    for item in metrics.funnel:
        rows.append((f"Hồ sơ vào bước {STAGES[item.stage]}", number(item.count)))
        if item.next_stage is not None:
            rows.append(
                (
                    f"Chuyển {STAGES[item.stage]} → {STAGES[item.next_stage]}",
                    number(item.conversion_rate, percent=True),
                )
            )
    for stage, value in metrics.stage_duration.items():
        rows.append((f"Trung vị ngày ở bước {STAGES[stage]}", number(value.days)))
        rows.append((f"Số lượt hoàn tất {STAGES[stage]}", number(value.sample_count)))
    rows.extend((ACTIVITIES[kind], number(count)) for kind, count in metrics.activities.items())
    return rows


def table(headers: list[str], rows: list[list[str]]) -> str:
    return (
        '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">'
        "<thead><tr>"
        + "".join(f'<th scope="col">{escape(header)}</th>' for header in headers)
        + "</tr></thead><tbody>"
        + "".join(
            "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>" for row in rows
        )
        + "</tbody></table>"
    )


@dataclass(frozen=True)
class ReportMail:
    subject: str
    html: str
    params: ReportInput


def build_report(
    session: Session, actor: User, kind: ReportKind, now: datetime, settings: Settings
) -> ReportMail:
    if not actor.is_active or actor.role not in MANAGERS:
        raise AppError("FORBIDDEN", "Không có quyền xem báo cáo nhóm.", 403)
    params = report_input(kind, now)
    start, end, filters, period = queries.prepare(session, actor, params, now=now)
    metrics = queries.collect(session, start, end, filters)[None]
    team = service.recruiter_rows(session, start, end, filters, period)
    subject = "Báo cáo tuyển dụng ngày" if kind == "daily" else "Báo cáo tuyển dụng tuần"
    span = f"{params.from_date:%d/%m/%Y} – {params.to_date - timedelta(days=1):%d/%m/%Y}"
    subject += f" {span}"
    headers = ["Chỉ số", "Trong kỳ"]
    rows = [[label, value] for label, value in metric_rows(metrics)]
    comparison = ""
    if kind == "weekly":
        previous = queries.collect(session, start - timedelta(days=7), start, filters)[None]
        headers.append("Tuần trước nữa")
        for metric_row, (_, value) in zip(rows, metric_rows(previous), strict=True):
            metric_row.append(value)
        comparison = (
            f"<p>So với {params.from_date - timedelta(days=7):%d/%m/%Y} – "
            f"{params.from_date - timedelta(days=1):%d/%m/%Y}.</p>"
        )
    parts = [
        '<!doctype html><html lang="vi"><head><meta charset="utf-8">',
        f"<title>{escape(subject)}</title></head><body>",
        f"<h1>{escape(subject)}</h1>",
        "<p>Định nghĩa KPI: Bản nháp — chưa được duyệt.</p>",
        f"<p>Số liệu ghi nhận lúc {now.astimezone(queries.VIETNAM):%d/%m/%Y %H:%M} "
        "(giờ Việt Nam). Kỳ theo ngày, ngày kết thúc không bao gồm: "
        f"{params.to_date:%d/%m/%Y}.</p>",
        "<p>Chưa có dữ liệu không phải số 0. Phí chỉ gồm phần đã biết. "
        "Lịch đã đến giờ không xác nhận phỏng vấn đã diễn ra. "
        "Tỉ lệ chuyển bước có thể lớn hơn 100% do hồ sơ vào bước trong kỳ khác nhau.</p>",
        comparison,
        "<h2>Tổng hợp</h2>",
        table(headers, rows),
        "<h2>Theo người phụ trách</h2>",
    ]
    # Keep the team overview compact enough for ordinary email clients.
    parts.append(
        table(
            [
                "Người phụ trách",
                "CV mới",
                "Đã sàng lọc",
                "Đã gửi",
                "Phỏng vấn",
                "Offer",
                "Nhận việc",
                "Thời gian tuyển trung vị (ngày)",
                "Job trễ hạn hiện tại",
                "Phí đã biết (VND)",
                "Đồng thuận AI",
            ],
            [
                [
                    row.recruiter_name or "Chưa gán / hệ thống",
                    *map(
                        number,
                        [
                            row.metrics.new_cvs,
                            row.metrics.screened,
                            row.metrics.submitted,
                            row.metrics.interviews.total,
                            row.metrics.offers,
                            row.metrics.placements,
                            row.metrics.time_to_fill.days,
                            row.metrics.overdue_jobs,
                            row.metrics.placement_revenue.amount,
                        ],
                    ),
                    number(row.metrics.ai_agreement.rate, percent=True),
                ]
                for row in team.items
            ],
        )
    )
    parts.append(
        f"<p>Job trễ hạn hiện tại: {metrics.overdue_jobs}. "
        "Đây là trạng thái lúc lập báo cáo, không phải trạng thái cuối kỳ trước.</p>"
    )
    if kind == "weekly":
        parts.extend(
            [
                "<h2>Tối đa 5 Job trễ hạn lâu nhất</h2>",
                table(
                    ["Job", "Hạn tuyển"],
                    [list(row) for row in queries.top_overdue_jobs(session, filters)],
                ),
            ]
        )
    parts.extend(
        [
            f'<p><a href="{escape(settings.frontend_origin + "/reports", quote=True)}">'
            "Mở trang Báo cáo</a></p>",
            "</body></html>",
        ]
    )
    return ReportMail(subject, "".join(parts), params)


def queue_reports(
    session: Session, kind: ReportKind, now: datetime, settings: Settings
) -> list[tuple[str, str, str]]:
    session.execute(select(func.pg_advisory_xact_lock(280028)))
    params = report_input(kind, now)
    messages = []
    report = None
    for actor in recipients(session):
        record_id = report_id(actor.id, kind, params.from_date)
        row = session.get(EmailMessage, record_id)
        if row is None:
            if report is None:
                report = build_report(session, actor, kind, now, settings)
            row = EmailMessage(
                id=record_id,
                created_at=now,
                created_by=actor.id,
                to_email=actor.email,
                subject=report.subject,
                body_html=report.html,
                message_id=report_marker(record_id, kind),
                status=EmailStatus.queued,
                scheduled_for=now,
            )
            session.add(row)
        if (
            row.deleted_at is None
            and row.status == EmailStatus.queued
            and row.scheduled_for
            and row.message_id
        ):
            messages.append((str(row.id), row.message_id, row.scheduled_for.isoformat()))
    session.commit()
    return messages
