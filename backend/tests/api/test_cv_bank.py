"""T16 acceptance and privacy boundaries on PostgreSQL, entirely synthetic data."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.ai.embed import FakeEmbedder
from app.core.config import get_settings
from app.core.security import hash_password
from app.models import Activity, Application, Candidate, CvFile, HiringUnit, Job, JobMember, User
from app.models.applications import AiFeedback, StageEvent
from app.models.enums import ActivityType, ApplicationStage, CandidateSource, HiringUnitKind
from app.models.users import UserRole
from app.services import cv_bank
from tests.auth_helpers import PASSWORD, csrf_headers, sign_in


@pytest.fixture
def records(db_session, account):
    embedder = FakeEmbedder(get_settings().embedding_dim)
    vector = embedder.embed(["Kế toán excel"])[0]
    candidates = [
        Candidate(
            full_name=f"Ứng viên giả {index}",
            current_title="Kế toán",
            skills=["Excel", "Kế toán"],
            years_experience=3,
            location="Đà Nẵng",
            retention_until=date(2099, 1, 1),
            embedding=vector,
            email=f"bank-{index}@example.invalid",
            phone="+84900000000",
            anonymized_text="PRIVATE_CV",
            consent_note="PRIVATE_CONSENT",
        )
        for index in range(3)
    ]
    unit = HiringUnit(name="Đơn vị giả T16", kind=HiringUnitKind.department)
    recruiter = User(
        email="bank@example.invalid",
        full_name="HR giả T16",
        role=UserRole.recruiter,
        password_hash=hash_password(PASSWORD),
    )
    db_session.add_all([*candidates, unit, recruiter])
    db_session.flush()
    job = Job(
        title="Kế toán giả T16",
        description="Excel",
        must_have=["Excel"],
        owner_id=account.id,
        hiring_unit_id=unit.id,
        embedding=vector,
    )
    db_session.add(job)
    db_session.flush()
    application = Application(
        candidate_id=candidates[0].id,
        job_id=job.id,
        owner_id=account.id,
        stage=ApplicationStage.interview,
    )
    db_session.add(application)
    db_session.commit()
    return SimpleNamespace(
        candidates=candidates, job=job, application=application, recruiter=recruiter
    )


def test_ke_toan_finds_accented_cv_and_returns_only_summary(client, account, records):
    sign_in(client)
    response = client.get("/api/v1/candidates?q=ke%20toan")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["total"] == 3
    assert all(c["current_title"] == "Kế toán" for c in response.json()["items"])
    assert set(response.json()["items"][0]) == {
        "id",
        "full_name",
        "current_title",
        "years_experience",
        "skills",
        "location",
        "source",
        "created_at",
        "possible_duplicate",
    }
    for forbidden in ("email", "phone", "embedding", "search_tsv", "anonymized_text", "PRIVATE_"):
        assert forbidden not in response.text


def test_combined_filters_and_pagination(client, account, records, db_session):
    records.candidates[1].source = CandidateSource.email
    records.candidates[2].years_experience = 1
    db_session.commit()
    sign_in(client)
    params = {
        "q": "ke toan",
        "skills": "excel, KE TOAN",
        "location": "da nang",
        "min_years": 2,
        "source": "upload",
        "page_size": 1,
    }
    response = client.get("/api/v1/candidates", params=params)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == str(records.candidates[0].id)
    assert client.get("/api/v1/candidates", params={**params, "page": 2}).json()["items"] == []
    assert client.get("/api/v1/candidates?skills=excel,python").json()["total"] == 0
    assert client.get("/api/v1/candidates?location=%25").json()["total"] == 0
    assert client.get("/api/v1/candidates?q=%27%3Bdrop%20table").status_code == 200


def test_semantic_orders_by_real_cosine_and_applies_filters(client, account, records, db_session):
    records.candidates[1].embedding = FakeEmbedder(get_settings().embedding_dim).embed(["Java"])[0]
    records.candidates[2].embedding = None
    db_session.commit()
    sign_in(client)
    response = client.get("/api/v1/candidates/search/semantic?q=Kế%20toán%20excel&skills=excel")
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 2
    assert response.json()["items"][0]["id"] == str(records.candidates[0].id)
    assert client.get("/api/v1/candidates/search/semantic?q=%20").status_code == 422


def test_semantic_redacts_contacts_and_returns_safe_provider_errors(
    client, account, records, monkeypatch
):
    seen = []

    class Spy:
        def embed(self, texts):
            seen.extend(texts)
            raise RuntimeError("PRIVATE_PROVIDER_CV")

    monkeypatch.setattr(cv_bank, "get_embedder", lambda settings: Spy())
    sign_in(client)
    response = client.get(
        "/api/v1/candidates/search/semantic", params={"q": "Python bank@example.invalid"}
    )
    assert response.status_code == 503
    assert "PRIVATE" not in response.text and "bank@" not in response.text
    assert seen and "bank@" not in seen[0] and "Python" in seen[0]


def test_suggestions_exclude_existing_and_limit_to_top_50(client, account, records, db_session):
    for index in range(55):
        db_session.add(
            Candidate(
                full_name=f"Ứng viên giả bổ sung {index}",
                retention_until=date(2099, 1, 1),
                embedding=records.candidates[0].embedding,
            )
        )
    db_session.commit()
    sign_in(client)
    response = client.get(f"/api/v1/jobs/{records.job.id}/suggestions")
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 50
    assert str(records.candidates[0].id) not in {c["id"] for c in items}
    assert (
        len(client.get(f"/api/v1/jobs/{records.job.id}/suggestions?limit=1").json()["items"]) == 1
    )


@pytest.mark.parametrize("state", ["deleted", "merged", "expired"])
def test_all_search_modes_exclude_ineligible(client, account, records, db_session, state):
    candidate = records.candidates[1]
    if state == "deleted":
        candidate.deleted_at = datetime.now(UTC)
    elif state == "merged":
        candidate.merged_into_id = records.candidates[0].id
    else:
        candidate.retention_until = date(2000, 1, 1)
    db_session.commit()
    sign_in(client)
    for path in (
        "/candidates?q=ke%20toan",
        "/candidates/search/semantic?q=excel",
        f"/jobs/{records.job.id}/suggestions",
    ):
        response = client.get("/api/v1" + path)
        assert response.status_code == 200, response.text
        assert str(candidate.id) not in {c["id"] for c in response.json()["items"]}


def test_shared_bank_does_not_grant_job_or_merge_permissions(client, records, db_session):
    sign_in(client, records.recruiter.email)
    assert client.get("/api/v1/candidates").status_code == 200
    path = f"/api/v1/jobs/{records.job.id}/suggestions"
    assert client.get(path).status_code == 403
    db_session.add(JobMember(job_id=records.job.id, user_id=records.recruiter.id))
    db_session.commit()
    assert client.get(path).status_code == 200
    member = db_session.scalar(select(JobMember).where(JobMember.job_id == records.job.id))
    db_session.delete(member)
    db_session.commit()
    assert client.get(path).status_code == 403
    response = client.post(
        f"/api/v1/candidates/{records.candidates[1].id}/merge",
        json={"into_id": str(records.candidates[0].id)},
        headers=csrf_headers(client),
    )
    assert response.status_code == 403


def test_duplicate_hint_is_summary_only_symmetric_and_ignores_stale_hint(
    client, account, records, db_session
):
    source, target = records.candidates[:2]
    file = CvFile(
        candidate_id=source.id,
        storage_key="PRIVATE_STORAGE",
        original_filename="cv-gia.pdf",
        mime_type="application/pdf",
        size_bytes=1,
        sha256="d" * 64,
        parsed_json={"possible_duplicate_of": str(target.id), "private": "PRIVATE_PARSE"},
    )
    db_session.add(file)
    db_session.commit()
    sign_in(client)
    data = client.get("/api/v1/candidates").json()
    by_id = {c["id"]: c for c in data["items"]}
    assert by_id[str(source.id)]["possible_duplicate"]["id"] == str(target.id)
    assert by_id[str(target.id)]["possible_duplicate"]["id"] == str(source.id)
    assert "PRIVATE" not in str(data)
    target.deleted_at = datetime.now(UTC)
    db_session.commit()
    data = client.get("/api/v1/candidates").json()
    assert all(c["possible_duplicate"] is None for c in data["items"])


@pytest.mark.parametrize("role", [UserRole.admin, UserRole.lead])
def test_merge_moves_files_and_apps_without_duplicate_active_job_and_keeps_history(
    client,
    account,
    records,
    db_session,
    role,
):
    account.role = role
    source, target = records.candidates[1:]
    source_application = Application(
        candidate_id=source.id,
        job_id=records.job.id,
        owner_id=account.id,
        stage=ApplicationStage.offer,
    )
    target_application = Application(
        candidate_id=target.id,
        job_id=records.job.id,
        owner_id=account.id,
        stage=ApplicationStage.screening,
    )
    other_job = Job(
        title="Vị trí giả khác",
        description="Mô tả giả",
        owner_id=account.id,
        hiring_unit_id=records.job.hiring_unit_id,
    )
    db_session.add_all([source_application, target_application, other_job])
    db_session.flush()
    unique_application = Application(
        candidate_id=source.id, job_id=other_job.id, owner_id=account.id
    )
    file = CvFile(
        candidate_id=source.id,
        storage_key="PRIVATE_STORAGE",
        original_filename="cv-gia.pdf",
        mime_type="application/pdf",
        size_bytes=1,
        sha256="e" * 64,
    )
    event = StageEvent(
        application_id=source_application.id, to_stage=ApplicationStage.offer, actor_id=account.id
    )
    feedback = AiFeedback(application_id=source_application.id, user_id=account.id, verdict="agree")
    db_session.add_all([file, unique_application, event, feedback])
    db_session.commit()
    sign_in(client)
    response = client.post(
        f"/api/v1/candidates/{source.id}/merge",
        json={"into_id": str(target.id)},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert source.merged_into_id == target.id and source.deleted_at is not None
    assert file.candidate_id == target.id
    assert unique_application.candidate_id == target.id and unique_application.deleted_at is None
    assert (
        source_application.candidate_id == target.id and source_application.deleted_at is not None
    )
    assert (
        target_application.stage == ApplicationStage.screening
        and target_application.deleted_at is None
    )
    assert (
        event.application_id == source_application.id
        and feedback.application_id == source_application.id
    )
    assert target.consent_at is None and target.retention_until == date(2099, 1, 1)
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(Application)
            .where(
                Application.candidate_id == target.id,
                Application.job_id == records.job.id,
                Application.deleted_at.is_(None),
            )
        )
        == 1
    )
    activity = db_session.scalar(select(Activity).where(Activity.candidate_id == target.id))
    assert activity.type == ActivityType.note and activity.payload["source_id"] == str(source.id)
    assert client.get("/api/v1/candidates").json()["total"] == 2
    assert (
        client.post(
            f"/api/v1/candidates/{source.id}/merge",
            json={"into_id": str(target.id)},
            headers=csrf_headers(client),
        ).status_code
        == 404
    )


def test_merge_rolls_back_everything_if_activity_fails(
    client, account, records, db_session, monkeypatch
):
    source, target = records.candidates[:2]

    def fail(*args, **kwargs):
        raise RuntimeError("PRIVATE_ERROR")

    monkeypatch.setattr(cv_bank, "log_activity", fail)
    sign_in(client)
    response = client.post(
        f"/api/v1/candidates/{source.id}/merge",
        json={"into_id": str(target.id)},
        headers=csrf_headers(client),
    )
    assert response.status_code == 500 and "PRIVATE" not in response.text
    db_session.expire_all()
    assert source.deleted_at is None and source.merged_into_id is None
    assert records.application.candidate_id == source.id


@pytest.mark.parametrize(
    "query", ["page=0", "page_size=101", "min_years=-1", "source=bad", "q=" + "a" * 201]
)
def test_invalid_search_input(client, account, records, query):
    sign_in(client)
    assert client.get("/api/v1/candidates?" + query).status_code == 422


def test_auth_csrf_and_merge_input(client, account, records):
    assert client.get("/api/v1/candidates").status_code == 401
    sign_in(client)
    path = f"/api/v1/candidates/{records.candidates[0].id}/merge"
    body = {"into_id": str(records.candidates[1].id)}
    assert client.post(path, json=body).status_code == 403
    assert (
        client.post(
            path, json=body, headers={**csrf_headers(client), "Origin": "https://example.invalid"}
        ).status_code
        == 403
    )
    assert (
        client.post(path, json={**body, "extra": True}, headers=csrf_headers(client)).status_code
        == 422
    )
    assert (
        client.post(
            path, json={"into_id": str(records.candidates[0].id)}, headers=csrf_headers(client)
        ).status_code
        == 422
    )
    assert (
        client.post(path, json={"into_id": str(uuid4())}, headers=csrf_headers(client)).status_code
        == 404
    )


def test_suggestions_allow_archived_application_and_handle_missing_vector(
    client, account, records, db_session
):
    records.application.deleted_at = datetime.now(UTC)
    db_session.commit()
    sign_in(client)
    path = f"/api/v1/jobs/{records.job.id}/suggestions"
    response = client.get(path)
    assert response.status_code == 200
    assert str(records.candidates[0].id) in {c["id"] for c in response.json()["items"]}
    for limit in (0, 51):
        assert client.get(path, params={"limit": limit}).status_code == 422
    records.job.embedding = None
    db_session.commit()
    assert client.get(path).json() == {"items": [], "total": 0}
    assert client.get(f"/api/v1/jobs/{uuid4()}/suggestions").status_code == 404


@pytest.mark.parametrize("side", [0, 1])
@pytest.mark.parametrize("state", ["deleted", "merged", "expired"])
def test_merge_rejects_ineligible_source_or_target_without_side_effects(
    client, account, records, db_session, side, state
):
    source, target = records.candidates[:2]
    candidate = (source, target)[side]
    if state == "deleted":
        candidate.deleted_at = datetime.now(UTC)
    elif state == "merged":
        candidate.merged_into_id = records.candidates[2].id
    else:
        candidate.retention_until = date(2000, 1, 1)
    db_session.commit()
    sign_in(client)
    response = client.post(
        f"/api/v1/candidates/{source.id}/merge",
        json={"into_id": str(target.id)},
        headers=csrf_headers(client),
    )
    assert response.status_code == 404
    assert records.application.candidate_id == source.id
    assert db_session.scalar(select(func.count()).select_from(Activity)) == 0
