"""T10 acceptance slice: HTTP upload, real storage/extraction/DB, eager Celery and FakeLLM."""

import json
import logging
from contextlib import contextmanager
from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from docx import Document
from sqlalchemy import func, select

from app.ai.embed import FakeEmbedder
from app.ai.extract import ExtractionError
from app.ai.llm import FakeLLM, LLMValidationError
from app.api.cv_files import storage_dependency
from app.core.config import REPO_ROOT, get_settings
from app.models import Application, Candidate, CvFile, User, UserRole
from app.models.enums import ProcessingStatus
from app.services import embeddings
from app.storage import LocalStorage, StorageError
from app.workers import tasks
from tests.auth_helpers import csrf_headers, sign_in

SAMPLES = REPO_ROOT / "data/sample_cvs"
LABELS = [
    json.loads(path.read_text(encoding="utf-8")) for path in sorted(SAMPLES.glob("cv_*.json"))
]
DIGITAL = [label for label in LABELS if label["layout"] != "scan"][:10]


def cv_docx(text):
    document = Document()
    document.core_properties.author = "Synthetic T10 fixture"
    for line in text.splitlines():
        document.add_paragraph(line)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


@pytest.fixture
def runtime(app, db_session, tmp_path, monkeypatch):
    storage = LocalStorage(tmp_path / "pipeline")
    app.dependency_overrides[storage_dependency] = lambda: storage

    @contextmanager
    def session():
        yield db_session

    monkeypatch.setattr(tasks, "worker_session", session)
    monkeypatch.setattr(tasks, "build_storage", lambda settings: storage)
    return storage


def upload(client, *documents):
    result = client.post(
        "/api/v1/cv-files",
        files=[("files", (name, data, "application/octet-stream")) for name, data in documents],
        headers=csrf_headers(client),
    )
    assert result.status_code == 200, result.text
    return result.json()["items"]


def get_row(session, item):
    assert item["error"] is None
    return session.get(CvFile, UUID(item["cv_file"]["id"]))


def count_candidates(session):
    return session.scalar(select(func.count()).select_from(Candidate))


def test_upload_ten_labeled_cvs_dedupe_cross_format_and_isolate_corruption(
    client, account, db_session, runtime, monkeypatch, caplog
):
    caplog.set_level(logging.INFO)
    assert sign_in(client).status_code == 200
    sent = []

    class RecordingFake(FakeLLM):
        def complete_json(self, **kwargs):
            sent.append(kwargs["user"])
            return super().complete_json(**kwargs)

    monkeypatch.setattr(tasks, "get_llm_client", lambda settings: RecordingFake())
    embedded = []

    class RecordingEmbedder(FakeEmbedder):
        def embed(self, texts):
            embedded.extend(texts)
            return super().embed(texts)

    monkeypatch.setattr(
        embeddings, "get_embedder", lambda settings: RecordingEmbedder(settings.embedding_dim)
    )
    documents = [
        (label["file_name"], (SAMPLES / label["file_name"]).read_bytes()) for label in DIGITAL
    ]
    documents.insert(4, ("corrupt.pdf", b"%PDF-1.7\nsynthetic corrupt document"))
    items = upload(client, *documents)
    assert len(items) == 11 and count_candidates(db_session) == 10
    failed = get_row(db_session, items.pop(4))
    assert failed.status == ProcessingStatus.failed and failed.error == "Không đọc được nội dung CV"
    assert failed.candidate_id is None
    for label, item in zip(DIGITAL, items, strict=True):
        row = get_row(db_session, item)
        candidate = db_session.get(Candidate, row.candidate_id)
        assert row.status == ProcessingStatus.done and row.error is None
        assert row.parse_model == "fake-v1" and row.parse_prompt_version == "v1"
        assert row.extraction_method in {"pdf_text", "docx"} and row.extracted_text
        assert candidate.email == label["email"]
        assert candidate.phone == "+84" + label["phone"].replace(" ", "")[1:]
        assert candidate.retention_until == tasks.retention_date(
            datetime.now(ZoneInfo(get_settings().tz)).date(), get_settings().data_retention_months
        )
        assert candidate.consent_at is None
        assert candidate.anonymized_text
        assert len(candidate.embedding) == get_settings().embedding_dim
        assert candidate.embedding == pytest.approx(
            FakeEmbedder(get_settings().embedding_dim).embed([candidate.anonymized_text])[0]
        )
        assert label["full_name"] not in candidate.anonymized_text
        assert candidate.anonymized_text in embedded
        assert all(
            label["email"] not in text and label["full_name"] not in text for text in embedded
        )
        assert label["date_of_birth"] not in candidate.anonymized_text
        assert label["location"] not in candidate.anonymized_text
        assert "email" not in row.parsed_json and "phone" not in row.parsed_json
        # Original contacts stay in local persistence, never in any parse request/log.
        assert all(label["email"] not in user and label["phone"] not in user for user in sent)
        assert label["email"] not in caplog.text and label["phone"] not in caplog.text
    original = get_row(db_session, items[0])
    candidate_id = original.candidate_id
    label = DIGITAL[0]
    revised = cv_docx(
        f"Họ tên: {label['full_name']}\nEmail: {label['email'].upper()}\n"
        "Chức danh: Chuyên viên mô phỏng\nKỹ năng: JS, Python\nSố năm kinh nghiệm: 7"
    )
    revision = get_row(db_session, upload(client, ("revision.docx", revised))[0])
    assert revision.id != original.id and revision.candidate_id == candidate_id
    assert revision.status == ProcessingStatus.done and count_candidates(db_session) == 10
    candidate = db_session.get(Candidate, candidate_id)
    assert candidate.current_title == "Chuyên viên mô phỏng"
    assert candidate.years_experience == 7 and candidate.skills == ["javascript", "python"]
    assert candidate.phone == "+84" + label["phone"].replace(" ", "")[1:]
    before = len(sent)
    duplicate = upload(client, documents[0])[0]
    assert duplicate["duplicate"] and duplicate["cv_file"]["id"] == str(original.id)
    tasks.process_cv_file.delay(str(original.id))
    tasks.process_cv_file.delay(str(failed.id))
    assert len(sent) == before and count_candidates(db_session) == 10
    assert any(record.name == "app.ai.llm" for record in caplog.records)
    assert all(label["email"].casefold() not in user.casefold() for user in sent)
    assert db_session.scalar(select(func.count()).select_from(Application)) == 0


@pytest.mark.parametrize(
    "stage", ["storage", "extract", "redact", "parse", "save", "enrich", "application"]
)
def test_every_stage_fails_safely_and_next_file_succeeds(
    client, account, db_session, runtime, monkeypatch, caplog, stage
):
    caplog.set_level(logging.INFO)
    sign_in(client)
    target, name = {
        "storage": (runtime, "get"),
        "extract": (tasks, "extract_text"),
        "redact": (tasks, "redact_contacts"),
        "parse": (tasks, "parse_cv"),
        "save": (tasks, "save_candidate"),
        "enrich": (tasks, "anonymize_and_embed"),
        "application": (tasks, "create_and_score_application"),
    }[stage]
    original = getattr(target, name)
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("synthetic-private-body sentinel@example.invalid +84900000999")
        return original(*args, **kwargs)

    monkeypatch.setattr(target, name, fail_once)
    items = upload(
        client,
        *[
            (label["file_name"], (SAMPLES / label["file_name"]).read_bytes())
            for label in DIGITAL[:2]
        ],
    )
    failed, good = [get_row(db_session, item) for item in items]
    assert failed.status == ProcessingStatus.failed and failed.error
    assert failed.candidate_id is None and failed.parsed_json is None
    assert good.status == ProcessingStatus.done and good.candidate_id
    assert count_candidates(db_session) == 1
    assert "synthetic-private-body" not in failed.error + caplog.text
    assert "sentinel@example.invalid" not in failed.error + caplog.text
    assert "+84900000999" not in failed.error + caplog.text


def test_failed_new_revision_rolls_back_candidate_update(
    client, account, db_session, runtime, monkeypatch
):
    sign_in(client)
    source = cv_docx("Họ tên: Nhân vật giả\nEmail: rollback@example.invalid\nKỹ năng: Python")
    first = get_row(db_session, upload(client, ("first.docx", source))[0])
    original_id = first.candidate_id

    def fail(*args):
        raise StorageError("synthetic-private-hook-failure")

    monkeypatch.setattr(tasks, "create_and_score_application", fail)
    source = cv_docx("Họ tên: Tên sửa giả\nEmail: rollback@example.invalid\nKỹ năng: JS")
    revision = get_row(db_session, upload(client, ("second.docx", source))[0])
    assert revision.status == ProcessingStatus.failed and revision.candidate_id is None
    old = db_session.get(Candidate, original_id)
    assert old.full_name == "Nhân vật giả" and old.skills == ["python"]
    assert count_candidates(db_session) == 1


def test_phone_only_match_updates_same_candidate(client, account, db_session, runtime):
    sign_in(client)
    first = get_row(
        db_session,
        upload(
            client,
            (
                "one.docx",
                cv_docx("Họ tên: Nhân vật giả\nĐiện thoại: 0900 000 123\nKỹ năng: Python"),
            ),
        )[0],
    )
    second = get_row(
        db_session,
        upload(
            client,
            (
                "two.docx",
                cv_docx("Họ tên: Nhân vật giả\nĐiện thoại: +84 (900) 000-123\nKỹ năng: JS"),
            ),
        )[0],
    )
    assert first.candidate_id == second.candidate_id and count_candidates(db_session) == 1
    assert db_session.get(Candidate, first.candidate_id).phone == "+84900000123"


def test_t11_pipeline_cosine_top_k_and_real_duplicate_suggestion(
    client, account, db_session, runtime
):
    sign_in(client)
    items = upload(
        client,
        ("python.docx", cv_docx("Họ tên: Nhân Vật Giả\nKỹ năng: Python SQL FastAPI")),
        ("react.docx", cv_docx("Họ tên: Người Giả Khác\nKỹ năng: React CSS Typescript")),
        ("excel.docx", cv_docx("Họ tên: Người Giả Nữa\nKỹ năng: Excel Bookkeeping Tax")),
    )
    rows = [get_row(db_session, item) for item in items]
    candidate = db_session.get(Candidate, rows[0].candidate_id)
    vector = FakeEmbedder(get_settings().embedding_dim).embed(["Python SQL FastAPI"])[0]
    distance = Candidate.embedding.cosine_distance(vector)
    hits = db_session.execute(
        select(Candidate.id, distance.label("distance"))
        .where(Candidate.deleted_at.is_(None), Candidate.embedding.is_not(None))
        .order_by(distance, Candidate.id)
        .limit(2)
    ).all()
    assert len(hits) == 2 and hits[0].id == candidate.id
    assert hits[0].distance < hits[1].distance
    revision = get_row(
        db_session,
        upload(
            client, ("possible.docx", cv_docx("Họ tên: nhan vat gia\nKỹ năng: Python SQL FastAPI"))
        )[0],
    )
    assert revision.status == ProcessingStatus.done
    assert revision.candidate_id != candidate.id
    assert revision.parsed_json["possible_duplicate_of"] == str(candidate.id)
    assert count_candidates(db_session) == 4


def test_t11_encoder_failure_and_wrong_dimension_roll_back_revision(
    client, account, db_session, runtime, monkeypatch, caplog
):
    sign_in(client)
    first = get_row(
        db_session,
        upload(
            client,
            (
                "original.docx",
                cv_docx("Họ tên: Nhân Vật Giả\nEmail: vector@example.invalid\nKỹ năng: SQL"),
            ),
        )[0],
    )
    original = db_session.get(Candidate, first.candidate_id)
    old_text, old_vector = original.anonymized_text, list(original.embedding)

    class BrokenEmbedder:
        def embed(self, texts):
            return [[1.0, 0.0]]

    monkeypatch.setattr(embeddings, "get_embedder", lambda settings: BrokenEmbedder())
    failed = get_row(
        db_session,
        upload(
            client,
            (
                "revision.docx",
                cv_docx("Họ tên: Tên Sửa Giả\nEmail: vector@example.invalid\nKỹ năng: Python"),
            ),
        )[0],
    )
    assert failed.status == ProcessingStatus.failed and failed.candidate_id is None
    db_session.refresh(original)
    assert original.full_name == "Nhân Vật Giả" and original.anonymized_text == old_text
    assert original.embedding == pytest.approx(old_vector)
    assert "vector@example.invalid" not in caplog.text + failed.error


def test_without_contacts_creates_distinct_candidates_until_embedding_exists(
    client, account, db_session, runtime
):
    sign_in(client)
    items = upload(
        client,
        ("one.docx", cv_docx("Họ tên: Nhân vật giả\nKỹ năng: Python")),
        ("two.docx", cv_docx("Họ tên: Nhân vật giả\nKỹ năng: JS")),
    )
    rows = [get_row(db_session, item) for item in items]
    assert all(row.status == ProcessingStatus.done for row in rows)
    assert rows[0].candidate_id != rows[1].candidate_id
    assert all("possible_duplicate_of" not in row.parsed_json for row in rows)


def test_unknown_name_stays_null_in_parse_and_no_consent_is_invented(
    client, account, db_session, runtime
):
    sign_in(client)
    row = get_row(db_session, upload(client, ("unknown.docx", cv_docx("Kỹ năng: Python")))[0])
    assert row.status == ProcessingStatus.done and row.parsed_json["full_name"] is None
    candidate = db_session.get(Candidate, row.candidate_id)
    assert candidate.full_name == "Chưa xác định" and candidate.consent_at is None


def test_worker_ignores_unknown_invalid_and_deleted_ids(
    client, account, db_session, runtime, monkeypatch
):
    sign_in(client)
    # Hold delivery to set up a genuinely pending, then soft deleted row.
    monkeypatch.setattr(tasks.process_cv_file, "delay", lambda *args: None)
    label = DIGITAL[0]
    row = get_row(
        db_session,
        upload(client, (label["file_name"], (SAMPLES / label["file_name"]).read_bytes()))[0],
    )
    row.deleted_at = datetime.now(UTC)
    db_session.commit()
    for value in (str(row.id), str(uuid4()), "invalid-id", None):
        tasks.process_cv_file.run(value)
    assert row.status == ProcessingStatus.pending and count_candidates(db_session) == 0


def test_possible_duplicate_hook_flags_file_without_auto_merge(
    client, account, db_session, runtime, monkeypatch
):
    sign_in(client)
    vector = [1.0] + [0.0] * (get_settings().embedding_dim - 1)
    previous = Candidate(
        full_name="TRẦN ĐỨC MÔ PHỎNG", retention_until=datetime.now().date(), embedding=vector
    )
    db_session.add(previous)
    db_session.commit()

    def enrich(session, candidate, text):
        candidate.embedding = vector

    monkeypatch.setattr(tasks, "anonymize_and_embed", enrich)
    row = get_row(
        db_session,
        upload(client, ("suggestion.docx", cv_docx("Họ tên: tran duc mo phong\nKỹ năng: Python")))[
            0
        ],
    )
    assert row.status == ProcessingStatus.done
    assert row.parsed_json["possible_duplicate_of"] == str(previous.id)
    assert row.candidate_id != previous.id and count_candidates(db_session) == 2
    assert db_session.get(Candidate, row.candidate_id).merged_into_id is None


def test_persistence_constraint_failure_rolls_back_and_does_not_leak_output(
    client, account, db_session, runtime, monkeypatch, caplog
):
    caplog.set_level(logging.INFO)
    sign_in(client)

    class OversizedFake(FakeLLM):
        def complete_json(self, **kwargs):
            output = super().complete_json(**kwargs)
            if hasattr(output, "full_name"):
                return output.model_copy(update={"full_name": "synthetic-private-name" * 20})
            return output

    monkeypatch.setattr(tasks, "get_llm_client", lambda settings: OversizedFake())
    row = get_row(db_session, upload(client, ("oversized.docx", cv_docx("Kỹ năng: Python")))[0])
    assert row.status == ProcessingStatus.failed and row.candidate_id is None
    assert count_candidates(db_session) == 0
    assert "synthetic-private-name" not in row.error + caplog.text


@pytest.mark.parametrize(
    "failure", [ExtractionError("OCR_NOT_INSTALLED", "Máy chủ chưa cài OCR"), LLMValidationError()]
)
def test_known_ocr_and_invalid_llm_failures_are_saved(
    client, account, db_session, runtime, monkeypatch, failure
):
    sign_in(client)

    def fail(*args, **kwargs):
        raise failure

    stage = "extract_text" if isinstance(failure, ExtractionError) else "parse_cv"
    monkeypatch.setattr(tasks, stage, fail)
    row = get_row(db_session, upload(client, ("failure.docx", cv_docx("Kỹ năng: Python")))[0])
    assert row.status == ProcessingStatus.failed and row.candidate_id is None
    if isinstance(failure, ExtractionError):
        assert row.error == "Máy chủ chưa cài OCR"
    else:
        assert row.error == "Không thể phân tích CV. Vui lòng thử lại."


def test_uploader_keeps_access_after_parse_without_access_to_other_candidates_files(
    client, account, db_session, runtime
):
    account.role = UserRole.recruiter
    other = User(
        email="other-uploader@example.invalid",
        full_name="Người tải giả",
        role=UserRole.recruiter,
        password_hash=account.password_hash,
    )
    db_session.add(other)
    db_session.commit()
    sign_in(client)
    row = get_row(
        db_session,
        upload(
            client,
            (
                "mine.docx",
                cv_docx("Họ tên: Nhân vật giả\nEmail: shared@example.invalid\nKỹ năng: Python"),
            ),
        )[0],
    )
    assert row.status == ProcessingStatus.done and row.candidate_id
    assert client.get(f"/api/v1/cv-files/{row.id}/download").status_code == 200
    sign_in(client, other.email)
    assert client.get(f"/api/v1/cv-files/{row.id}").status_code == 403
    second = get_row(
        db_session,
        upload(
            client,
            (
                "theirs.docx",
                cv_docx("Họ tên: Nhân vật giả\nEmail: shared@example.invalid\nKỹ năng: JS"),
            ),
        )[0],
    )
    assert second.candidate_id == row.candidate_id
    sign_in(client)
    assert client.get(f"/api/v1/cv-files/{second.id}/download").status_code == 403
    assert client.get(f"/api/v1/cv-files/{row.id}").status_code == 200


def test_conflicting_contacts_fail_without_reassigning_or_merging_candidates(
    client, account, db_session, runtime
):
    sign_in(client)
    first = Candidate(
        full_name="Nhân vật giả A",
        email="conflict@example.invalid",
        retention_until=datetime.now().date(),
    )
    second = Candidate(
        full_name="Nhân vật giả B", phone="+84900000123", retention_until=datetime.now().date()
    )
    db_session.add_all([first, second])
    db_session.commit()
    row = get_row(
        db_session,
        upload(
            client,
            (
                "conflict.docx",
                cv_docx(
                    "Họ tên: Nhân vật giả C\nEmail: conflict@example.invalid\n"
                    "Điện thoại: 0900 000 123"
                ),
            ),
        )[0],
    )
    assert row.status == ProcessingStatus.failed and row.candidate_id is None
    assert row.error == "Email và số điện thoại khớp nhiều ứng viên. Cần kiểm tra thủ công."
    assert first.full_name == "Nhân vật giả A" and second.full_name == "Nhân vật giả B"
    assert first.merged_into_id is second.merged_into_id is None
    assert count_candidates(db_session) == 2
