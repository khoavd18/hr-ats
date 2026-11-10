"""Production log formatter around upload → extraction → parse → embed → score."""

import json
import logging
from contextlib import contextmanager
from io import StringIO
from uuid import UUID

from app.ai.embed import FakeEmbedder
from app.ai.llm import FakeLLM
from app.api.cv_files import storage_dependency
from app.core.logging import JsonFormatter, PiiFilter
from app.models import Application, Candidate, CvFile
from app.models.enums import ProcessingStatus
from app.services import embeddings
from app.storage import LocalStorage
from app.workers import tasks
from tests.api.test_cv_pipeline import DIGITAL, SAMPLES
from tests.api.test_pipeline import seed_records
from tests.auth_helpers import csrf_headers, sign_in


def test_full_pipeline_logs_exclude_all_synthetic_identities(
    app,
    client,
    account,
    db_session,
    tmp_path,
    monkeypatch,
):
    records = seed_records(db_session, account)
    records.job.must_have = ["Python"]
    db_session.commit()
    storage = LocalStorage(tmp_path / "logs-pipeline")
    app.dependency_overrides[storage_dependency] = lambda: storage

    @contextmanager
    def session():
        yield db_session

    monkeypatch.setattr(tasks, "worker_session", session)
    monkeypatch.setattr(tasks, "build_storage", lambda settings: storage)
    prompts, embedded = [], []

    class RecordingLLM(FakeLLM):
        def complete_json(self, **kwargs):
            prompts.append((kwargs["schema"].__name__, kwargs["user"]))
            return super().complete_json(**kwargs)

    class RecordingEmbedder(FakeEmbedder):
        def embed(self, texts):
            embedded.extend(texts)
            return super().embed(texts)

    monkeypatch.setattr(tasks, "get_llm_client", lambda settings: RecordingLLM())
    monkeypatch.setattr(
        embeddings, "get_embedder", lambda settings: RecordingEmbedder(settings.embedding_dim)
    )
    output = StringIO()
    handler = logging.StreamHandler(output)
    handler.addFilter(PiiFilter())
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.addHandler(handler)
    label = DIGITAL[0]
    try:
        assert sign_in(client).status_code == 200
        response = client.post(
            "/api/v1/cv-files",
            data={"job_id": str(records.job.id)},
            files=[
                (
                    "files",
                    (label["full_name"] + ".docx", (SAMPLES / label["file_name"]).read_bytes()),
                )
            ],
            headers=csrf_headers(client),
        )
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["error"] is None
        file = db_session.get_one(CvFile, UUID(item["cv_file"]["id"]))
        assert file.status == ProcessingStatus.done
        candidate = db_session.get_one(Candidate, file.candidate_id)
        assert (
            candidate.email == label["email"]
            and candidate.anonymized_text
            and len(candidate.embedding) > 0
        )
        application = db_session.query(Application).filter_by(candidate_id=candidate.id).one()
        assert application.ai_status == ProcessingStatus.done and application.ai_score is not None
        assert client.get(f"/api/v1/applications/{application.id}").status_code == 200
        assert client.get(f"/api/v1/cv-files/{file.id}/download").status_code == 200
    finally:
        root.removeHandler(handler)
        handler.close()
    serialized = output.getvalue()
    logs = [json.loads(line) for line in serialized.splitlines()]
    assert any(row["logger"] == "app.http" for row in logs)
    assert any(row["logger"] == "app.ai.llm" for row in logs)
    for pii in (
        label["email"],
        label["full_name"],
        label["phone"],
        candidate.phone,
        account.email,
        account.full_name,
    ):
        assert pii and pii not in serialized
    assert embedded and prompts
    scoring_prompts = [text for schema, text in prompts if schema == "ScoreOutput"]
    assert scoring_prompts
    for text in scoring_prompts:
        assert all(pii not in text for pii in (label["email"], label["full_name"], label["phone"]))
    for text in embedded:
        assert all(pii not in text for pii in (label["email"], label["full_name"], label["phone"]))
