"""T13 contracts on real PostgreSQL with synthetic records and FakeEmbedder."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.ai.embed import EmbeddingError, FakeEmbedder
from app.core.security import hash_password
from app.models import Application, Candidate, HiringUnit, Job, JobMember, User
from app.models.enums import HiringUnitKind
from app.models.users import UserRole
from app.services import jobs
from app.services.embeddings import job_embedding_text
from tests.auth_helpers import PASSWORD, csrf_headers, sign_in


@pytest.fixture
def records(db_session, account):
    unit = HiringUnit(name="Đơn vị mô phỏng", kind=HiringUnitKind.department)
    other = User(
        email="jobs-other@example.invalid",
        full_name="Người dùng giả khác",
        role=UserRole.recruiter,
        password_hash=hash_password(PASSWORD),
    )
    db_session.add_all([unit, other])
    db_session.commit()
    return SimpleNamespace(unit=unit, other=other)


def payload(account, records, **extra):
    return {
        "title": "Kỹ sư Python giả",
        "hiring_unit_id": str(records.unit.id),
        "owner_id": str(account.id),
        "must_have": ["Python"],
        **extra,
    }


def write(client, path, data, method="post"):
    return getattr(client, method)("/api/v1" + path, json=data, headers=csrf_headers(client))


def make_job(client, account, records, **extra):
    result = write(client, "/jobs", payload(account, records, **extra))
    assert result.status_code == 201, result.text
    return result.json()


def test_create_read_patch_members_embedding_and_timestamps(client, account, records, db_session):
    sign_in(client)
    row = make_job(client, account, records, status="open", member_ids=[str(records.other.id)])
    job_id = row["id"]
    assert row["opened_at"] and row["closed_at"] is None
    assert row["hiring_unit_name"] == records.unit.name and row["owner_name"] == account.full_name
    assert row["member_ids"] == [str(records.other.id)] and row["needs_rescore"] is False
    assert "embedding" not in row and "email" not in row
    job = db_session.get(Job, UUID(job_id))
    assert list(job.embedding) == pytest.approx(FakeEmbedder().embed([job_embedding_text(job)])[0])
    first_opened = row["opened_at"]
    same = write(client, f"/jobs/{job_id}", {"status": "open"}, "patch").json()
    assert same["opened_at"] == first_opened
    closed = write(client, f"/jobs/{job_id}", {"status": "closed"}, "patch")
    assert closed.status_code == 200 and closed.json()["closed_at"]
    reopened = write(client, f"/jobs/{job_id}", {"status": "open", "title": "SQL giả"}, "patch")
    assert reopened.json()["closed_at"] is None
    assert reopened.json()["opened_at"] >= first_opened
    assert list(job.embedding) == pytest.approx(FakeEmbedder().embed([job_embedding_text(job)])[0])
    members = write(client, f"/jobs/{job_id}/members", {"user_ids": []}, "put")
    assert members.status_code == 200 and members.json()["member_ids"] == []
    result = client.get(f"/api/v1/jobs/{job_id}")
    assert result.status_code == 200 and result.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "bad",
    [
        {"title": ""},
        {"title": "   "},
        {"title": None},
        {"title": "x" * 201},
        {"salary_min": 20, "salary_max": 10},
        {"salary_min": -1},
        {"salary_max": 2147483648},
        {"status": "open", "must_have": []},
        {"status": "open", "must_have": ["  "]},
        {"headcount": 0},
        {"deadline": "bad-date"},
        {"embedding": [1]},
        {"opened_at": "2026-01-01"},
        {"member_ids": ["bad"]},
        {"owner_id": None},
        {"must_have": ["x" * 501]},
    ],
)
def test_create_validation(client, account, records, bad):
    sign_in(client)
    result = write(client, "/jobs", payload(account, records, **bad))
    assert result.status_code == 422 and result.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "patch",
    [
        {"title": " "},
        {"title": None},
        {"description": None},
        {"status": None},
        {"must_have": []},
        {"must_have": None},
        {"member_ids": None},
        {"headcount": None},
        {"salary_min": 30},
        {"salary_max": 5},
        {"opened_at": None},
    ],
)
def test_patch_validates_effective_record_and_preserves_old_values(client, account, records, patch):
    sign_in(client)
    row = make_job(client, account, records, status="open", salary_min=10, salary_max=20)
    result = write(client, f"/jobs/{row['id']}", patch, "patch")
    assert result.status_code == 422
    assert client.get(f"/api/v1/jobs/{row['id']}").json() == row


def test_draft_can_lack_requirements_but_cannot_open_until_added(client, account, records):
    sign_in(client)
    row = make_job(client, account, records, must_have=[])
    path = f"/jobs/{row['id']}"
    assert write(client, path, {"status": "open"}, "patch").status_code == 422
    opened = write(client, path, {"status": "open", "must_have": [" SQL "]}, "patch")
    assert opened.status_code == 200 and opened.json()["must_have"] == ["SQL"]
    cleared = write(client, path, {"status": "draft", "must_have": [], "salary_min": None}, "patch")
    assert cleared.status_code == 200 and cleared.json()["salary_min"] is None


def test_recruiter_visibility_filter_pagination_and_revoked_membership(
    client, account, records, db_session
):
    account.role = UserRole.recruiter
    db_session.commit()
    sign_in(client)
    owned = make_job(client, account, records, title="Python 100%_ giả", status="open")
    foreign = Job(
        title="Python khác",
        description="",
        hiring_unit_id=records.unit.id,
        owner_id=records.other.id,
    )
    db_session.add(foreign)
    db_session.commit()
    path = f"/jobs/{foreign.id}"
    assert client.get("/api/v1/jobs").json()["total"] == 1
    for method, suffix, data in [
        ("get", "", None),
        ("patch", "", {"title": "sai"}),
        ("put", "/members", {"user_ids": [str(account.id)]}),
    ]:
        result = (
            client.get("/api/v1" + path)
            if method == "get"
            else write(client, path + suffix, data, method)
        )
        assert result.status_code == 403
    member = JobMember(job_id=foreign.id, user_id=account.id)
    db_session.add(member)
    db_session.commit()
    assert client.get("/api/v1/jobs").json()["total"] == 2
    assert client.get("/api/v1/jobs?page_size=1&page=2").json()["total"] == 2
    assert (
        client.get("/api/v1/jobs", params={"status": "open", "q": "100%_"}).json()["items"][0]["id"]
        == owned["id"]
    )
    assert (
        client.get("/api/v1/jobs", params={"owner_id": str(records.other.id)}).json()["total"] == 1
    )
    assert (
        write(client, path, {"description": "Thành viên sửa mô tả giả"}, "patch").status_code == 200
    )
    db_session.delete(member)
    db_session.commit()
    assert client.get("/api/v1" + path).status_code == 403
    assert (
        client.get("/api/v1/jobs", params={"owner_id": str(records.other.id)}).json()["total"] == 0
    )
    assert (
        write(
            client, "/jobs", payload(account, records, owner_id=str(records.other.id))
        ).status_code
        == 403
    )
    assert (
        write(
            client, f"/jobs/{owned['id']}", {"owner_id": str(records.other.id)}, "patch"
        ).status_code
        == 403
    )


@pytest.mark.parametrize("role", [UserRole.admin, UserRole.lead])
def test_managers_see_all_and_assign_owner(client, account, records, db_session, role):
    account.role = role
    db_session.commit()
    sign_in(client)
    row = make_job(client, account, records, owner_id=str(records.other.id))
    assert client.get("/api/v1/jobs").json()["total"] == 1
    changed = write(client, f"/jobs/{row['id']}", {"owner_id": str(account.id)}, "patch")
    assert changed.status_code == 200 and changed.json()["owner_id"] == str(account.id)


def test_needs_rescore_only_changes_requirements_with_active_applications(
    client, account, records, db_session, monkeypatch
):
    sign_in(client)
    row = make_job(client, account, records)
    path = f"/jobs/{row['id']}"
    assert write(client, path, {"must_have": ["SQL"]}, "patch").json()["needs_rescore"] is False
    candidate = Candidate(full_name="Ứng viên giả", retention_until=date(2099, 1, 1))
    db_session.add(candidate)
    db_session.flush()
    application = Application(
        job_id=UUID(row["id"]), candidate_id=candidate.id, owner_id=account.id
    )
    db_session.add(application)
    db_session.commit()
    monkeypatch.setattr(
        "app.workers.tasks.rescore_job.delay", lambda *args: pytest.fail("No automatic score")
    )
    assert write(client, path, {"must_have": ["SQL"]}, "patch").json()["needs_rescore"] is False
    assert write(client, path, {"title": "Tiêu đề mới"}, "patch").json()["needs_rescore"] is False
    assert (
        write(client, path, {"nice_to_have": ["Python"]}, "patch").json()["needs_rescore"] is True
    )
    assert write(client, path, {"must_have": ["Rust"]}, "patch").json()["needs_rescore"] is True
    application.deleted_at = datetime.now(UTC)
    db_session.commit()
    assert write(client, path, {"must_have": ["Go"]}, "patch").json()["needs_rescore"] is False


def test_embedding_failure_rolls_back_job_and_members(
    client, account, records, db_session, monkeypatch
):
    sign_in(client)
    row = make_job(client, account, records)

    def failed(*args, **kwargs):
        raise EmbeddingError()

    monkeypatch.setattr(jobs, "embed_job", failed)
    result = write(
        client,
        f"/jobs/{row['id']}",
        {"title": "Đổi thất bại", "member_ids": [str(records.other.id)]},
        "patch",
    )
    assert result.status_code == 503 and result.json()["error"]["code"] == "EMBEDDING_UNAVAILABLE"
    assert client.get(f"/api/v1/jobs/{row['id']}").json() == row
    assert write(client, "/jobs", payload(account, records)).status_code == 503
    assert db_session.scalar(select(func.count()).select_from(Job)) == 1


def test_invalid_member_rolls_back_entire_edit_and_duplicate_members_are_deduped(
    client, account, records
):
    sign_in(client)
    row = make_job(client, account, records, member_ids=[str(records.other.id)] * 2)
    assert row["member_ids"] == [str(records.other.id)]
    path = f"/jobs/{row['id']}"
    result = write(client, path, {"title": "Không được lưu", "member_ids": [str(uuid4())]}, "patch")
    assert result.status_code == 422
    assert client.get("/api/v1" + path).json() == row
    assert write(client, path + "/members", {"user_ids": [str(uuid4())]}, "put").status_code == 422


def test_inactive_references_options_and_existing_records(client, account, records, db_session):
    sign_in(client)
    row = make_job(client, account, records, member_ids=[str(records.other.id)])
    records.unit.is_active = False
    records.other.is_active = False
    db_session.commit()
    assert write(client, "/jobs", payload(account, records)).status_code == 422
    assert (
        write(client, f"/jobs/{row['id']}", {"title": "Vẫn sửa được"}, "patch").status_code == 200
    )
    choices = client.get("/api/v1/jobs/options").json()
    assert choices["hiring_units"] == []
    assert all(option["id"] != str(records.other.id) for option in choices["users"])
    assert all(set(option) == {"id", "name"} for option in choices["users"])


@pytest.mark.parametrize(
    "role,allowed", [(UserRole.admin, True), (UserRole.lead, True), (UserRole.recruiter, False)]
)
def test_hiring_unit_management_permissions(client, account, db_session, role, allowed):
    account.role = role
    db_session.commit()
    sign_in(client)
    result = write(
        client,
        "/hiring-units",
        {"name": " Đơn vị giả ", "kind": "client", "contact_email": "unit@example.invalid"},
    )
    assert result.status_code == (201 if allowed else 403)
    assert client.get("/api/v1/hiring-units").status_code == (200 if allowed else 403)
    if allowed:
        row = result.json()
        assert row["name"] == "Đơn vị giả"
        edited = write(
            client,
            f"/hiring-units/{row['id']}",
            {"is_active": False, "contact_email": None},
            "patch",
        )
        assert edited.status_code == 200 and edited.json()["contact_email"] is None
        assert client.get("/api/v1/hiring-units?page_size=1").json()["total"] == 1
    else:
        assert (
            write(client, f"/hiring-units/{uuid4()}", {"is_active": False}, "patch").status_code
            == 403
        )


@pytest.mark.parametrize(
    "bad",
    [{"name": " "}, {"kind": "bad"}, {"is_active": None}, {"contact_email": "bad"}, {"extra": 1}],
)
def test_unit_input_validation(client, account, bad):
    account.role = UserRole.admin
    sign_in(client)
    assert (
        write(
            client, "/hiring-units", {"name": "Đơn vị giả", "kind": "department", **bad}
        ).status_code
        == 422
    )


def test_auth_csrf_not_found_and_query_validation(client, account, records):
    assert client.get("/api/v1/jobs").status_code == 401
    sign_in(client)
    assert client.post("/api/v1/jobs", json=payload(account, records)).status_code == 403
    assert client.put(f"/api/v1/jobs/{uuid4()}/members", json={"user_ids": []}).status_code == 403
    assert client.get(f"/api/v1/jobs/{uuid4()}").status_code == 404
    assert write(client, f"/jobs/{uuid4()}", {"title": "Mô phỏng"}, "patch").status_code == 404
    for query in ["page=0", "page_size=101", "status=bad", "owner_id=bad", "q=" + "x" * 201]:
        assert client.get("/api/v1/jobs?" + query).status_code == 422
