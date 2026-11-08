from contextlib import contextmanager
from datetime import UTC, date, datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID, uuid4
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from sqlalchemy import func, select

from app.ai.extract import ExtractResult
from app.api.cv_files import storage_dependency
from app.core.errors import AppError
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
)
from app.models.enums import ActivityType, ExtractionMethod, HiringUnitKind, ProcessingStatus
from app.models.users import User, UserRole
from app.services import cv_files as cv_service
from app.services.cv_files import QUEUE_ERROR
from app.services.cv_validation import MAX_FILE_BYTES
from app.storage import LocalStorage, StorageError
from app.workers import tasks
from tests.auth_helpers import PASSWORD, csrf_headers, sign_in
from tests.cv_helpers import PDF, docx_bytes, image_bytes

BASE = "/api/v1/cv-files"


@pytest.fixture(autouse=True)
def cv_runtime(app, db_session, tmp_path, monkeypatch):
    storage = LocalStorage(tmp_path / "cv-storage")
    app.dependency_overrides[storage_dependency] = lambda: storage

    @contextmanager
    def worker_session():
        yield db_session

    monkeypatch.setattr(tasks, "worker_session", worker_session)
    monkeypatch.setattr(tasks, "build_storage", lambda settings: storage)
    # T07 tests upload/access/queue behaviour, including a blank 10px image.
    # Supply an explicit extraction outcome here; T10's pipeline suite exercises
    # real extraction and rejects corrupt/empty documents independently.
    monkeypatch.setattr(
        tasks,
        "extract_text",
        lambda data, mime: ExtractResult(
            text="Họ tên: Ứng viên mô phỏng\nKỹ năng: Python",
            method=ExtractionMethod.pdf_text,
            page_count=1,
        ),
    )
    return storage


@pytest.fixture
def scope(db_session, account):
    recruiter = User(
        email="uploader@example.invalid",
        full_name="Recruiter giả",
        role=UserRole.recruiter,
        password_hash=hash_password(PASSWORD),
    )
    outsider = User(
        email="outsider@example.invalid",
        full_name="Recruiter ngoài giả",
        role=UserRole.recruiter,
        password_hash=hash_password(PASSWORD),
    )
    unit = HiringUnit(name="Đơn vị mô phỏng", kind=HiringUnitKind.department)
    db_session.add_all([recruiter, outsider, unit])
    db_session.flush()
    job = Job(
        hiring_unit_id=unit.id,
        title="Vị trí mô phỏng",
        description="Yêu cầu mô phỏng",
        owner_id=account.id,
    )
    db_session.add(job)
    db_session.flush()
    member = JobMember(job_id=job.id, user_id=recruiter.id)
    db_session.add(member)
    db_session.commit()
    return SimpleNamespace(recruiter=recruiter, outsider=outsider, job=job, member=member)


def upload(client, files=None, job_id=None, **kwargs):
    return client.post(
        BASE,
        files=files or [("files", ("synthetic.pdf", PDF, "application/pdf"))],
        data={"job_id": str(job_id)} if job_id else {},
        headers=csrf_headers(client),
        **kwargs,
    )


def one_file(response):
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["error"] is None, item
    return item["cv_file"]


def test_mixed_upload_duplicate_status_download_and_audit(
    client, account, scope, db_session, cv_runtime, caplog
):
    assert sign_in(client, scope.recruiter.email).status_code == 200
    source = [PDF, docx_bytes(), image_bytes()]
    files = [
        ("files", (f"synthetic-{index}.bin", data, "application/octet-stream"))
        for index, data in enumerate(source)
    ]
    files.append(("files", ("renamed.pdf", b"MZ synthetic executable", "application/pdf")))
    response = upload(client, files, scope.job.id)
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [item["index"] for item in items] == [0, 1, 2, 3]
    assert all(
        item["cv_file"]["status"] == "pending" and item["error"] is None and not item["duplicate"]
        for item in items[:3]
    )
    assert items[3]["cv_file"] is None
    assert items[3]["error"] == {
        "code": "INVALID_FILE_TYPE",
        "message": "Chỉ chấp nhận tệp PDF, DOCX, JPG hoặc PNG hợp lệ.",
    }
    assert db_session.scalar(select(func.count()).select_from(CvFile)) == 3
    # T12 also scores the three applications. Keep the T07 upload assertions
    # scoped to cv_uploaded, and verify the additional scoring activities too.
    activities = db_session.scalars(
        select(Activity).where(Activity.type == ActivityType.cv_uploaded)
    ).all()
    assert len(activities) == 3
    assert all(
        row.type == ActivityType.cv_uploaded
        and row.actor_id == scope.recruiter.id
        and row.job_id == scope.job.id
        and set(row.payload) == {"cv_file_id"}
        for row in activities
    )
    duplicate = upload(client, [files[0]], scope.job.id).json()["items"][0]
    assert duplicate["duplicate"] and duplicate["cv_file"]["id"] == items[0]["cv_file"]["id"]
    assert db_session.scalar(select(func.count()).select_from(CvFile)) == 3
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(Activity)
            .where(Activity.type == ActivityType.cv_uploaded)
        )
        == 3
    )
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(Activity)
            .where(Activity.type == ActivityType.ai_scored)
        )
        == 3
    )
    assert db_session.scalar(select(func.count()).select_from(Application)) == 3
    assert len(list(cv_runtime.root.iterdir())) == 3
    for index, item in enumerate(items[:3]):
        cv_file = item["cv_file"]
        status = client.get(f"{BASE}/{cv_file['id']}")
        assert status.status_code == 200 and status.json()["status"] == "done"
        assert status.headers["cache-control"] == "no-store"
        assert not {"storage_key", "extracted_text", "parsed_json", "error"} & status.json().keys()
        download = client.get(f"{BASE}/{cv_file['id']}/download")
        assert download.status_code == 200 and download.content == source[index]
        assert download.headers["content-type"] == cv_file["mime_type"]
        assert download.headers["x-content-type-options"] == "nosniff"
        assert download.headers["cache-control"] == "no-store"
        assert "attachment;" in download.headers["content-disposition"]
        assert "synthetic-" not in download.headers["content-disposition"]
        audit = db_session.scalar(
            select(AuditLog).where(
                AuditLog.entity_id == UUID(cv_file["id"]), AuditLog.action == "download"
            )
        )
        assert audit.entity == "cv_file" and audit.actor_id == scope.recruiter.id
    assert "MZ synthetic executable" not in caplog.text and "renamed.pdf" not in caplog.text


def test_unauthorized_recruiter_cannot_read_download_or_probe_duplicate(
    client, account, scope, db_session
):
    sign_in(client)
    cv_file = one_file(upload(client, job_id=scope.job.id))
    sign_in(client, scope.outsider.email)
    for suffix in ("", "/download"):
        assert client.get(f"{BASE}/{cv_file['id']}{suffix}").status_code == 403
    duplicate = upload(client).json()["items"][0]
    assert duplicate["cv_file"] is None and duplicate["error"]["code"] == "FORBIDDEN"
    assert db_session.scalar(select(func.count()).select_from(AuditLog)) == 0
    assert upload(client, job_id=scope.job.id).status_code == 403


def test_membership_revocation_and_owner_scope(client, account, scope, db_session):
    sign_in(client, scope.recruiter.email)
    cv_file = one_file(upload(client, job_id=scope.job.id))
    assert client.get(f"{BASE}/{cv_file['id']}").status_code == 200
    db_session.delete(scope.member)
    db_session.commit()
    assert client.get(f"{BASE}/{cv_file['id']}/download").status_code == 403
    scope.job.owner_id = scope.recruiter.id
    db_session.commit()
    assert client.get(f"{BASE}/{cv_file['id']}/download").status_code == 200


def test_unassigned_file_is_private_to_uploader_admin_and_lead(client, account, scope, db_session):
    sign_in(client, scope.recruiter.email)
    cv_file = one_file(upload(client))
    assert client.get(f"{BASE}/{cv_file['id']}/download").status_code == 200
    sign_in(client, scope.outsider.email)
    assert client.get(f"{BASE}/{cv_file['id']}").status_code == 403
    scope.outsider.role = UserRole.lead
    db_session.commit()
    sign_in(client, scope.outsider.email)
    assert client.get(f"{BASE}/{cv_file['id']}/download").status_code == 200
    sign_in(client)
    assert client.get(f"{BASE}/{cv_file['id']}/download").status_code == 200


def test_candidate_application_grants_access_and_soft_deletion_hides_file(
    client, account, scope, db_session
):
    sign_in(client)
    uploaded = one_file(upload(client))
    cv_file = db_session.get(CvFile, UUID(uploaded["id"]))
    candidate = Candidate(full_name="Ứng viên mô phỏng", retention_until=date(2028, 1, 1))
    db_session.add(candidate)
    db_session.flush()
    cv_file.candidate_id = candidate.id
    application = Application(candidate_id=candidate.id, job_id=scope.job.id, owner_id=account.id)
    db_session.add(application)
    db_session.commit()
    sign_in(client, scope.recruiter.email)
    assert client.get(f"{BASE}/{cv_file.id}/download").status_code == 200
    application.deleted_at = datetime.now(UTC)
    db_session.commit()
    assert client.get(f"{BASE}/{cv_file.id}/download").status_code == 403
    candidate.deleted_at = datetime.now(UTC)
    db_session.commit()
    sign_in(client)
    assert client.get(f"{BASE}/{cv_file.id}").status_code == 404


def test_soft_deleted_file_is_not_resurrected_by_duplicate(client, account, db_session):
    sign_in(client)
    uploaded = one_file(upload(client))
    cv_file = db_session.get(CvFile, UUID(uploaded["id"]))
    cv_file.deleted_at = datetime.now(UTC)
    db_session.commit()
    assert client.get(f"{BASE}/{cv_file.id}").status_code == 404
    assert client.get(f"{BASE}/{cv_file.id}/download").status_code == 404
    assert upload(client).json()["items"][0]["error"]["code"] == "NOT_FOUND"
    assert db_session.scalar(select(func.count()).select_from(CvFile)) == 1


def test_jpeg_size_macro_and_batch_limits(client, account, db_session):
    sign_in(client)
    assert (
        one_file(upload(client, [("files", ("synthetic.jpg", image_bytes("JPEG"), "image/jpeg"))]))[
            "mime_type"
        ]
        == "image/jpeg"
    )
    oversized = PDF + b" " * MAX_FILE_BYTES
    rejected = upload(
        client,
        [
            ("files", ("large.pdf", oversized, "application/pdf")),
            ("files", ("synthetic.DOCM", PDF, "application/pdf")),
        ],
    )
    assert [item["error"]["code"] for item in rejected.json()["items"]] == [
        "FILE_TOO_LARGE",
        "MACRO_NOT_ALLOWED",
    ]
    files = [("files", ("synthetic.pdf", PDF, "application/pdf"))] * 51
    assert upload(client, files).status_code == 422
    assert upload(client, files[:50]).status_code == 200
    assert db_session.scalar(select(func.count()).select_from(CvFile)) == 2


def test_renamed_macro_docx_is_rejected_at_api(client, account):
    sign_in(client)
    output = BytesIO()
    with ZipFile(BytesIO(docx_bytes())) as source, ZipFile(output, "w", ZIP_DEFLATED) as target:
        for entry in source.infolist():
            target.writestr(entry.filename, source.read(entry.filename))
        target.writestr("word/vbaProject.bin", b"synthetic macro marker")
    response = upload(client, [("files", ("renamed.docx", output.getvalue(), "application/zip"))])
    assert response.json()["items"][0]["error"]["code"] == "MACRO_NOT_ALLOWED"


def test_auth_csrf_invalid_batch_and_missing_file(client, account):
    file_id = uuid4()
    assert client.get(f"{BASE}/{file_id}").status_code == 401
    assert client.get(f"{BASE}/{file_id}/download").status_code == 401
    sign_in(client)
    assert client.post(BASE, files={"files": ("synthetic.pdf", PDF)}).status_code == 403
    assert client.post(BASE, headers=csrf_headers(client)).status_code == 422
    assert upload(client, job_id=uuid4()).status_code == 404
    assert client.get(f"{BASE}/{file_id}").status_code == 404
    assert client.get(f"{BASE}/{file_id}/download").status_code == 404
    assert client.get(f"{BASE}/invalid-id").status_code == 422
    assert (
        client.post(
            BASE, files={"other": ("synthetic.pdf", PDF)}, headers=csrf_headers(client)
        ).status_code
        == 422
    )
    assert (
        client.post(
            BASE,
            files={"files": ("synthetic.pdf", PDF)},
            data={"job_id": "invalid"},
            headers=csrf_headers(client),
        ).status_code
        == 422
    )


def test_queue_failure_is_safe_recoverable_and_does_not_duplicate_activity(
    client, account, db_session, monkeypatch
):
    sign_in(client)
    original_delay = tasks.process_cv_file.delay

    def fail(*args):
        raise RuntimeError("synthetic private broker details")

    monkeypatch.setattr(tasks.process_cv_file, "delay", fail)
    cv_file = one_file(upload(client))
    assert cv_file["status"] == "failed"
    assert db_session.get(CvFile, UUID(cv_file["id"])).error == QUEUE_ERROR
    monkeypatch.setattr(tasks.process_cv_file, "delay", original_delay)
    retried = upload(client).json()["items"][0]
    assert retried["duplicate"] and retried["cv_file"]["id"] == cv_file["id"]
    assert client.get(f"{BASE}/{cv_file['id']}").json()["status"] == "done"
    assert db_session.scalar(select(func.count()).select_from(Activity)) == 1


def test_storage_failure_and_missing_object_do_not_record_download(
    client, account, db_session, cv_runtime, monkeypatch
):
    sign_in(client)
    original_put = cv_runtime.put

    def fail(*args):
        raise StorageError("synthetic internal path")

    monkeypatch.setattr(cv_runtime, "put", fail)
    result = upload(client).json()["items"][0]
    assert result["cv_file"] is None and result["error"]["code"] == "STORAGE_UNAVAILABLE"
    assert db_session.scalar(select(func.count()).select_from(CvFile)) == 0
    monkeypatch.setattr(cv_runtime, "put", original_put)
    uploaded = one_file(upload(client))
    cv_file = db_session.get(CvFile, UUID(uploaded["id"]))
    cv_runtime.delete(cv_file.storage_key)
    response = client.get(f"{BASE}/{cv_file.id}/download")
    assert response.status_code == 503 and "synthetic" not in response.text
    assert db_session.scalar(select(func.count()).select_from(AuditLog)) == 0


def test_worker_is_idempotent_and_ignores_deleted_or_unknown_records(client, account, db_session):
    sign_in(client)
    uploaded = one_file(upload(client))
    cv_file = db_session.get(CvFile, UUID(uploaded["id"]))
    tasks.process_cv_file.delay(str(cv_file.id))
    assert cv_file.status == ProcessingStatus.done
    cv_file.status = ProcessingStatus.pending
    cv_file.deleted_at = datetime.now(UTC)
    db_session.commit()
    tasks.process_cv_file.delay(str(cv_file.id))
    tasks.process_cv_file.delay(str(uuid4()))
    assert cv_file.status == ProcessingStatus.pending


def test_db_failure_rolls_back_activity_and_cleans_new_storage_object(
    account, db_session, cv_runtime, monkeypatch
):
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic transaction failure")

    monkeypatch.setattr(cv_service, "log_activity", fail)
    with pytest.raises(RuntimeError, match="synthetic transaction failure"):
        cv_service.upload_file(
            db_session,
            account,
            cv_runtime,
            data=PDF,
            filename="synthetic.pdf",
            job_id=None,
            index=0,
        )
    assert db_session.scalar(select(func.count()).select_from(CvFile)) == 0
    assert db_session.scalar(select(func.count()).select_from(Activity)) == 0
    assert list(cv_runtime.root.iterdir()) == []


def test_invalid_multipart_returns_safe_validation_error(client, account):
    sign_in(client)
    response = client.post(
        BASE,
        content=b"--test\r\ninvalid multipart",
        headers={**csrf_headers(client), "Content-Type": "multipart/form-data; boundary=test"},
    )
    assert response.status_code == 422
    assert "invalid multipart" not in response.text


def test_openapi_contains_multipart_and_download_contract(client):
    paths = client.get("/openapi.json").json()["paths"]
    schema = paths[BASE]["post"]["requestBody"]["content"]["multipart/form-data"]["schema"]
    assert schema["properties"]["files"]["maxItems"] == 50
    assert schema["properties"]["job_id"]["format"] == "uuid"
    assert (
        "application/pdf"
        in paths[BASE + "/{cv_file_id}/download"]["get"]["responses"]["200"]["content"]
    )


def test_filename_controls_are_metadata_only_and_cannot_bypass_macro_check(
    account, db_session, cv_runtime
):
    result = cv_service.upload_file(
        db_session,
        account,
        cv_runtime,
        data=PDF,
        filename="..\\synthetic\x00\r\n.pdf",
        job_id=None,
        index=0,
    )
    assert result.cv_file.original_filename == "synthetic.pdf"
    assert all("synthetic" not in path.name for path in cv_runtime.root.iterdir())
    with pytest.raises(AppError) as caught:
        cv_service.upload_file(
            db_session,
            account,
            cv_runtime,
            data=PDF,
            filename="synthetic.docm\x00 ",
            job_id=None,
            index=1,
        )
    assert caught.value.code == "MACRO_NOT_ALLOWED"


def test_publish_timeout_after_worker_success_does_not_overwrite_done(client, account, monkeypatch):
    sign_in(client)
    original_delay = tasks.process_cv_file.delay

    def processed_then_timeout(*args):
        original_delay(*args)
        raise RuntimeError("synthetic ambiguous broker acknowledgement")

    monkeypatch.setattr(tasks.process_cv_file, "delay", processed_then_timeout)
    uploaded = one_file(upload(client))
    assert uploaded["status"] == "done"
    assert client.get(f"{BASE}/{uploaded['id']}").json()["status"] == "done"
