"""Aggregate-only workbook; personal CV contents never enter this export."""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from app.models import User
from app.models.enums import ActivityType
from app.reports import queries, service
from app.schemas.reports import Metrics, ReportInput
from app.services.export import STAGES

HEADERS = [
    "CV mới",
    "Đã sàng lọc",
    "Đã gửi đơn vị tuyển",
    "Phỏng vấn",
    "Đã đến giờ",
    "Sắp tới",
    "Offer",
    "Nhận việc",
    "Time-to-fill (ngày)",
    "Mẫu time-to-fill",
    "Mẫu time-to-fill không hợp lệ",
    "Job trễ hạn",
    "Phí đã biết (VND)",
    "Placement có phí",
    "Placement chưa có phí",
    "Đồng ý AI",
    "Không đồng ý AI",
    "Số phản hồi AI",
    "Tỉ lệ đồng thuận AI",
]
ACTIVITIES = dict(
    zip(
        ActivityType,
        [
            "Ghi chú",
            "Gọi điện",
            "Gửi email",
            "Đổi bước",
            "Nhận CV",
            "AI chấm điểm",
            "Phản hồi AI",
            "Đặt lịch phỏng vấn",
            "Tạo offer",
            "Hoàn thành việc",
        ],
        strict=True,
    )
)


def _values(metrics: Metrics) -> list:
    return [
        metrics.new_cvs,
        metrics.screened,
        metrics.submitted,
        metrics.interviews.total,
        metrics.interviews.elapsed,
        metrics.interviews.upcoming,
        metrics.offers,
        metrics.placements,
        metrics.time_to_fill.days,
        metrics.time_to_fill.sample_count,
        metrics.time_to_fill.excluded_count,
        metrics.overdue_jobs,
        metrics.placement_revenue.amount,
        metrics.placement_revenue.known_count,
        metrics.placement_revenue.missing_count,
        metrics.ai_agreement.agree,
        metrics.ai_agreement.disagree,
        metrics.ai_agreement.total,
        metrics.ai_agreement.rate,
    ]


def _sheet(workbook: Workbook, title: str, headers: list[str], rows) -> None:
    sheet = workbook.create_sheet(title)
    for values in [headers, *rows]:
        sheet.append(
            [
                ILLEGAL_CHARACTERS_RE.sub("", value) if isinstance(value, str) else value
                for value in values
            ]
        )
    for row in sheet:
        for cell in row:
            if isinstance(cell.value, str):
                # Force the OOXML string type, including =/+/-/@ names and controls.
                cell.value = ILLEGAL_CHARACTERS_RE.sub("", cell.value)
                cell.data_type = "s"
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in range(1, len(headers) + 1):
        sheet.column_dimensions[get_column_letter(column)].width = 28


def export_report(session: Session, actor: User, params: ReportInput) -> tuple[bytes, str]:
    report = service.summary(session, actor, params)
    start, end, filters, period = queries.prepare(session, actor, params, now=report.period.as_of)
    team = service.recruiter_rows(session, start, end, filters, period)
    workbook = Workbook()
    workbook.remove(workbook.active)
    _sheet(
        workbook,
        "Thông tin",
        ["Mục", "Giá trị"],
        [
            ["Định nghĩa KPI", "Bản nháp — chưa được duyệt"],
            ["Từ ngày (bao gồm)", period.from_date.isoformat()],
            ["Đến ngày (không bao gồm)", period.to_date.isoformat()],
            ["Múi giờ", period.timezone],
            ["Thời điểm truy vấn", period.as_of.astimezone(queries.VIETNAM).isoformat()],
            ["Người phụ trách", str(period.recruiter_id) if period.recruiter_id else "Tất cả"],
            ["Job", str(period.job_id) if period.job_id else "Tất cả"],
            ["Đơn vị tuyển", str(period.hiring_unit_id) if period.hiring_unit_id else "Tất cả"],
            ["Ô trống", "Chưa có dữ liệu hoặc không xác định; không phải số 0"],
            ["Phỏng vấn đã đến giờ", "Theo lịch đã qua; không xác nhận buổi phỏng vấn đã diễn ra"],
        ],
    )
    _sheet(workbook, "Tổng hợp", HEADERS, [_values(report.metrics)])
    _sheet(
        workbook,
        "Theo người phụ trách",
        ["Người phụ trách", *HEADERS],
        [
            [row.recruiter_name or "Chưa gán / hệ thống", *_values(row.metrics)]
            for row in team.items
        ],
    )
    _sheet(
        workbook,
        "Phễu",
        ["Bước", "Số hồ sơ", "Bước tiếp", "Số bước tiếp", "Tỉ lệ"],
        [
            [
                STAGES[row.stage],
                row.count,
                STAGES[row.next_stage] if row.next_stage is not None else None,
                row.next_count,
                row.conversion_rate,
            ]
            for row in report.metrics.funnel
        ],
    )
    _sheet(
        workbook,
        "Thời gian ở bước",
        ["Bước", "Trung vị (ngày)", "Số lượt hoàn tất"],
        [
            [STAGES[stage], metric.days, metric.sample_count]
            for stage, metric in report.metrics.stage_duration.items()
        ],
    )
    _sheet(
        workbook,
        "CV theo ngày",
        ["Ngày", "CV mới"],
        [[row.date.isoformat(), row.count] for row in report.new_cvs_by_day],
    )
    _sheet(
        workbook,
        "Hoạt động",
        ["Loại", "Số hoạt động"],
        [[ACTIVITIES[kind], count] for kind, count in report.metrics.activities.items()],
    )
    _sheet(
        workbook,
        "Hoạt động theo người",
        ["Người phụ trách", *ACTIVITIES.values()],
        [
            [
                row.recruiter_name or "Chưa gán / hệ thống",
                *[row.metrics.activities[kind] for kind in ActivityType],
            ]
            for row in team.items
        ],
    )
    output = BytesIO()
    workbook.save(output)
    return output.getvalue(), f"bao-cao-{period.from_date}-{period.to_date}.xlsx"
