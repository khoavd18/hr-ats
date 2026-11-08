import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

import pymupdf
import pytest
from docx import Document
from eval.generate_synthetic_cvs import (
    COMPANIES,
    DEFAULT_SEED,
    LAYOUTS,
    PROFILES,
    generate_dataset,
    main,
)
from eval.schemas import CVLabel, JobDataset
from PIL import Image
from pydantic import ValidationError

from app.core.config import REPO_ROOT

SAMPLES = REPO_ROOT / "data/sample_cvs"


def labels_in(directory: Path) -> list[CVLabel]:
    return [
        CVLabel.model_validate_json(path.read_bytes())
        for path in sorted(directory.glob("cv_*.json"))
    ]


def hashes(directory: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in directory.iterdir()
        if path.is_file() and path.name != ".gitkeep"
    }


def document_text(path: Path) -> str:
    if path.suffix == ".pdf":
        with pymupdf.open(path) as doc:
            return "\n".join(page.get_text() for page in doc)
    doc = Document(path)
    pieces = [p.text for p in doc.paragraphs]
    pieces.extend(cell.text for table in doc.tables for row in table.rows for cell in row.cells)
    pieces.extend(p.text for section in doc.sections for p in section.footer.paragraphs)
    return "\n".join(pieces)


def normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def test_committed_cvs_have_valid_matching_labels_and_complete_job_matrix() -> None:
    labels = labels_in(SAMPLES)
    jobs = JobDataset.model_validate_json((SAMPLES / "jobs.json").read_bytes())
    assert len(labels) == 60
    assert jobs.seed == DEFAULT_SEED
    files = {p.name for p in SAMPLES.iterdir() if p.suffix in {".pdf", ".docx"}}
    assert files == {label.file_name for label in labels}
    assert {label.id for label in labels} == set(jobs.expected_level)
    assert len(jobs.jobs) == 5
    for label in labels:
        assert label.expected_level == jobs.expected_level[label.id]
        assert set(label.expected_level) == {job.id for job in jobs.jobs}
    assert sum(p.stat().st_size for p in SAMPLES.iterdir()) < 30_000_000


def test_every_layout_career_language_and_identity_bucket_is_present() -> None:
    labels = labels_in(SAMPLES)
    assert Counter(label.layout for label in labels) == dict.fromkeys(LAYOUTS, 10)
    assert set(label.career for label in labels) == set(PROFILES)
    assert {label.language for label in labels} == {"vi", "en"}
    assert {(label.region, label.gender) for label in labels} == {
        (region, gender) for region in ("north", "central", "south") for gender in ("Nam", "Nữ")
    }
    for career in PROFILES:
        assert len({label.full_name for label in labels if label.career == career}) > 1
    for layout in set(LAYOUTS) - {"scan"}:
        assert {Path(label.file_name).suffix for label in labels if label.layout == layout} == {
            ".pdf",
            ".docx",
        }


def test_contacts_and_employment_histories_are_consistent_and_fabricated() -> None:
    labels = labels_in(SAMPLES)
    assert len({label.email for label in labels}) == len(labels)
    assert len({label.phone for label in labels}) == len(labels)
    for label in labels:
        assert label.synthetic is True
        assert label.email.endswith("@example.com")
        assert re.fullmatch(r"09\d{2} 000 \d{3}", label.phone)
        total_months = 0
        for item in label.experience:
            assert item.company in COMPANIES
            assert item.company.startswith("Công ty Giả lập ")
            start_year, start_month = map(int, item.start.split("-"))
            end_year, end_month = map(int, item.end.split("-"))
            months = (end_year - start_year) * 12 + end_month - start_month
            assert months > 0
            total_months += months
        assert total_months == label.years_experience * 12
        assert all("Đại học Mô phỏng" in item.school for item in label.education)


def test_expected_levels_follow_documented_fixture_scenarios() -> None:
    labels = labels_in(SAMPLES)
    jobs = JobDataset.model_validate_json((SAMPLES / "jobs.json").read_bytes())
    for job in jobs.jobs:
        assert {label.expected_level[job.id] for label in labels} == {"low", "medium", "high"}
        for label in labels:
            if job.id != f"job_{label.career}":
                assert label.expected_level[job.id] == "low"
            elif label.expected_level[job.id] == "high":
                assert label.years_experience >= 3
                assert set(job.must_have[:2] + job.nice_to_have) <= set(label.skills)
            elif label.expected_level[job.id] == "medium":
                assert label.years_experience == 2
                assert set(job.must_have[:2]) <= set(label.skills)
                assert set(job.nice_to_have).isdisjoint(label.skills)
            else:
                assert label.years_experience == 1
                assert not set(job.must_have[:2]) <= set(label.skills)


def test_digital_documents_really_contain_the_labeled_content_and_structures() -> None:
    for label in labels_in(SAMPLES):
        path = SAMPLES / label.file_name
        if label.layout == "scan":
            continue
        text = normalized(document_text(path))
        expected = [
            label.full_name,
            label.email,
            label.phone,
            label.location,
            label.date_of_birth,
            label.current_title,
            *label.skills,
        ]
        for item in label.experience:
            expected.extend((item.company, item.title, item.start, item.end, item.description))
        for item in label.education:
            expected.extend((item.school, item.degree, item.major, item.start, item.end))
        for value in expected:
            assert normalized(value) in text, f"Missing labeled field in {label.id}"
        if label.language == "en":
            for heading in ("Contact", "Profile", "Skills", "Experience", "Education"):
                assert heading in text
            assert f"{label.years_experience} years of experience" in text
        else:
            assert f"{label.years_experience} năm kinh nghiệm" in text
        if path.suffix == ".docx":
            doc = Document(path)
            if label.layout in {"two_column", "table"}:
                assert len(doc.tables) == 1 and len(doc.tables[0].columns) == 2
            if label.layout == "table":
                assert len(doc.tables[0].rows) == 5
            if label.layout == "avatar":
                assert len(doc.inline_shapes) == 1
            with ZipFile(path) as archive:
                assert {entry.date_time for entry in archive.infolist()} == {(2000, 1, 1, 0, 0, 0)}
        else:
            with pymupdf.open(path) as doc:
                page = doc[0]
                if label.layout == "two_column":
                    assert page.search_for(label.email)[0].x1 < 238
                    assert page.search_for(label.experience[0].description)[0].x0 >= 238
                if label.layout == "table":
                    assert len(page.get_drawings()) >= 10
                if label.layout == "avatar":
                    assert any(drawing["fill"] is not None for drawing in page.get_drawings())


def test_scans_are_image_only_and_have_visible_document_ink() -> None:
    for label in labels_in(SAMPLES):
        if label.layout != "scan":
            continue
        with pymupdf.open(SAMPLES / label.file_name) as doc:
            assert len(doc) == 1 and not doc[0].get_text().strip()
            assert len(doc[0].get_images()) == 1
            pix = doc[0].get_pixmap(colorspace=pymupdf.csGRAY)
            image = Image.frombytes("L", (pix.width, pix.height), pix.samples)
            histogram = image.histogram()
            # Distinguishes an actual document image from a blank scan fixture.
            assert sum(histogram[:128]) > image.width * image.height * 0.01


def test_same_seed_reproduces_every_committed_byte(tmp_path: Path) -> None:
    generate_dataset(count=60, seed=DEFAULT_SEED, out=tmp_path)
    assert hashes(tmp_path) == hashes(SAMPLES)


def test_arbitrary_seed_is_repeatable_including_docx_and_scan(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    generate_dataset(count=12, seed=17, out=first)
    generate_dataset(count=12, seed=17, out=second)
    assert hashes(first) == hashes(second)
    generate_dataset(count=12, seed=18, out=second)
    assert hashes(first) != hashes(second)
    assert (first / "cv_0006.pdf").read_bytes() != (second / "cv_0006.pdf").read_bytes()
    assert labels_in(first) != labels_in(second)


@pytest.mark.parametrize("count", [0, -1, 10001])
def test_invalid_count_leaves_output_untouched(tmp_path: Path, count: int) -> None:
    with pytest.raises(ValueError, match="count"):
        generate_dataset(count=count, seed=1, out=tmp_path)
    assert not list(tmp_path.iterdir())


def test_generator_does_not_delete_or_overwrite_unrelated_output(tmp_path: Path) -> None:
    document = tmp_path / "cv_0001.pdf"
    document.write_bytes(b"unrelated synthetic marker")
    before = hashes(tmp_path)
    with pytest.raises(ValueError, match="empty output"):
        generate_dataset(count=1, seed=1, out=tmp_path)
    assert hashes(tmp_path) == before


def test_cli_honors_arguments_without_logging_fixture_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate_synthetic_cvs.py", "--count", "1", "--seed", "23", "--out", str(tmp_path)],
    )
    main()
    assert len(labels_in(tmp_path)) == 1
    assert JobDataset.model_validate_json((tmp_path / "jobs.json").read_bytes()).seed == 23
    assert capsys.readouterr().out == "Generated 1 synthetic CVs and labels (seed=23).\n"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("email", "fixture@example.invalid"),
        ("phone", "not-a-phone"),
        ("file_name", "../cv_0001.pdf"),
        ("file_name", "cv_9999.pdf"),
        ("years_experience", -1),
        ("expected_level", {"job_backend": "invalid"}),
        ("synthetic", False),
        ("unknown_field", "synthetic marker"),
    ],
)
def test_cv_label_schema_rejects_invalid_data(field: str, value: object) -> None:
    data = json.loads((SAMPLES / "cv_0001.json").read_bytes())
    data[field] = value
    with pytest.raises(ValidationError):
        CVLabel.model_validate(data)


def test_cli_schema_error_does_not_echo_contact_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    generate_dataset(count=1, seed=23, out=tmp_path)
    path = tmp_path / "cv_0001.json"
    data = json.loads(path.read_bytes())
    marker = "synthetic-private-marker@example.com"
    data["email"] = marker
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv", ["generate_synthetic_cvs.py", "--count", "1", "--out", str(tmp_path)]
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    output = capsys.readouterr()
    assert marker not in output.err + output.out


def test_job_schema_rejects_incomplete_or_duplicate_job_matrix() -> None:
    data = json.loads((SAMPLES / "jobs.json").read_bytes())
    del data["expected_level"]["cv_0001"]["job_backend"]
    with pytest.raises(ValidationError):
        JobDataset.model_validate(data)
    data = json.loads((SAMPLES / "jobs.json").read_bytes())
    data["jobs"][1]["id"] = data["jobs"][0]["id"]
    with pytest.raises(ValidationError):
        JobDataset.model_validate(data)
