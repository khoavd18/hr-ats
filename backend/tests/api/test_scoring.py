"""T12: real PostgreSQL/storage/extraction, fixed Celery workflow, offline LLM."""

import json
import logging
from contextlib import contextmanager
from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.ai.llm import FakeLLM
from app.api.cv_files import storage_dependency
from app.core.config import REPO_ROOT
from app.core.security import hash_password
from app.models import Activity, Application, Candidate, CvFile, HiringUnit, Job, JobMember, User
from app.models.enums import ActivityType, ApplicationStage, HiringUnitKind, ProcessingStatus
from app.models.users import UserRole
from app.services import applications
from app.storage import LocalStorage
from app.workers import tasks
from tests.auth_helpers import PASSWORD, csrf_headers, sign_in

SAMPLES = REPO_ROOT / "data/sample_cvs"
LONG_TEXT = "[TÊN]\nKỹ năng: Python, SQL\nSố năm kinh nghiệm: 5 năm\n" + (
    "Kinh nghiệm mô phỏng: xây dựng dịch vụ và kiểm thử phần mềm.\n" * 8
)


@pytest.fixture
def runtime(app, db_session, tmp_path, monkeypatch):
    storage = LocalStorage(tmp_path / "scoring")
    app.dependency_overrides[storage_dependency] = lambda: storage

    @contextmanager
    def worker_session():
        yield db_session

    monkeypatch.setattr(tasks, "worker_session", worker_session)
    monkeypatch.setattr(tasks, "build_storage", lambda settings: storage)
    return storage


@pytest.fixture
def records(db_session, account, runtime):
    candidate = Candidate(
        full_name="Nhân Vật Giả", retention_until=date(2099, 1, 1), anonymized_text=LONG_TEXT
    )
    unit = HiringUnit(name="Đơn vị giả", kind=HiringUnitKind.department)
    outsider = User(
        email="scoring-outsider@example.invalid",
        full_name="Ngoài Job giả",
        role=UserRole.recruiter,
        password_hash=hash_password(PASSWORD),
    )
    db_session.add_all([unit, candidate, outsider])
    db_session.flush()
    job = Job(
        hiring_unit_id=unit.id,
        owner_id=account.id,
        title="Python",
        description="SQL",
        must_have=["Python"],
        nice_to_have=["SQL"],
    )
    db_session.add(job)
    db_session.commit()
    return SimpleNamespace(candidate=candidate, job=job, outsider=outsider)


def create(client, records, **extra):
    return client.post(
        "/api/v1/applications",
        headers=csrf_headers(client),
        json={"candidate_id": str(records.candidate.id), "job_id": str(records.job.id), **extra},
    )


def post(client, path):
    return client.post("/api/v1" + path, headers=csrf_headers(client))


def scored_row(client, records, session):
    response = create(client, records)
    assert response.status_code == 201, response.text
    application = session.get(Application, UUID(response.json()["id"]))
    session.refresh(application)
    assert application.ai_status == "done"
    return application


def score_activities(session):
    return list(session.scalars(select(Activity).where(Activity.type == ActivityType.ai_scored)))


def test_bank_create_scoring_rescore_and_no_recruitment_side_effects(
    client, account, records, db_session, monkeypatch
):
    sign_in(client)
    sent = []

    class RecordingFake(FakeLLM):
        def complete_json(self, **kwargs):
            sent.append(json.loads(kwargs["user"]))
            return super().complete_json(**kwargs)

    monkeypatch.setattr(tasks, "get_llm_client", lambda settings: RecordingFake())
    application = scored_row(client, records, db_session)
    assert application.ai_level == "high" and application.ai_score == 100
    assert application.stage == "new" and application.owner_id == records.job.owner_id
    assert application.ai_model == "fake-v1" and application.ai_prompt_version == "v1"
    assert application.ai_scored_at is not None
    assert application.ai_reasons and application.ai_criteria and application.ai_flags == []
    assert sent[0]["anonymized_text"] == records.candidate.anonymized_text
    assert records.candidate.full_name not in json.dumps(sent, ensure_ascii=False)
    assert len(score_activities(db_session)) == 1
    activity = score_activities(db_session)[0]
    assert activity.actor_id is None and activity.application_id == application.id
    assert activity.payload == {"ai_level": "high", "ai_score": 100}
    tasks.score_application.delay(str(application.id))
    assert len(sent) == 1 and len(score_activities(db_session)) == 1
    duplicate = create(client, records)
    assert duplicate.status_code == 409 and len(sent) == 1
    records.job.must_have = ["Rust"]
    application.stage = ApplicationStage.interview
    db_session.commit()
    response = post(client, f"/applications/{application.id}/rescore")
    assert response.status_code == 202 and response.json()["ai_status"] == "pending"
    assert response.headers["cache-control"] == "no-store"
    db_session.refresh(application)
    assert application.ai_status == "done" and application.ai_level == "low"
    assert application.stage == "interview" and application.ai_score == 25
    assert len(score_activities(db_session)) == 2
    assert db_session.scalar(select(func.count()).select_from(Application)) == 1


@pytest.mark.parametrize("role", ["admin", "lead", "owner", "member", "outsider", "revoked"])
def test_all_three_endpoints_enforce_current_job_scope(client, account, records, db_session, role):
    if role == "admin":
        actor = account
    else:
        actor = records.outsider
        if role == "lead":
            actor.role = UserRole.lead
        elif role == "owner":
            records.job.owner_id = actor.id
        elif role in {"member", "revoked"}:
            membership = JobMember(job_id=records.job.id, user_id=actor.id)
            db_session.add(membership)
            db_session.commit()
            if role == "revoked":
                db_session.delete(membership)
        db_session.commit()
    application = Application(
        candidate_id=records.candidate.id,
        job_id=records.job.id,
        owner_id=actor.id,
        ai_status=ProcessingStatus.failed,
    )
    db_session.add(application)
    db_session.commit()
    sign_in(client, actor.email)
    expected = 403 if role in {"outsider", "revoked"} else 202
    assert post(client, f"/applications/{application.id}/rescore").status_code == expected
    assert post(client, f"/jobs/{records.job.id}/rescore").status_code == expected
    # Existing candidate/job still requires authorization before revealing duplication.
    response = create(client, records)
    assert response.status_code == (403 if expected == 403 else 409)


def test_auth_csrf_unknown_fields_and_missing_resources(client, account, records, db_session):
    payload = {"candidate_id": str(records.candidate.id), "job_id": str(records.job.id)}
    assert client.post("/api/v1/applications", json=payload).status_code == 403
    client.get("/api/v1/auth/csrf")
    assert create(client, records).status_code == 401
    sign_in(client)
    assert client.post("/api/v1/applications", json=payload).status_code == 403
    assert create(client, records, owner_id=str(account.id)).status_code == 422
    assert create(client, records, candidate_id="bad").status_code == 422
    assert create(client, records, job_id=str(uuid4())).status_code == 404
    assert create(client, records, candidate_id=str(uuid4())).status_code == 404
    assert post(client, f"/applications/{uuid4()}/rescore").status_code == 404
    assert post(client, f"/jobs/{uuid4()}/rescore").status_code == 404
    assert post(client, "/jobs/not-a-uuid/rescore").status_code == 422
    assert not score_activities(db_session)


@pytest.mark.parametrize("ineligible", ["deleted", "merged", "expired"])
def test_bank_and_workers_do_not_process_ineligible_candidates(
    client, account, records, db_session, ineligible, monkeypatch
):
    sign_in(client)
    application = scored_row(client, records, db_session)
    if ineligible == "deleted":
        records.candidate.deleted_at = datetime.now(UTC)
    elif ineligible == "merged":
        other = Candidate(full_name="Ứng viên giả khác", retention_until=date(2099, 1, 1))
        db_session.add(other)
        db_session.flush()
        records.candidate.merged_into_id = other.id
    else:
        records.candidate.retention_until = date(2000, 1, 1)
    db_session.commit()
    assert create(client, records).status_code == 404
    assert post(client, f"/applications/{application.id}/rescore").status_code == 404
    before = len(score_activities(db_session))
    assert post(client, f"/jobs/{records.job.id}/rescore").status_code == 202
    assert len(score_activities(db_session)) == before
    applications.reset_score(application)
    db_session.commit()
    monkeypatch.setattr(tasks, "get_llm_client", lambda settings: pytest.fail("Must not call LLM"))
    tasks.score_application.delay(str(application.id))
    assert application.ai_status == "failed"


def test_soft_deleted_application_is_not_reused_or_rescored(client, account, records, db_session):
    sign_in(client)
    old = scored_row(client, records, db_session)
    old.deleted_at = datetime.now(UTC)
    db_session.commit()
    assert post(client, f"/applications/{old.id}/rescore").status_code == 404
    new = scored_row(client, records, db_session)
    assert new.id != old.id
    before = len(score_activities(db_session))
    post(client, f"/jobs/{records.job.id}/rescore")
    assert len(score_activities(db_session)) == before + 1


@pytest.mark.parametrize("failure", ["llm", "activity", "missing_text"])
def test_failed_score_is_atomic_safe_and_does_not_block_next_application(
    client, account, records, db_session, monkeypatch, caplog, failure
):
    sign_in(client)
    caplog.set_level(logging.INFO)
    marker = "SYNTHETIC_PRIVATE_FAILURE_MARKER"

    def fail(*args, **kwargs):
        raise RuntimeError(marker)

    with monkeypatch.context() as patch:
        if failure == "llm":
            patch.setattr(tasks, "score_cv", fail)
        elif failure == "activity":
            patch.setattr(tasks, "log_activity", fail)
        else:
            records.candidate.anonymized_text = None
            db_session.commit()
            patch.setattr(tasks, "get_llm_client", lambda settings: pytest.fail("No raw fallback"))
        response = create(client, records)
        assert response.status_code == 201
        application = db_session.get(Application, UUID(response.json()["id"]))
        db_session.refresh(application)
        assert application.ai_status == "failed" and application.ai_score is None
        assert application.ai_level is application.ai_model is application.ai_scored_at is None
        assert application.ai_criteria == application.ai_reasons == application.ai_flags == []
        assert not score_activities(db_session)
    assert marker not in caplog.text
    records.candidate.anonymized_text = LONG_TEXT
    db_session.commit()
    assert post(client, f"/applications/{application.id}/rescore").status_code == 202
    db_session.refresh(application)
    assert application.ai_status == "done" and len(score_activities(db_session)) == 1


def test_queue_failures_are_visible_and_retryable(
    client, account, records, db_session, monkeypatch
):
    sign_in(client)

    def fail(*args):
        raise RuntimeError("synthetic queue failure")

    original = tasks.score_application.delay
    monkeypatch.setattr(tasks.score_application, "delay", fail)
    response = create(client, records)
    assert response.status_code == 201 and response.json()["ai_status"] == "failed"
    application_id = response.json()["id"]
    assert post(client, f"/applications/{application_id}/rescore").status_code == 503
    monkeypatch.setattr(tasks.rescore_job, "delay", fail)
    assert post(client, f"/jobs/{records.job.id}/rescore").status_code == 503
    monkeypatch.setattr(tasks.score_application, "delay", original)
    assert post(client, f"/applications/{application_id}/rescore").status_code == 202
    assert db_session.get(Application, UUID(application_id)).ai_status == "done"


def test_bulk_rescore_isolates_failures_and_preserves_stages(
    client, account, records, db_session, monkeypatch
):
    sign_in(client)
    first = scored_row(client, records, db_session)
    other = Candidate(
        full_name="Ứng viên giả khác",
        anonymized_text=LONG_TEXT + "\nSECOND_MARKER",
        retention_until=date(2099, 1, 1),
    )
    db_session.add(other)
    db_session.commit()
    second = scored_row(client, SimpleNamespace(candidate=other, job=records.job), db_session)
    first.stage = ApplicationStage.hired
    db_session.commit()
    original = tasks.score_cv

    def fail_one(text, **kwargs):
        if "SECOND_MARKER" in text:
            raise RuntimeError("synthetic provider failure")
        return original(text, **kwargs)

    monkeypatch.setattr(tasks, "score_cv", fail_one)
    result = post(client, f"/jobs/{records.job.id}/rescore")
    assert result.status_code == 202
    db_session.refresh(first)
    db_session.refresh(second)
    assert first.ai_status == "done" and first.stage == "hired"
    assert second.ai_status == "failed" and second.stage == "new"
    assert len(score_activities(db_session)) == 3


def test_upload_to_job_dedupes_application_and_scores_after_commit(
    client, account, records, db_session, monkeypatch
):
    sign_in(client)
    data = (SAMPLES / "cv_0001.pdf").read_bytes()

    def upload(data):
        result = client.post(
            "/api/v1/cv-files",
            headers=csrf_headers(client),
            files=[("files", ("synthetic.pdf", data, "application/pdf"))],
            data={"job_id": str(records.job.id)},
        )
        assert result.status_code == 200, result.text
        file_id = UUID(result.json()["items"][0]["cv_file"]["id"])
        row = db_session.get(CvFile, file_id)
        db_session.refresh(row)
        assert row.status == "done"
        return row

    first = upload(data)
    application = db_session.scalar(select(Application))
    assert application.candidate_id == first.candidate_id and application.ai_status == "done"
    assert application.owner_id == records.job.owner_id and application.stage == "new"
    second = upload(data + b"\n% synthetic revision")
    assert second.candidate_id == first.candidate_id
    assert db_session.scalar(select(func.count()).select_from(Application)) == 1
    assert len(score_activities(db_session)) == 2
    before = len(score_activities(db_session))
    upload(data)
    tasks.process_cv_file.delay(str(first.id))
    assert len(score_activities(db_session)) == before


def test_upload_scoring_publish_failure_keeps_cv_and_candidate_done(
    client, account, records, db_session, monkeypatch
):
    sign_in(client)

    def fail(*args):
        raise RuntimeError("synthetic queue failure")

    monkeypatch.setattr(tasks.score_application, "delay", fail)
    result = client.post(
        "/api/v1/cv-files",
        headers=csrf_headers(client),
        files=[("files", ("fake.pdf", (SAMPLES / "cv_0001.pdf").read_bytes()))],
        data={"job_id": str(records.job.id)},
    )
    row = db_session.get(CvFile, UUID(result.json()["items"][0]["cv_file"]["id"]))
    assert row.status == "done" and row.candidate_id is not None
    assert db_session.scalar(select(Application)).ai_status == "failed"


@pytest.mark.parametrize("task", ["score_application", "rescore_job"])
def test_worker_ignores_invalid_or_missing_ids(task, runtime):
    for value in ("invalid", None, str(uuid4())):
        getattr(tasks, task).run(value)


def test_fake_llm_end_to_end_sample_jobs_matches_at_least_seventy_percent(
    client, account, db_session, runtime, caplog, record_property
):
    """Count the ten scan-only CVs against the denominator, without requiring OCR here."""
    caplog.set_level(logging.WARNING)
    sign_in(client)
    fixture = json.loads((SAMPLES / "jobs.json").read_text(encoding="utf-8"))
    unit = HiringUnit(name="Đơn vị đánh giá giả", kind=HiringUnitKind.department)
    db_session.add(unit)
    db_session.flush()
    jobs = {}
    for job_data in fixture["jobs"]:
        values = {key: value for key, value in job_data.items() if key != "id"}
        job = Job(**values, hiring_unit_id=unit.id, owner_id=account.id)
        db_session.add(job)
        db_session.flush()
        jobs[job_data["id"]] = job
    db_session.commit()
    matched = evaluated = matched_cvs = 0
    observed = set()
    for path in sorted(SAMPLES.glob("cv_*.json")):
        label = json.loads(path.read_text(encoding="utf-8"))
        if label["layout"] == "scan":
            continue
        upload = client.post(
            "/api/v1/cv-files",
            headers=csrf_headers(client),
            files=[("files", (label["file_name"], (SAMPLES / label["file_name"]).read_bytes()))],
        )
        assert upload.status_code == 200, upload.text
        cv_file = db_session.get(CvFile, UUID(upload.json()["items"][0]["cv_file"]["id"]))
        assert cv_file.status == "done"
        candidate = db_session.get(Candidate, cv_file.candidate_id)
        assert label["full_name"] not in candidate.anonymized_text
        cv_matches = 0
        for job_key, job in jobs.items():
            application = scored_row(
                client, SimpleNamespace(candidate=candidate, job=job), db_session
            )
            expected = fixture["expected_level"][label["id"]][job_key]
            matched += application.ai_level == expected
            cv_matches += application.ai_level == expected
            evaluated += 1
            observed.add(application.ai_level.value)
            assert application.ai_score is not None and application.stage == "new"
        matched_cvs += cv_matches == len(jobs)
    total = sum(len(values) for values in fixture["expected_level"].values())
    assert evaluated == 250 and total == 300
    assert observed >= {"high", "medium", "low"}  # prevents a trivial all-low fake
    report = (
        f"{matched}/{evaluated} evaluated; {matched}/{total} total; "
        f"{matched_cvs}/{len(fixture['expected_level'])} CVs match all five jobs"
    )
    record_property("sample_scoring", report)
    print(f"T12 sample scoring: {report}")
    assert matched / total >= 0.70
    assert matched_cvs / len(fixture["expected_level"]) >= 0.70
