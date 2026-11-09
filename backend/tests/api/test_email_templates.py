from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.email.defaults import DEFAULT_TEMPLATES
from app.models import EmailMessage, EmailTemplate, Interview, Offer
from app.models.enums import ApplicationStage
from app.models.users import UserRole
from app.services.email_templates import build_context, seed_templates
from tests.api.test_pipeline import seed_records
from tests.auth_helpers import csrf_headers, sign_in

BASE = "/api/v1/email-templates"
TEMPLATE = dict(
    key="synthetic",
    name="Mẫu giả T22",
    subject="Vị trí {{ job_title }}",
    body="Chào **{{ candidate_name }}**",
)


@pytest.fixture
def records(db_session, account):
    data = seed_records(db_session, account)
    db_session.add_all(
        [
            Interview(
                application_id=data.application.id,
                round=1,
                scheduled_at=datetime(2026, 11, 10, 2, 30, tzinfo=UTC),
                duration_minutes=60,
                location_or_link="Phòng giả T22",
            ),
            Offer(application_id=data.application.id, salary=0, start_date=date(2026, 12, 1)),
        ]
    )
    db_session.commit()
    return data


def create(client, **changes):
    return client.post(BASE, json=TEMPLATE | changes, headers=csrf_headers(client))


def test_defaults_seed_is_idempotent_preserves_edits_and_message_defaults(db_session, account):
    rows = db_session.scalars(select(EmailTemplate)).all()
    assert len(rows) == 5
    assert {row.key for row in rows} == {item["key"] for item in DEFAULT_TEMPLATES}
    for row in rows:
        expected = next(item for item in DEFAULT_TEMPLATES if item["key"] == row.key)
        assert all(getattr(row, key) == value for key, value in expected.items())
    row = rows[0]
    row.body = "Nội dung HR giả đã sửa"
    row.is_active = False
    db_session.commit()
    seed_templates(db_session)
    seed_templates(db_session)
    db_session.commit()
    db_session.refresh(row)
    assert row.body == "Nội dung HR giả đã sửa" and not row.is_active
    assert db_session.scalar(select(func.count()).select_from(EmailTemplate)) == 5
    message = EmailMessage(
        to_email="synthetic@example.invalid",
        subject="Thư giả",
        body_html="<p>Giả</p>",
        created_by=account.id,
        template_id=row.id,
    )
    db_session.add(message)
    db_session.commit()
    assert message.status == "draft" and message.cc == [] and message.deleted_at is None
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(
            EmailTemplate(**(TEMPLATE | {"key": "unsafe", "requires_confirmation": False}))
        )
        db_session.flush()


@pytest.mark.parametrize("role", [UserRole.admin, UserRole.lead])
def test_crud_preview_unsaved_edits_and_no_side_effects(
    client, account, records, db_session, role, email_outbox
):
    account.role = role
    db_session.commit()
    sign_in(client)
    result = create(client)
    assert result.status_code == 201, result.text
    row = result.json()
    assert row["requires_confirmation"] and row["is_active"]
    assert result.headers["cache-control"] == "no-store"
    listed = client.get(BASE + "?page_size=2").json()
    assert listed["total"] == 6 and len(listed["items"]) == 2
    assert create(client).status_code == 409
    options = client.get(BASE + "/preview-options?q=T19").json()
    assert options == {
        "items": [
            {
                "id": str(records.application.id),
                "candidate_name": records.candidate.full_name,
                "job_title": records.job.title,
            }
        ],
        "total": 1,
    }
    data = {
        "application_id": str(records.application.id),
        "body": "<script>bad()</script> **{{ candidate_name }}**",
    }
    preview = client.post(BASE + f"/{row['id']}/preview", json=data, headers=csrf_headers(client))
    assert preview.status_code == 200, preview.text
    assert "&lt;script&gt;" in preview.json()["body_html"]
    assert "<script>" not in preview.json()["body_html"]
    assert records.candidate.full_name in preview.json()["body"]
    assert preview.headers["cache-control"] == "no-store"
    saved = client.patch(
        BASE + f"/{row['id']}",
        json={"is_active": False, "stage": "offer", "body": "Thay đổi giả"},
        headers=csrf_headers(client),
    )
    assert saved.status_code == 200 and not saved.json()["is_active"]
    assert saved.json()["stage"] == "offer"
    assert db_session.scalar(select(func.count()).select_from(EmailMessage)) == 0
    db_session.refresh(records.application)
    assert records.application.stage == ApplicationStage.new and email_outbox == []


def test_context_uses_application_owner_real_business_fields_and_missing_values(
    client, account, records, db_session
):
    context = build_context(
        db_session,
        account,
        records.application.id,
        Settings(smtp_from="Công ty giả <sender@example.invalid>"),
    )
    assert context == dict(
        candidate_name=records.candidate.full_name,
        job_title=records.job.title,
        hiring_unit_name="Đơn vị giả T19",
        recruiter_name=records.other.full_name,
        recruiter_email=records.other.email,
        company_name="Công ty giả",
        interview_time="10/11/2026 09:30",
        interview_location="Phòng giả T22",
        offer_salary="0 đồng",
        offer_start_date="01/12/2026",
    )
    sign_in(client)
    template = create(client, body="{{ offer_salary }}").json()
    offer = db_session.scalars(select(Offer)).one()
    offer.deleted_at = datetime.now(UTC)
    db_session.commit()
    result = client.post(
        BASE + f"/{template['id']}/preview",
        json={"application_id": str(records.application.id)},
        headers=csrf_headers(client),
    )
    assert result.status_code == 422
    assert result.json()["error"] == {
        "code": "EMAIL_MISSING_OFFER_SALARY",
        "message": "Thiếu thông tin cho biến: offer_salary.",
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"key": "Bad code"},
        {"name": " "},
        {"subject": "A\r\nB"},
        {"body": " "},
        {"requires_confirmation": False},
        {"body": "{{ candidate_name.__class__ }}"},
        {"body": "{{ other_variable }}"},
        {"body": "{% for x in range(5) %}x{% endfor %}"},
        {"unknown": "PII sentinel must not be reflected"},
    ],
)
def test_input_validation_and_sandbox_on_write(client, account, changes):
    sign_in(client)
    response = create(client, **changes)
    assert response.status_code == 422
    assert "PII sentinel" not in response.text


def test_auth_csrf_forbidden_recruiter_and_no_message_endpoints(
    client, account, records, db_session
):
    assert client.get(BASE).status_code == 401
    sign_in(client)
    row = create(client).json()
    assert client.post(BASE, json=TEMPLATE).status_code == 403
    assert client.patch(BASE + f"/{row['id']}", json={"name": "Giả"}).status_code == 403
    assert (
        client.post(
            BASE + f"/{row['id']}/preview", json={"application_id": str(records.application.id)}
        ).status_code
        == 403
    )
    assert create(client, key="another").status_code == 201
    account.role = UserRole.recruiter
    db_session.commit()
    for method, path, data in [
        ("get", BASE, None),
        ("get", BASE + "/preview-options", None),
        ("post", BASE, TEMPLATE),
        ("patch", BASE + f"/{row['id']}", {"name": "Giả"}),
        ("post", BASE + f"/{row['id']}/preview", {"application_id": str(records.application.id)}),
    ]:
        result = client.request(method, path, json=data, headers=csrf_headers(client))
        assert result.status_code == 403
    assert (
        client.post("/api/v1/email-messages", json={}, headers=csrf_headers(client)).status_code
        == 404
    )


@pytest.mark.parametrize("state", ["deleted", "merged", "expired", "application_deleted"])
def test_preview_and_selector_exclude_ineligible_candidates(
    client, account, records, db_session, state
):
    if state == "deleted":
        records.candidate.deleted_at = datetime.now(UTC)
    elif state == "merged":
        records.candidate.merged_into_id = records.candidate.id
    elif state == "expired":
        records.candidate.retention_until = date(2000, 1, 1)
    else:
        records.application.deleted_at = datetime.now(UTC)
    db_session.commit()
    sign_in(client)
    row = create(client).json()
    result = client.post(
        BASE + f"/{row['id']}/preview",
        json={"application_id": str(records.application.id)},
        headers=csrf_headers(client),
    )
    assert result.status_code == 404
    assert client.get(BASE + "/preview-options").json() == {"items": [], "total": 0}


def test_patch_validates_effective_record_missing_ids_and_no_hard_delete(client, account):
    sign_in(client)
    row = create(client).json()
    for data in [
        {"name": None},
        {"subject": "A\nB"},
        {"key": "changed"},
        {"requires_confirmation": False},
        {"body": "{{ candidate_name.__class__ }}"},
    ]:
        assert (
            client.patch(
                BASE + f"/{row['id']}", json=data, headers=csrf_headers(client)
            ).status_code
            == 422
        )
    assert (
        client.patch(
            BASE + f"/{uuid4()}", json={"name": "Giả"}, headers=csrf_headers(client)
        ).status_code
        == 404
    )
    assert client.delete(BASE + f"/{row['id']}", headers=csrf_headers(client)).status_code == 405
