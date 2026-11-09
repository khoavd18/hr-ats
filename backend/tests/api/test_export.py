"""T17: workbook export and minimal audit metadata."""

import re
from datetime import date
from io import BytesIO

from openpyxl import load_workbook
from sqlalchemy import select

from app.models import Application, AuditLog
from app.models.enums import AiLevel, ApplicationStage, ProcessingStatus
from tests.auth_helpers import sign_in


def test_job_export_workbook_and_audit(client, account, records, db_session):
    candidate = records.candidate
    candidate.full_name = '=HYPERLINK("https://example.invalid","Giả")'
    candidate.email = "ung-vien-gia@example.invalid"
    candidate.phone = "+84900000000"
    candidate.skills = ["Python", "SQL"]
    candidate.years_experience = 4.5
    candidate.retention_until = date(2099, 1, 1)
    application = Application(
        candidate_id=candidate.id,
        job_id=records.job.id,
        owner_id=account.id,
        stage=ApplicationStage.interview,
        ai_status=ProcessingStatus.done,
        ai_level=AiLevel.high,
        ai_score=91,
        ai_reasons=["Kinh nghiệm phù hợp", "Có kỹ năng Python"],
    )
    db_session.add(application)
    db_session.commit()

    sign_in(client)
    response = client.get(f"/api/v1/jobs/{records.job.id}/export.xlsx")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert re.search(
        r'attachment; filename="ung-vien-python-\d{4}-\d{2}-\d{2}\.xlsx"',
        response.headers["content-disposition"],
    )
    workbook = load_workbook(BytesIO(response.content), data_only=True)
    sheet = workbook["Ứng viên"]
    assert sheet.freeze_panes == "A2"
    assert sheet["A1"].font.bold is True
    assert sheet.column_dimensions["A"].width >= 20
    rows = list(sheet.values)
    assert rows[0] == (
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
    )
    assert len(rows) == 2
    assert rows[1][0] == '\'=HYPERLINK("https://example.invalid","Giả")'
    assert rows[1][1:5] == ("ung-vien-gia@example.invalid", "+84900000000", "Cao", 91)
    assert rows[1][5:9] == (
        "Kinh nghiệm phù hợp; Có kỹ năng Python",
        "Python, SQL",
        4.5,
        "Phỏng vấn",
    )
    assert rows[1][9] is not None

    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "candidate.export", AuditLog.entity_id == records.job.id
        )
    )
    assert audit is not None
    assert audit.details == {"record_count": 1, "job_id": str(records.job.id)}
    assert candidate.full_name not in str(audit.details)
    workbook.close()
