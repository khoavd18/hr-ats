"""T14: real database permissions, ranking, polling and synthetic upload isolation."""

import json
import logging
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.models import Application, Candidate, CvFile, Job, JobMember
from app.models.enums import AiLevel, ApplicationStage, ProcessingStatus
from app.models.users import UserRole
from tests.api.test_scoring import SAMPLES
from tests.api.test_scoring import records as records
from tests.api.test_scoring import runtime as runtime
from tests.auth_helpers import csrf_headers, sign_in


def get(client, job_id, **params):
    return client.get(f"/api/v1/jobs/{job_id}/applications", params=params)


def add(db_session, records, name="Ứng viên giả", **extra):
    candidate = Candidate(
        full_name=name,
        skills=["python", "sql"],
        current_title="Kỹ sư mô phỏng",
        years_experience=3.5,
        retention_until=date(2099, 1, 1),
    )
    db_session.add(candidate)
    db_session.flush()
    application = Application(
        candidate_id=candidate.id, job_id=records.job.id, owner_id=records.outsider.id, **extra
    )
    db_session.add(application)
    db_session.commit()
    return application, candidate


def test_level_then_score_order_ties_nulls_pagination_and_shared_counts(
    client, account, records, db_session
):
    sign_in(client)
    apps = []
    for level, score in [
        ("low", 99),
        ("high", 80),
        ("medium", 95),
        ("high", 90),
        ("insufficient", 100),
        ("medium", None),
    ]:
        app, _ = add(
            db_session,
            records,
            ai_status=ProcessingStatus.done,
            ai_level=AiLevel(level),
            ai_score=score,
        )
        apps.append(app)
    for status in (ProcessingStatus.pending, ProcessingStatus.running, ProcessingStatus.failed):
        add(db_session, records, ai_status=status)
    # Force equal score/time and verify ID gives stable pages across polls.
    apps[1].ai_score = 90
    apps[1].created_at = apps[3].created_at
    db_session.commit()
    result = get(client, records.job.id)
    assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
    data = result.json()
    assert data["total"] == 9
    assert [row["ai_level"] for row in data["items"]] == [
        "high",
        "high",
        "medium",
        "medium",
        "low",
        "insufficient",
        None,
        None,
        None,
    ]
    assert [row["id"] for row in data["items"][:2]] == sorted([str(apps[1].id), str(apps[3].id)])
    assert data["items"][2]["id"] == str(apps[2].id)
    assert data["ai_counts"] == dict(
        high=2, medium=2, low=1, insufficient=1, pending=1, running=1, failed=1
    )
    assert get(client, records.job.id, page=2, page_size=2).json()["items"] == data["items"][2:4]
    assert get(client, records.job.id, page=100).json()["items"] == []
    assert data["items"][0]["skills"] == ["python", "sql"]
    assert data["items"][0]["years_experience"] == "3.50"
    assert set(data["items"][0]) == {
        "id",
        "candidate_id",
        "candidate_name",
        "skills",
        "years_experience",
        "stage",
        "created_at",
        "ai_status",
        "ai_level",
    }
    for path in [f"/api/v1/jobs/{records.job.id}", "/api/v1/jobs"]:
        jobs = client.get(path).json()
        assert (jobs["items"][0] if "items" in jobs else jobs)["ai_counts"] == data["ai_counts"]
    newest = get(client, records.job.id, sort="created_at").json()["items"]
    assert [row["created_at"] for row in newest] == sorted(
        [row["created_at"] for row in newest], reverse=True
    )


def test_filters_search_literal_wildcards_totals_and_global_counts(
    client, account, records, db_session
):
    sign_in(client)
    app, _ = add(
        db_session,
        records,
        "Giả 100%_A",
        ai_status=ProcessingStatus.done,
        ai_level=AiLevel.high,
        ai_score=90,
        stage=ApplicationStage.interview,
    )
    add(
        db_session,
        records,
        "Giả khác",
        ai_status=ProcessingStatus.done,
        ai_level=AiLevel.low,
        ai_score=10,
    )
    # A stale level must not match the completed-level filter or inflate the high count.
    add(db_session, records, ai_status=ProcessingStatus.failed, ai_level=AiLevel.high)
    for params in [
        {"q": "%_"},
        {"q": "  giả 100  "},
        {"q": "SQL"},
        {"q": "mô phỏng"},
        {"stage": "interview", "ai_level": "high", "q": "giả"},
    ]:
        result = get(client, records.job.id, **params).json()
        assert result["ai_counts"]["high"] == 1
        assert result["ai_counts"]["failed"] == 1
        if params.get("q") in {"SQL", "mô phỏng"}:
            assert result["total"] == 3
        else:
            assert result["total"] == 1 and result["items"][0]["id"] == str(app.id)
    assert get(client, records.job.id, ai_level="high").json()["total"] == 1
    assert get(client, records.job.id, q="no such synthetic skill").json()["items"] == []


@pytest.mark.parametrize(
    "excluded", ["application_deleted", "candidate_deleted", "merged", "expired"]
)
def test_ineligible_rows_excluded_from_items_total_and_counts(
    client, account, records, db_session, excluded
):
    sign_in(client)
    application, candidate = add(
        db_session, records, ai_level=AiLevel.high, ai_status=ProcessingStatus.done
    )
    if excluded == "application_deleted":
        application.deleted_at = datetime.now(UTC)
    elif excluded == "candidate_deleted":
        candidate.deleted_at = datetime.now(UTC)
    elif excluded == "merged":
        candidate.merged_into_id = records.candidate.id
    else:
        candidate.retention_until = date(2000, 1, 1)
    db_session.commit()
    data = get(client, records.job.id).json()
    assert data["items"] == [] and data["total"] == 0 and not any(data["ai_counts"].values())
    assert not any(client.get("/api/v1/jobs").json()["items"][0]["ai_counts"].values())


@pytest.mark.parametrize("role", ["admin", "lead", "owner", "member", "outsider", "revoked"])
def test_ranking_requires_current_job_permission_even_when_empty(
    client, account, records, db_session, role
):
    actor = account if role == "admin" else records.outsider
    if role == "lead":
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
    assert get(client, records.job.id).status_code == (
        403 if role in {"outsider", "revoked"} else 200
    )


@pytest.mark.parametrize(
    "params",
    [
        {"stage": "bad"},
        {"ai_level": "bad"},
        {"sort": "id"},
        {"page": 0},
        {"page_size": 101},
        {"q": "x" * 201},
    ],
)
def test_invalid_filters(client, account, records, params):
    sign_in(client)
    assert get(client, records.job.id, **params).status_code == 422


def test_unauthenticated_and_missing(client, account, records):
    assert get(client, records.job.id).status_code == 401
    sign_in(client)
    assert get(client, uuid4()).status_code == 404
    assert get(client, "not-a-uuid").status_code == 422


def test_ten_real_synthetic_cvs_ranked_with_independent_file_errors(
    client, account, records, db_session, caplog
):
    sign_in(client)
    fixture = json.loads((SAMPLES / "jobs.json").read_text(encoding="utf-8"))
    for key, value in fixture["jobs"][0].items():
        if key != "id":
            setattr(records.job, key, value)
    db_session.commit()
    selected = []
    for level in ("high", "medium", "low"):
        for path in sorted(SAMPLES.glob("cv_*.json")):
            label = json.loads(path.read_text(encoding="utf-8"))
            if (
                label["layout"] != "scan"
                and fixture["expected_level"][label["id"]]["job_backend"] == level
            ):
                selected.append(label)
                if (
                    sum(
                        fixture["expected_level"][item["id"]]["job_backend"] == level
                        for item in selected
                    )
                    == {"high": 3, "medium": 1, "low": 6}[level]
                ):
                    break
    assert len(selected) == 10
    files = [
        ("files", (item["file_name"], (SAMPLES / item["file_name"]).read_bytes()))
        for item in selected
    ]
    files.insert(2, ("files", ("invalid.exe", b"MZ synthetic executable")))
    files.insert(6, ("files", ("broken.pdf", b"%PDF-1.7\nsynthetic broken document")))
    caplog.set_level(logging.DEBUG, logger="app.http")
    result = client.post(
        "/api/v1/cv-files",
        headers=csrf_headers(client),
        files=files,
        data={"job_id": str(records.job.id)},
    )
    assert result.status_code == 200
    items = result.json()["items"]
    assert len(items) == 12 and items[2]["error"]["code"] == "INVALID_FILE_TYPE"
    ranking = get(client, records.job.id).json()
    assert ranking["total"] == 10
    actual = [row["ai_level"] for row in ranking["items"]]
    assert actual == ["high"] * 3 + ["medium"] + ["low"] * 6
    for index, item in enumerate(items):
        if index == 2:
            continue
        status = client.get(f"/api/v1/cv-files/{item['cv_file']['id']}")
        assert status.status_code == 200
        data = status.json()
        assert data["status"] == ("failed" if index == 6 else "done")
        if index == 6:
            assert data["processing_error"] == {
                "code": "CV_PROCESSING_FAILED",
                "message": "Không thể đọc CV. Vui lòng kiểm tra tệp và tải lại.",
            }
            assert data["application_id"] is None
        else:
            assert data["ai_status"] == "done" and data["application_id"] is not None
            assert data["processing_error"] is None
    # Metadata polling never reflects arbitrary stored error strings.
    broken = db_session.get(CvFile, UUID(items[6]["cv_file"]["id"]))
    broken.error = "SYNTHETIC_PRIVATE_ERROR"
    db_session.commit()
    assert "SYNTHETIC_PRIVATE_ERROR" not in client.get(f"/api/v1/cv-files/{broken.id}").text
    polls = [
        record
        for record in caplog.records
        if record.name == "app.http"
        and record.route in {"/cv-files/{cv_file_id}", "/jobs/{job_id}/applications"}
    ]
    assert polls and all(record.levelno == logging.DEBUG for record in polls)
    assert not list(
        db_session.scalars(select(Application).where(Application.stage != ApplicationStage.new))
    )


def test_file_access_via_other_job_does_not_reveal_original_application(
    client, account, records, db_session
):
    sign_in(client)
    response = client.post(
        "/api/v1/cv-files",
        headers=csrf_headers(client),
        files=[("files", ("synthetic.pdf", (SAMPLES / "cv_0001.pdf").read_bytes()))],
        data={"job_id": str(records.job.id)},
    )
    file_id = response.json()["items"][0]["cv_file"]["id"]
    cv = db_session.get(CvFile, UUID(file_id))
    other = Job(
        title="Job khác giả",
        description="Mô tả giả",
        hiring_unit_id=records.job.hiring_unit_id,
        owner_id=records.outsider.id,
    )
    db_session.add(other)
    db_session.flush()
    db_session.add(
        Application(candidate_id=cv.candidate_id, job_id=other.id, owner_id=records.outsider.id)
    )
    db_session.commit()
    sign_in(client, records.outsider.email)
    data = client.get(f"/api/v1/cv-files/{file_id}").json()
    assert data["application_id"] is None and data["ai_status"] is None


def test_polling_errors_remain_info_level(client, account, records, caplog):
    caplog.set_level(logging.DEBUG, logger="app.http")
    assert get(client, records.job.id).status_code == 401
    record = next(record for record in caplog.records if record.name == "app.http")
    assert record.levelno == logging.INFO
