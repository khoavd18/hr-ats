"""T15: profile boundaries and human actions against real PostgreSQL, synthetic data."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.security import hash_password
from app.models import (
    Activity,
    Application,
    AuditLog,
    Candidate,
    CvFile,
    HiringUnit,
    Job,
    JobMember,
    User,
)
from app.models.applications import AiFeedback
from app.models.enums import ActivityType, AiLevel, HiringUnitKind, ProcessingStatus
from app.models.users import UserRole
from app.services import profile
from tests.auth_helpers import PASSWORD, csrf_headers, sign_in


@pytest.fixture
def records(db_session, account):
    candidate = Candidate(
        full_name="Ứng viên mô phỏng",
        retention_until=date(2099, 1, 1),
        anonymized_text="[TÊN] Python",
        skills=["python"],
    )
    unit = HiringUnit(name="Đơn vị mô phỏng", kind=HiringUnitKind.department)
    recruiter = User(
        email="profile@example.invalid",
        full_name="HR mô phỏng",
        role=UserRole.recruiter,
        password_hash=hash_password(PASSWORD),
    )
    db_session.add_all([candidate, unit, recruiter])
    db_session.flush()
    job = Job(
        title="Vị trí mô phỏng",
        description="Mô tả giả",
        owner_id=account.id,
        hiring_unit_id=unit.id,
    )
    db_session.add(job)
    db_session.flush()
    application = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        owner_id=recruiter.id,
        ai_status=ProcessingStatus.done,
        ai_level=AiLevel.high,
        ai_score=90,
        ai_model="PRIVATE_MODEL",
        ai_prompt_version="PRIVATE_VERSION",
    )
    db_session.add(application)
    db_session.flush()
    docx = CvFile(
        candidate_id=candidate.id,
        storage_key="PRIVATE_KEY",
        original_filename="cv-gia.docx",
        mime_type=profile.DOCX,
        sha256="a" * 64,
        size_bytes=10,
        extracted_text="Nội dung CV giả",
        job_id=job.id,
        uploaded_by=account.id,
        status=ProcessingStatus.done,
        parsed_json={"private": "PRIVATE_PARSE"},
    )
    pdf = CvFile(
        candidate_id=candidate.id,
        storage_key="PRIVATE_KEY_2",
        original_filename="cv-gia.pdf",
        mime_type="application/pdf",
        sha256="b" * 64,
        size_bytes=10,
        extracted_text="PRIVATE_PDF_TEXT",
        job_id=job.id,
        status=ProcessingStatus.done,
    )
    db_session.add_all([docx, pdf])
    db_session.commit()
    return SimpleNamespace(
        candidate=candidate,
        job=job,
        application=application,
        recruiter=recruiter,
        docx=docx,
        pdf=pdf,
    )


def path(records, suffix=""):
    return f"/api/v1/applications/{records.application.id}{suffix}"


def post(client, records, suffix, body):
    return client.post(path(records, suffix), json=body, headers=csrf_headers(client))


def test_detail_records_candidate_view_and_exposes_only_authorized_docx_text(
    client, account, records, db_session
):
    sign_in(client)
    response = client.get(path(records), headers={"X-Forwarded-For": "192.0.2.4"})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["candidate"]["full_name"] == "Ứng viên mô phỏng"
    assert data["application"]["ai_score"] == 90
    files = {f["mime_type"]: f for f in data["cv_files"]}
    assert files[profile.DOCX]["extracted_text"] == "Nội dung CV giả"
    assert files["application/pdf"]["extracted_text"] is None
    for secret in (
        "PRIVATE_KEY",
        "PRIVATE_PARSE",
        "PRIVATE_PDF_TEXT",
        "anonymized_text",
        "embedding",
        "search_tsv",
    ):
        assert secret not in response.text
    audit = db_session.scalars(select(AuditLog).where(AuditLog.entity == "candidate")).one()
    assert (
        audit.action == "view"
        and audit.entity_id == records.candidate.id
        and audit.actor_id == account.id
    )
    assert audit.ip != "192.0.2.4"
    assert data["feedback"] is None and data["activities"] == []


def test_feedback_second_submission_overwrites_same_user_without_changing_ai_or_stage(
    client, account, records, db_session
):
    sign_in(client)
    first = post(client, records, "/ai-feedback", {"verdict": "agree", "comment": "Nhận xét giả"})
    assert first.status_code == 200
    second = post(
        client,
        records,
        "/ai-feedback",
        {"verdict": "disagree", "corrected_level": "low", "comment": "Đã kiểm tra lại"},
    )
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    assert (
        second.json()["comment"] == "Đã kiểm tra lại" and second.json()["corrected_level"] == "low"
    )
    assert db_session.scalar(select(func.count()).select_from(AiFeedback)) == 1
    events = list(db_session.scalars(select(Activity)))
    assert len(events) == 2 and all(a.type == ActivityType.ai_feedback for a in events)
    assert all("comment" not in a.payload for a in events)
    db_session.refresh(records.application)
    assert records.application.ai_level == AiLevel.high and records.application.ai_score == 90
    assert (
        records.application.stage == "new" and records.application.owner_id == records.recruiter.id
    )
    assert client.get(path(records)).json()["feedback"] == second.json()
    third = post(client, records, "/ai-feedback", {"verdict": "agree"})
    assert third.json()["corrected_level"] is None and third.json()["comment"] is None


def test_feedback_is_per_user_and_activity_history_includes_notes(client, records, db_session):
    sign_in(client)
    post(client, records, "/ai-feedback", {"verdict": "agree"})
    response = post(
        client, records, "/notes", {"text": "  Ghi chú giả <script>khong-chay()</script>  "}
    )
    assert response.status_code == 201 and response.headers["cache-control"] == "no-store"
    assert response.json()["payload"]["text"] == "Ghi chú giả <script>khong-chay()</script>"
    db_session.add(JobMember(job_id=records.job.id, user_id=records.recruiter.id))
    db_session.commit()
    sign_in(client, records.recruiter.email)
    assert client.get(path(records)).json()["feedback"] is None
    assert (
        post(
            client, records, "/ai-feedback", {"verdict": "disagree", "corrected_level": "medium"}
        ).status_code
        == 200
    )
    assert db_session.scalar(select(func.count()).select_from(AiFeedback)) == 2
    data = client.get(path(records)).json()
    assert len(data["activities"]) == 3
    assert data["feedback"]["user_id"] == str(records.recruiter.id)


@pytest.mark.parametrize("role", ["admin", "lead", "owner", "member", "outsider", "revoked"])
def test_every_endpoint_checks_current_job_scope(client, records, db_session, role):
    actor = records.recruiter
    if role == "admin":
        actor.role = UserRole.admin
    elif role == "lead":
        actor.role = UserRole.lead
    elif role == "owner":
        records.job.owner_id = actor.id
    elif role in {"member", "revoked"}:
        member = JobMember(job_id=records.job.id, user_id=actor.id)
        db_session.add(member)
        db_session.flush()
        if role == "revoked":
            db_session.delete(member)
    db_session.commit()
    sign_in(client, actor.email)
    expected = 403 if role in {"outsider", "revoked"} else 200
    assert client.get(path(records)).status_code == expected
    assert post(client, records, "/ai-feedback", {"verdict": "agree"}).status_code == expected
    assert post(client, records, "/notes", {"text": "Ghi chú giả"}).status_code == (
        201 if expected == 200 else expected
    )
    response = client.patch(
        f"/api/v1/candidates/{records.candidate.id}",
        headers=csrf_headers(client),
        json={"full_name": "Tên sửa giả"},
    )
    assert response.status_code == expected
    if expected == 403:
        assert db_session.scalar(select(func.count()).select_from(Activity)) == 0
        assert db_session.scalar(select(func.count()).select_from(AuditLog)) == 0


@pytest.mark.parametrize("state", ["missing", "deleted", "candidate_deleted", "merged", "expired"])
def test_ineligible_profiles_cannot_be_read_or_mutated(client, records, db_session, state):
    if state == "missing":
        records.application.id = uuid4()
        # Keep an absent URL without modifying persisted PK/FKs.
        db_session.expunge(records.application)
    elif state == "deleted":
        records.application.deleted_at = datetime.now(UTC)
    elif state == "candidate_deleted":
        records.candidate.deleted_at = datetime.now(UTC)
    elif state == "merged":
        records.candidate.merged_into_id = records.candidate.id
    else:
        records.candidate.retention_until = date(2000, 1, 1)
    db_session.commit()
    sign_in(client)
    assert client.get(path(records)).status_code == 404
    assert post(client, records, "/ai-feedback", {"verdict": "agree"}).status_code == 404
    assert post(client, records, "/notes", {"text": "Ghi chú giả"}).status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"verdict": "other"},
        {"verdict": "disagree"},
        {"verdict": "agree", "corrected_level": "low"},
        {"verdict": "agree", "user_id": str(uuid4())},
        {"verdict": "agree", "comment": " "},
    ],
)
def test_feedback_validation(client, records, body):
    sign_in(client)
    assert post(client, records, "/ai-feedback", body).status_code == 422


@pytest.mark.parametrize(
    "body", [{"text": " "}, {"text": "a" * 10001}, {"text": "ok", "actor_id": str(uuid4())}]
)
def test_note_validation(client, records, body):
    sign_in(client)
    assert post(client, records, "/notes", body).status_code == 422


def test_candidate_patch_validates_and_preserves_original_cv_and_ai(client, records, db_session):
    sign_in(client)
    url = f"/api/v1/candidates/{records.candidate.id}"
    for body in (
        {"full_name": None},
        {"full_name": " "},
        {"email": "bad"},
        {"years_experience": -1},
        {"years_experience": "1.234"},
        {"skills": None},
        {"consent_at": "2026-01-01"},
        {"anonymized_text": "bad"},
    ):
        assert client.patch(url, json=body, headers=csrf_headers(client)).status_code == 422
    response = client.patch(
        url,
        json={
            "full_name": " Tên giả đã sửa ",
            "email": " SAMPLE@EXAMPLE.INVALID ",
            "phone": None,
            "skills": ["python", "sql"],
            "years_experience": "3.25",
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["full_name"] == "Tên giả đã sửa" and data["email"] == "sample@example.invalid"
    assert data["years_experience"] == "3.25" and data["skills"] == ["python", "sql"]
    assert data["consent_at"] is None
    db_session.refresh(records.candidate)
    assert records.candidate.anonymized_text == "[TÊN] Python"
    db_session.refresh(records.application)
    assert records.application.ai_score == 90


def test_auth_csrf_missing_records_and_no_private_log_content(client, records, caplog):
    assert client.get(path(records)).status_code == 401
    sign_in(client)
    assert client.post(path(records, "/notes"), json={"text": "Ghi chú giả"}).status_code == 403
    assert client.post(path(records, "/ai-feedback"), json={"verdict": "agree"}).status_code == 403
    assert (
        client.patch(
            f"/api/v1/candidates/{records.candidate.id}", json={"full_name": "Tên giả"}
        ).status_code
        == 403
    )
    assert client.get(f"/api/v1/applications/{uuid4()}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/candidates/{uuid4()}",
            json={"full_name": "Tên giả"},
            headers=csrf_headers(client),
        ).status_code
        == 404
    )
    post(client, records, "/notes", {"text": "SYNTHETIC_PRIVATE_NOTE"})
    post(
        client,
        records,
        "/ai-feedback",
        {"verdict": "agree", "comment": "SYNTHETIC_PRIVATE_COMMENT"},
    )
    client.get(path(records))
    assert "SYNTHETIC_PRIVATE_NOTE" not in caplog.text
    assert "SYNTHETIC_PRIVATE_COMMENT" not in caplog.text
    assert "Nội dung CV giả" not in caplog.text


def test_failed_activity_rolls_back_feedback(client, records, db_session, monkeypatch):
    sign_in(client)

    def fail(*args, **kwargs):
        raise RuntimeError("SYNTHETIC_PRIVATE_ERROR")

    monkeypatch.setattr(profile, "log_activity", fail)
    response = post(client, records, "/ai-feedback", {"verdict": "agree"})
    assert response.status_code == 500 and "SYNTHETIC_PRIVATE_ERROR" not in response.text
    assert db_session.scalar(select(func.count()).select_from(AiFeedback)) == 0
