"""All identities are synthetic labels from the committed T06 dataset."""

import json
import re
import unicodedata

import pytest

from app.ai.anonymize import anonymize
from app.ai.extract import extract_text
from app.core.config import REPO_ROOT
from app.services.dedupe import normalize_name

SAMPLES = REPO_ROOT / "data/sample_cvs"
LABELS = [
    json.loads(path.read_text(encoding="utf-8")) for path in sorted(SAMPLES.glob("cv_*.json"))
]
DIGITAL = [label for label in LABELS if label["layout"] != "scan"]


@pytest.mark.parametrize("label", DIGITAL, ids=lambda label: label["id"])
def test_anonymize_fifty_extracted_cvs_and_name_variants(label):
    mime = (
        "application/pdf"
        if label["file_name"].endswith(".pdf")
        else ("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    )
    source = extract_text((SAMPLES / label["file_name"]).read_bytes(), mime).text
    name = label["full_name"]
    no_accents = normalize_name(name)
    source += f"\n{name.upper()}\n{no_accents}\n{no_accents.upper()}"
    source += "\nTình trạng hôn nhân: Độc thân\nhttps://linkedin.com/in/synthetic-person"
    source += "\n![Ảnh](https://example.invalid/avatar.png)"
    cleaned = anonymize(unicodedata.normalize("NFD", source), name)
    assert name not in cleaned and no_accents not in normalize_name(cleaned)
    assert "[TÊN]" in cleaned
    assert label["email"] not in cleaned and label["phone"] not in cleaned
    assert label["date_of_birth"] not in cleaned and label["location"] not in cleaned
    assert not re.search(r"(?im)^\s*(?:nam|nữ|male|female|gender|giới tính)\b", cleaned)
    assert "Độc thân" not in cleaned and "synthetic-person" not in cleaned
    assert "avatar.png" not in cleaned
    assert all(skill.casefold() in cleaned.casefold() for skill in label["skills"])
    assert all(item["company"] in cleaned for item in label["experience"])
    assert all(item["start"] in cleaned for item in label["experience"])
    assert anonymize(cleaned, name) == cleaned


@pytest.mark.parametrize(
    "metadata",
    [
        "Ngay sinh: 2001-01-02",
        "Ngày sinh\n2001-01-02",
        "Tuổi: 25",
        "25 tuổi",
        "Năm sinh: 2001",
        "DOB: 2001-01-02",
        "Date of birth\n2001-01-02",
        "Gender: Female",
        "Giới tính\nNữ",
        "Nam",
        "Nữ",
        "Female",
        "Male",
        "Tôi là nữ",
        "I am male",
        "Marital status: single",
        "Hôn nhân: Đã kết hôn",
        "Dia chi: Số 99 đường giả",
        "Home address\n99 Synthetic Street",
        "Kỹ năng: SQL | Giới tính: Nam | Tuổi: 25",
    ],
)
def test_private_metadata_lines_are_removed_including_separate_values(metadata):
    assert anonymize(f"{metadata}\nKinh nghiệm: Python 2020-01 - 2026-01", None) == (
        "Kinh nghiệm: Python 2020-01 - 2026-01"
    )


def test_names_have_word_boundaries_and_professional_gender_substrings_are_kept():
    source = (
        "Họ tên: Nhân Vật Giả\nNHAN VAT GIA; nhân   vật giả; prefixnhan vat gia\n"
        "Phát triển phần mềm tại Việt Nam; quản lý nhân sự\n"
        "Đại học Mô phỏng Miền Nam\nKinh nghiệm: 5 năm; Python 3.12\n"
        "https://docs.python.org/3/; github.com/synthetic-cv"
    )
    cleaned = anonymize(source, "Nhân Vật Giả")
    assert cleaned.count("[TÊN]") == 3
    assert "prefixnhan vat gia" in cleaned and "Việt Nam" in cleaned
    assert "Miền Nam" in cleaned and "5 năm" in cleaned and "Python 3.12" in cleaned
    assert "https://docs.python.org/3/" in cleaned and "synthetic-cv" not in cleaned


def test_null_name_masks_labeled_or_unlabeled_header_without_storing_an_identity():
    assert anonymize("Họ tên: Nhân Vật Giả\nKỹ năng: SQL", None) == "Họ tên: [TÊN]\nKỹ năng: SQL"
    assert anonymize("Nhân Vật Giả\nKỹ năng: SQL", "Chưa xác định") == "[TÊN]\nKỹ năng: SQL"
    assert anonymize("", None) == ""
    assert anonymize("Tên Sửa Giả\nKỹ năng: SQL", "Tên Cũ Giả") == "[TÊN]\nKỹ năng: SQL"
