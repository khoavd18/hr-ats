"""Spec 07 × every business endpoint, using persisted scope and real auth/DB.

Cases are an independent policy inventory, not generated from authorize().
The OpenAPI inventory test requires new endpoints to receive an explicit case.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.api.cv_files import storage_dependency
from app.core import security
from app.core.config import get_settings
from app.models import (
    Activity,
    Application,
    AuditLog,
    Candidate,
    CvFile,
    DataRequest,
    EmailMessage,
    EmailTemplate,
    Interview,
    JobMember,
    Offer,
    Placement,
    StageEvent,
    Task,
)
from app.models.enums import ApplicationStage, ProcessingStatus
from app.models.users import UserRole
from app.storage import LocalStorage
from app.workers import email, tasks
from tests.api.test_pipeline import seed_records
from tests.auth_helpers import csrf_headers
from tests.cv_helpers import PDF


@dataclass(frozen=True)
class Case:
    name: str
    method: str
    path: str
    policy: str = "job"
    body: dict | None = None
    params: dict = field(default_factory=dict)
    status: int = 200


REPORT_PERIOD = {"from": "2026-11-01", "to": "2026-11-11"}
CASES = [
    Case("config", "GET", "/config/public", "all"),
    Case("jobs-list", "GET", "/jobs", "all"),
    Case("jobs-options", "GET", "/jobs/options", "all"),
    Case("job-detail", "GET", "/jobs/{job_id}"),
    Case(
        "job-create-self",
        "POST",
        "/jobs",
        "all",
        {
            "title": "Job mới giả",
            "hiring_unit_id": "$unit_id",
            "owner_id": "$actor_id",
        },
        status=201,
    ),
    Case(
        "job-create-other",
        "POST",
        "/jobs",
        "manager",
        {
            "title": "Job mới giả",
            "hiring_unit_id": "$unit_id",
            "owner_id": "$other_id",
        },
        status=201,
    ),
    Case("job-edit", "PATCH", "/jobs/{job_id}", body={"title": "Tiêu đề mới giả"}),
    Case("job-owner", "PATCH", "/jobs/{job_id}", "manager", {"owner_id": "$new_owner_id"}),
    Case("job-members", "PUT", "/jobs/{job_id}/members", body={"user_ids": []}),
    Case("ranking", "GET", "/jobs/{job_id}/applications"),
    Case("export-candidates", "GET", "/jobs/{job_id}/export.xlsx"),
    Case("pipeline", "GET", "/jobs/{job_id}/pipeline"),
    Case("suggestions", "GET", "/jobs/{job_id}/suggestions"),
    Case("rescore-job", "POST", "/jobs/{job_id}/rescore", status=202),
    Case(
        "application-create",
        "POST",
        "/applications",
        body={
            "candidate_id": "$free_id",
            "job_id": "$job_id",
        },
        status=201,
    ),
    Case("application-detail", "GET", "/applications/{application_id}"),
    Case("application-rescore", "POST", "/applications/{application_id}/rescore", status=202),
    Case("move", "POST", "/applications/{application_id}/move", body={"to_stage": "screening"}),
    Case("undo", "POST", "/applications/{application_id}/undo"),
    Case(
        "feedback", "POST", "/applications/{application_id}/ai-feedback", body={"verdict": "agree"}
    ),
    Case(
        "note",
        "POST",
        "/applications/{application_id}/notes",
        body={"text": "Ghi chú giả"},
        status=201,
    ),
    Case(
        "candidate-edit", "PATCH", "/candidates/{candidate_id}", body={"full_name": "Tên mới giả"}
    ),
    Case("bank-search", "GET", "/candidates", "all"),
    Case("bank-semantic", "GET", "/candidates/search/semantic", "all", params={"q": "Python"}),
    Case(
        "bank-merge", "POST", "/candidates/{free_id}/merge", "manager", {"into_id": "$candidate_id"}
    ),
    Case("upload-job", "POST", "/cv-files"),
    Case("upload-bank", "POST", "/cv-files", "all"),
    Case("cv-status", "GET", "/cv-files/{cv_file_id}"),
    Case("cv-download", "GET", "/cv-files/{cv_file_id}/download"),
    Case("units-list", "GET", "/hiring-units", "manager"),
    Case(
        "unit-create",
        "POST",
        "/hiring-units",
        "manager",
        {"name": "Đơn vị giả", "kind": "department"},
        status=201,
    ),
    Case("unit-edit", "PATCH", "/hiring-units/{unit_id}", "manager", {"name": "Tên mới giả"}),
    Case("templates-list", "GET", "/email-templates", "manager"),
    Case("template-options", "GET", "/email-templates/preview-options", "manager"),
    Case(
        "template-create",
        "POST",
        "/email-templates",
        "manager",
        {
            "key": "matrix_new",
            "name": "Mẫu giả",
            "subject": "Tiêu đề giả",
            "body": "Nội dung giả",
        },
        status=201,
    ),
    Case(
        "template-edit",
        "PATCH",
        "/email-templates/{template_id}",
        "manager",
        {"name": "Mẫu mới giả"},
    ),
    Case(
        "template-preview",
        "POST",
        "/email-templates/{template_id}/preview",
        "manager",
        {"application_id": "$application_id"},
    ),
    Case("mailbox", "GET", "/settings/mailbox", "manager"),
    Case("email-list", "GET", "/email-messages", params={"application_id": "$application_id"}),
    Case(
        "email-choices",
        "GET",
        "/email-messages/templates",
        params={"application_id": "$application_id"},
    ),
    Case(
        "email-preview",
        "POST",
        "/email-messages/preview",
        body={"application_id": "$application_id", "template_id": "$template_id"},
    ),
    Case(
        "email-create",
        "POST",
        "/email-messages",
        body={
            "application_id": "$application_id",
            "to_email": "matrix@example.invalid",
            "subject": "Thư giả",
            "body": "Nội dung giả",
        },
        status=201,
    ),
    Case("email-send", "POST", "/email-messages/{message_id}/send", status=202),
    Case("email-cancel", "POST", "/email-messages/{message_id}/cancel"),
    Case("users-list", "GET", "/users", "admin"),
    Case(
        "user-create",
        "POST",
        "/users",
        "admin",
        {
            "email": "matrix-new@example.invalid",
            "full_name": "Tài khoản mới giả",
            "password": "synthetic-matrix-password",
            "role": "recruiter",
        },
        status=201,
    ),
    Case("user-edit", "PATCH", "/users/{other_id}", "admin", {"role": "lead"}),
    Case("retention", "GET", "/settings/retention", "admin"),
    Case("requests-list", "GET", "/data-requests", "admin"),
    Case(
        "request-create",
        "POST",
        "/data-requests",
        "admin",
        {"candidate_id": "$free_id", "requested_by_note": "Bằng chứng giả"},
        status=201,
    ),
    Case("request-execute", "POST", "/data-requests/{request_id}/execute", "admin"),
    Case("audit", "GET", "/audit-log", "admin"),
    Case(
        "consent",
        "POST",
        "/candidates/{candidate_id}/consent",
        body={"consent_at": "$consent_at", "note": "Bằng chứng giả"},
    ),
    Case(
        "extend",
        "POST",
        "/candidates/{candidate_id}/consent",
        "admin",
        {"consent_at": "$consent_at", "note": "Bằng chứng giả", "extend_retention": True},
    ),
    Case("interviews-list", "GET", "/interviews", "all", params={"mine": "false"}),
    Case(
        "interview-create",
        "POST",
        "/applications/{application_id}/interviews",
        body={"scheduled_at": "$scheduled_at"},
        status=201,
    ),
    Case("interview-edit", "PATCH", "/interviews/{interview_id}", body={"result": "pass"}),
    Case("interview-ics", "GET", "/interviews/{interview_id}/ics"),
    Case(
        "offer-create",
        "POST",
        "/applications/{application_id}/offers",
        body={"status": "draft"},
        status=201,
    ),
    Case("offer-edit", "PATCH", "/offers/{offer_id}", body={"notes": "Ghi chú giả"}),
    Case(
        "placement-create",
        "POST",
        "/applications/{application_id}/placement",
        body={"start_date": "2026-11-15"},
        status=201,
    ),
    Case("placement-edit", "PATCH", "/placements/{placement_id}", body={"fee_amount": 0}),
    Case("tasks-list", "GET", "/tasks", "all"),
    Case("tasks-team", "GET", "/tasks", "manager", params={"mine": "false"}),
    Case("task-options", "GET", "/tasks/application-options", params={"job_id": "$job_id"}),
    Case(
        "task-create",
        "POST",
        "/tasks",
        body={"title": "Việc giả", "application_id": "$application_id"},
        status=201,
    ),
    Case("task-edit", "PATCH", "/tasks/{task_id}", body={"status": "done"}),
    Case("overview", "GET", "/overview", "all"),
]
for report in ("summary", "funnel", "recruiters", "ai-agreement", "export.xlsx"):
    CASES.extend(
        [
            Case(f"report-{report}", "GET", f"/reports/{report}", "all", params=REPORT_PERIOD),
            Case(
                f"report-other-{report}",
                "GET",
                f"/reports/{report}",
                "manager",
                params=REPORT_PERIOD | {"recruiter_id": "$other_id"},
            ),
        ]
    )

SCOPES = ["admin", "lead", "owner", "member", "outsider", "revoked", "inactive", "anonymous"]


def resolve(value, ids):
    if isinstance(value, dict):
        return {key: resolve(item, ids) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve(item, ids) for item in value]
    return ids[value[1:]] if isinstance(value, str) and value.startswith("$") else value


@pytest.fixture
def matrix(app, client, db_session, account, tmp_path, monkeypatch, scope, case):
    account.role = UserRole(scope) if scope in {"admin", "lead"} else UserRole.recruiter
    db_session.flush()
    records = seed_records(db_session, account)
    records.job.owner_id = account.id if scope == "owner" else records.other.id
    records.candidate.email = "matrix@example.invalid"
    records.candidate.phone = "+84900000123"
    records.application.owner_id = (
        account.id
    )  # Owning an application alone must NOT grant Job access.
    records.application.stage = (
        ApplicationStage.offer if case.name == "placement-create" else ApplicationStage.submitted
    )
    if scope in {"member", "revoked"}:
        membership = JobMember(job_id=records.job.id, user_id=account.id)
        db_session.add(membership)
        db_session.flush()
        if scope == "revoked":
            db_session.delete(membership)
    free = Candidate(full_name="Ứng viên tự do giả", retention_until=date(2099, 1, 1))
    erased = Candidate(full_name="Ứng viên xoá giả", retention_until=date(2099, 1, 1))
    db_session.add_all([free, erased])
    db_session.flush()
    storage = LocalStorage(tmp_path / "matrix")
    app.dependency_overrides[storage_dependency] = lambda: storage
    settings = get_settings().model_copy(update={"storage_local_dir": storage.root})
    app.dependency_overrides[get_settings] = lambda: settings
    cv_file = CvFile(
        candidate_id=records.candidate.id,
        job_id=records.job.id,
        uploaded_by=account.id,
        original_filename="synthetic.pdf",
        storage_key=storage.put(PDF, "application/pdf"),
        sha256=uuid4().hex,
        mime_type="application/pdf",
        size_bytes=len(PDF),
        status=ProcessingStatus.done,
    )
    template = EmailTemplate(
        key="matrix", name="Mẫu giả", subject="Thư giả", body="Chào {{ candidate_name }}"
    )
    interview = Interview(
        application_id=records.application.id,
        round=1,
        scheduled_at=datetime.now(UTC) + timedelta(days=1),
        duration_minutes=30,
    )
    offer = Offer(application_id=records.application.id)
    task = Task(
        title="Việc giả",
        assignee_id=account.id,
        created_by=records.other.id,
        job_id=records.job.id,
        application_id=records.application.id,
    )
    request = DataRequest(candidate_id=erased.id, kind="delete", requested_by_note="Bằng chứng giả")
    event = StageEvent(
        application_id=records.application.id,
        from_stage=ApplicationStage.screening,
        to_stage=ApplicationStage.submitted,
        actor_id=account.id,
        occurred_at=datetime.now(UTC),
    )
    db_session.add_all([cv_file, template, interview, offer, task, request, event])
    db_session.flush()
    message = EmailMessage(
        application_id=records.application.id,
        template_id=template.id,
        to_email="matrix@example.invalid",
        subject="Thư giả",
        body_html="Nội dung giả",
        created_by=records.other.id,
    )
    placement = Placement(application_id=records.application.id, start_date=date(2026, 11, 15))
    db_session.add(message)
    if case.name == "placement-edit":
        db_session.add(placement)
    db_session.commit()
    published = Mock()
    for task_object in (
        tasks.process_cv_file,
        tasks.score_application,
        tasks.rescore_job,
        email.send_email_message,
    ):
        monkeypatch.setattr(task_object, "apply_async", published)
    csrf = security.new_csrf(settings)
    if scope != "anonymous":
        client.cookies.set("csrf_token", csrf)
        client.cookies.set("access_token", security.encode_token(account, "access", csrf, settings))
    if scope == "inactive":
        account.is_active = False
        db_session.commit()
    ids = {
        "job_id": str(records.job.id),
        "candidate_id": str(records.candidate.id),
        "application_id": str(records.application.id),
        "free_id": str(free.id),
        "unit_id": str(records.job.hiring_unit_id),
        "actor_id": str(account.id),
        "other_id": str(records.other.id),
        "new_owner_id": str(account.id if scope != "owner" else records.other.id),
        "cv_file_id": str(cv_file.id),
        "template_id": str(template.id),
        "message_id": str(message.id),
        "interview_id": str(interview.id),
        "offer_id": str(offer.id),
        "placement_id": str(placement.id),
        "task_id": str(task.id),
        "request_id": str(request.id),
        "consent_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        "scheduled_at": interview.scheduled_at.isoformat(),
    }
    return ids, records, published


@pytest.mark.parametrize("scope", SCOPES)
@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_spec07_endpoint_matrix(client, db_session, account, matrix, scope, case):
    ids, records, published = matrix
    allowed = case.policy == "all" or scope in {"admin", "lead"}
    if case.policy == "admin":
        allowed = scope == "admin"
    if case.policy == "job":
        allowed = scope in {"admin", "lead", "owner", "member"}
    expected = case.status if allowed else 403
    if scope in {"anonymous", "inactive"}:
        expected = 401
    models = (Activity, AuditLog, Application, Candidate, CvFile, EmailMessage, Task, DataRequest)
    before = [db_session.scalar(select(func.count()).select_from(model)) for model in models]
    old_name, old_title, old_owner = (
        records.candidate.full_name,
        records.job.title,
        records.job.owner_id,
    )
    kwargs = {"params": resolve(case.params, ids), "headers": csrf_headers(client)}
    if case.body is not None:
        kwargs["json"] = resolve(case.body, ids)
    if case.name.startswith("upload-"):
        kwargs["files"] = [("files", ("synthetic.pdf", PDF, "application/pdf"))]
        kwargs["data"] = {"job_id": ids["job_id"]} if case.name == "upload-job" else {}
    response = client.request(case.method, "/api/v1" + case.path.format_map(ids), **kwargs)
    assert response.status_code == expected, response.text
    if expected in {401, 403}:
        assert response.json()["error"]["code"] == (
            "UNAUTHORIZED" if expected == 401 else "FORBIDDEN"
        )
        assert "matrix@example.invalid" not in response.text
        assert [
            db_session.scalar(select(func.count()).select_from(model)) for model in models
        ] == before
        db_session.refresh(records.candidate)
        db_session.refresh(records.job)
        assert (records.candidate.full_name, records.job.title, records.job.owner_id) == (
            old_name,
            old_title,
            old_owner,
        )
        published.assert_not_called()
    elif case.name in {"bank-search", "bank-semantic"}:
        for row in response.json()["items"]:
            assert (
                not {
                    "email",
                    "phone",
                    "extracted_text",
                    "anonymized_text",
                    "embedding",
                    "cv_files",
                    "applications",
                }
                & row.keys()
            )
    elif case.name in {"jobs-list", "tasks-list", "interviews-list"}:
        assert response.json()["total"] == (0 if scope in {"outsider", "revoked"} else 1)
    elif (
        case.name.startswith("report-")
        and scope not in {"admin", "lead"}
        and not case.path.endswith(".xlsx")
    ):
        assert response.json()["period"]["recruiter_id"] == ids["actor_id"]
        if case.name == "report-recruiters":
            assert {row["recruiter_id"] for row in response.json()["items"]} == {ids["actor_id"]}


def test_permission_inventory_covers_every_business_endpoint(app):
    # Public health and auth have separate exhaustive token/CSRF/concurrency suites.
    excluded = {("GET", "/health")}
    schema = app.openapi()
    operations = {
        (method.upper(), path.removeprefix("/api/v1"))
        for path, methods in schema["paths"].items()
        for method in methods
        if method in {"get", "post", "patch", "put", "delete"}
        if not path.startswith("/api/v1/auth/")
    }
    # Free_id is the same route placeholder as candidate_id.
    covered = {
        (
            case.method,
            case.path.replace("{free_id}", "{candidate_id}").replace("{other_id}", "{user_id}"),
        )
        for case in CASES
    }
    assert operations == covered | excluded
