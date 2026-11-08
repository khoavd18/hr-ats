"""Only generated or committed synthetic CVs; OCR is entirely local."""

import shutil
import subprocess
import unicodedata
from io import BytesIO
from math import ceil

import pymupdf
import pytest
from docx import Document
from eval.schemas import CVLabel
from PIL import Image

from app.ai import extract
from app.ai.extract import ExtractionError, extract_text
from app.ai.redact import redact_contacts
from app.core.config import REPO_ROOT, Settings
from app.models.enums import ExtractionMethod
from app.services.cv_validation import DOCX_MIME

SAMPLES = REPO_ROOT / "data/sample_cvs"
LABELS = [
    CVLabel.model_validate_json(path.read_bytes()) for path in sorted(SAMPLES.glob("cv_*.json"))
]
DIGITAL = [label for label in LABELS if label.layout != "scan"]
SCANS = [label for label in LABELS if label.layout == "scan"]


def pdf_bytes(*pages: str) -> bytes:
    with pymupdf.open() as doc:
        for text in pages:
            page = doc.new_page()
            if text:
                page.insert_text((30, 40), text)
        return doc.tobytes()


def image_bytes(fmt: str = "PNG") -> bytes:
    output = BytesIO()
    Image.new("RGB", (120, 80), "white").save(output, format=fmt)
    return output.getvalue()


@pytest.fixture
def ocr_environment(monkeypatch: pytest.MonkeyPatch) -> list[bytes]:
    monkeypatch.setattr(extract, "get_settings", lambda: Settings(ocr_enabled=True))
    monkeypatch.setattr(extract.shutil, "which", lambda _: "synthetic-tesseract")
    inputs = []

    def run(command, **kwargs):
        assert command == [
            "synthetic-tesseract",
            "stdin",
            "stdout",
            "-l",
            "vie+eng",
            "--dpi",
            "300",
        ]
        assert kwargs["capture_output"] is True
        assert kwargs["timeout"] == 60
        assert kwargs.get("shell", False) is False
        inputs.append(kwargs["input"])
        return subprocess.CompletedProcess(command, 0, stdout=b"Synthetic OCR text", stderr=b"")

    monkeypatch.setattr(extract.subprocess, "run", run)
    return inputs


@pytest.mark.parametrize("label", DIGITAL, ids=lambda label: label.id)
def test_extract_committed_digital_cvs_against_labels(label: CVLabel) -> None:
    path = SAMPLES / label.file_name
    mime = "application/pdf" if path.suffix == ".pdf" else DOCX_MIME
    result = extract_text(path.read_bytes(), mime)
    assert result.method == ("pdf_text" if path.suffix == ".pdf" else "docx")
    assert result.page_count == (1 if path.suffix == ".pdf" else None)
    assert unicodedata.is_normalized("NFC", result.text)
    for value in [label.full_name, label.email, label.phone, *label.skills]:
        assert value in result.text, f"Missing labeled field in {label.id}"
    redacted, emails, phones = redact_contacts(result.text)
    assert label.email not in redacted and label.phone not in redacted
    assert emails == [label.email]
    assert phones == ["+84" + label.phone.replace(" ", "")[1:]]
    if label.layout == "two_column":
        # The labeled left column is contacts + skills; the right is profile +
        # experience + education. Insertion order or y-first sorting interleaves them.
        positions = [
            result.text.index(label.email),
            result.text.index(label.skills[0]),
            result.text.index(f"{label.years_experience} năm kinh nghiệm"),
            result.text.index(label.experience[0].company),
            result.text.index(label.education[0].school),
        ]
        assert positions == sorted(positions), f"Mixed columns in {label.id}"


def test_pdf_columns_with_spanning_header_footer_and_shuffled_insertion() -> None:
    with pymupdf.open() as doc:
        page = doc.new_page(width=600, height=800)
        # Long header/footer cross the gutter. Insert right-side content first.
        for xy, text in [
            ((270, 200), "Right experience"),
            ((40, 300), "Left skills"),
            ((40, 40), "SYNTHETIC FULL WIDTH HEADING FOR A TWO COLUMN DOCUMENT"),
            ((270, 100), "Right profile"),
            ((40, 100), "Left contact"),
            ((270, 400), "Right education"),
            ((40, 750), "SYNTHETIC FULL WIDTH FOOTER AT THE END OF THE DOCUMENT"),
        ]:
            page.insert_text(xy, text, fontsize=10)
        result = extract_text(doc.tobytes(), "application/pdf")
    expected = [
        "SYNTHETIC FULL WIDTH HEADING",
        "Left contact",
        "Left skills",
        "Right profile",
        "Right experience",
        "Right education",
        "SYNTHETIC FULL WIDTH FOOTER",
    ]
    positions = [result.text.index(text) for text in expected]
    assert positions == sorted(positions)


def test_docx_nested_tables_merges_headers_order_and_nfc() -> None:
    doc = Document()
    doc.sections[0].header.paragraphs[0].text = "Synthetic header"
    doc.add_paragraph("Before table")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Kỹ năng"
    nested = table.cell(0, 1).add_table(rows=1, cols=1)
    nested.cell(0, 0).text = "python  \t SQL"
    table.cell(1, 0).merge(table.cell(1, 1)).text = "Merged skill"
    doc.add_paragraph(unicodedata.normalize("NFD", "Tiếng Việt"))
    doc.sections[0].footer.paragraphs[0].text = "Synthetic footer"
    buffer = BytesIO()
    doc.save(buffer)
    result = extract_text(buffer.getvalue(), DOCX_MIME)
    assert "python SQL" in result.text
    assert "Tiếng Việt" in result.text
    assert result.text.count("Merged skill") == 1
    sections = [
        "Synthetic header",
        "Before table",
        "Kỹ năng",
        "python SQL",
        "Tiếng Việt",
        "Synthetic footer",
    ]
    assert [result.text.index(value) for value in sections] == sorted(
        result.text.index(value) for value in sections
    )


@pytest.mark.parametrize("length,expected_calls", [(49, 1), (50, 0)])
def test_ocr_threshold_and_300_dpi_render(
    length: int, expected_calls: int, ocr_environment: list[bytes]
) -> None:
    data = pdf_bytes("x" * length)
    result = extract_text(data, "application/pdf")
    assert len(ocr_environment) == expected_calls
    assert result.method == ("ocr" if expected_calls else "pdf_text")
    if expected_calls:
        with Image.open(BytesIO(ocr_environment[0])) as image:
            assert image.width == ceil(595 * 300 / 72)
            assert image.height == ceil(842 * 300 / 72)


def test_mixed_pdf_marks_entire_result_as_ocr_and_preserves_page_order(
    ocr_environment: list[bytes],
) -> None:
    digital = "Synthetic digital paragraph with more than fifty visible characters."
    result = extract_text(pdf_bytes(digital, "", digital), "application/pdf")
    assert result.page_count == 3
    assert result.method == "ocr"
    assert result.text == f"{digital}\n\nSynthetic OCR text\n\n{digital}"
    assert len(ocr_environment) == 1


@pytest.mark.parametrize("fmt,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg")])
def test_images_use_local_ocr(fmt: str, mime: str, ocr_environment: list[bytes]) -> None:
    result = extract_text(image_bytes(fmt), mime)
    assert result.method == "ocr" and result.page_count == 1
    assert result.text == "Synthetic OCR text"
    assert len(ocr_environment) == 1


def test_disabled_ocr_is_a_safe_per_file_error_and_digital_pdf_still_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(extract, "get_settings", lambda: Settings(ocr_enabled=False))
    for data, mime in [(pdf_bytes(""), "application/pdf"), (image_bytes(), "image/png")]:
        with pytest.raises(ExtractionError, match="Máy chủ chưa bật OCR") as error:
            extract_text(data, mime)
        assert error.value.code == "OCR_DISABLED"
    assert extract_text(pdf_bytes("Synthetic digital content " * 4), "application/pdf").method == (
        "pdf_text"
    )


def test_missing_tesseract_has_required_error_without_breaking_next_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(extract.shutil, "which", lambda _: None)
    with pytest.raises(ExtractionError, match="^Máy chủ chưa cài OCR$") as error:
        extract_text(pdf_bytes(""), "application/pdf")
    assert error.value.code == "OCR_NOT_INSTALLED"
    assert extract_text(pdf_bytes("Synthetic digital content " * 4), "application/pdf").text


@pytest.mark.parametrize("failure", ["missing", "timeout", "oserror", "exit", "empty"])
def test_ocr_errors_never_echo_document_or_stderr(
    failure: str,
    ocr_environment: list[bytes],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    private = b"synthetic-private@example.com"

    def run(command, **kwargs):
        if failure == "missing":
            raise FileNotFoundError(private)
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 60, output=private, stderr=private)
        if failure == "oserror":
            raise OSError(private)
        return subprocess.CompletedProcess(
            command, 1 if failure == "exit" else 0, stdout=b" \n\t", stderr=private
        )

    monkeypatch.setattr(extract.subprocess, "run", run)
    with pytest.raises(ExtractionError) as error:
        extract_text(image_bytes(), "image/png")
    assert private.decode() not in str(error.value)
    assert error.value.__suppress_context__ or error.value.__context__ is None
    output = capsys.readouterr()
    assert private.decode() not in output.out + output.err + caplog.text


def test_custom_languages_and_normalized_ocr_output(
    ocr_environment: list[bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(extract, "get_settings", lambda: Settings(tesseract_langs="eng"))

    def run(command, **kwargs):
        assert command[4] == "eng"
        text = unicodedata.normalize("NFD", "  Kỹ   năng\r\n\tpython\n\n\nSQL  ")
        return subprocess.CompletedProcess(command, 0, stdout=text.encode(), stderr=b"")

    monkeypatch.setattr(extract.subprocess, "run", run)
    result = extract_text(image_bytes(), "image/png")
    assert result.text == "Kỹ năng\npython\n\nSQL"
    assert "Kỹ" not in repr(result)


def test_invalid_language_configuration_cannot_be_a_path_or_argument(
    ocr_environment: list[bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(extract, "get_settings", lambda: Settings(tesseract_langs="../eng --foo"))
    with pytest.raises(ExtractionError, match="Cấu hình ngôn ngữ OCR không hợp lệ"):
        extract_text(image_bytes(), "image/png")
    assert not ocr_environment


def test_oversized_pdf_render_is_rejected_before_allocating_pixels(
    ocr_environment: list[bytes],
) -> None:
    with pymupdf.open() as doc:
        doc.new_page(width=5000, height=5000)
        data = doc.tobytes()
    with pytest.raises(ExtractionError) as error:
        extract_text(data, "application/pdf")
    assert error.value.code == "OCR_IMAGE_TOO_LARGE"
    assert not ocr_environment


def test_oversized_image_is_rejected_before_ocr(
    ocr_environment: list[bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(extract, "MAX_OCR_PIXELS", 100)
    with pytest.raises(ExtractionError) as error:
        extract_text(image_bytes(), "image/png")
    assert error.value.code == "OCR_IMAGE_TOO_LARGE"
    assert not ocr_environment


def test_transparent_image_and_exif_rotation_are_normalized_before_ocr(
    ocr_environment: list[bytes],
) -> None:
    output = BytesIO()
    image = Image.new("RGBA", (120, 80), (0, 0, 0, 0))
    exif = Image.Exif()
    exif[274] = 6
    image.save(output, format="PNG", exif=exif)
    extract_text(output.getvalue(), "image/png")
    with Image.open(BytesIO(ocr_environment[0])) as processed:
        assert processed.size == (80, 120)
        assert processed.convert("RGB").getpixel((0, 0)) == (255, 255, 255)


def test_pdf_page_limit_is_checked_before_reading_or_ocr(
    ocr_environment: list[bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(extract, "MAX_PDF_PAGES", 1)
    with pytest.raises(ExtractionError):
        extract_text(pdf_bytes("", ""), "application/pdf")
    assert not ocr_environment


@pytest.mark.parametrize("mime", ["application/pdf", DOCX_MIME, "image/png", "image/jpeg"])
def test_corrupt_documents_have_safe_errors(mime: str) -> None:
    with pytest.raises(ExtractionError, match="Không đọc được nội dung CV"):
        extract_text(b"synthetic-private-marker", mime)


def test_parser_failure_is_sanitized_after_successful_magic_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def open_pdf(*args, **kwargs):
        raise RuntimeError("synthetic-private-marker@example.com")

    data = pdf_bytes("Synthetic digital content " * 4)
    monkeypatch.setattr(extract.pymupdf, "open", open_pdf)
    with pytest.raises(ExtractionError, match="^Không đọc được nội dung CV$") as error:
        extract_text(data, "application/pdf")
    assert error.value.__suppress_context__


def test_encrypted_pdf_and_mime_mismatch_are_rejected() -> None:
    with pymupdf.open(stream=pdf_bytes("Synthetic paragraph " * 5), filetype="pdf") as doc:
        data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="synthetic")
    with pytest.raises(ExtractionError):
        extract_text(data, "application/pdf")
    with pytest.raises(ExtractionError) as error:
        extract_text(pdf_bytes("Synthetic paragraph " * 5), "text/plain")
    assert error.value.code == "UNSUPPORTED_CV_TYPE"


def test_empty_docx_has_specified_error() -> None:
    output = BytesIO()
    Document().save(output)
    with pytest.raises(ExtractionError, match="^Không đọc được nội dung CV$"):
        extract_text(output.getvalue(), DOCX_MIME)


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="T08: Tesseract is not installed")
@pytest.mark.parametrize("label", SCANS, ids=lambda label: label.id)
def test_committed_scan_really_extracts_labeled_email_with_tesseract(label: CVLabel) -> None:
    result = extract_text((SAMPLES / label.file_name).read_bytes(), "application/pdf")
    assert result.method == ExtractionMethod.ocr and result.page_count == 1
    assert label.email in result.text, f"OCR missed labeled email in {label.id}"
    redacted, emails, _ = redact_contacts(result.text)
    assert label.email in emails and label.email not in redacted


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="T08: Tesseract is not installed")
@pytest.mark.parametrize("fmt,mime", [("png", "image/png"), ("jpeg", "image/jpeg")])
def test_image_ocr_really_extracts_email_with_tesseract(fmt: str, mime: str) -> None:
    label = SCANS[0]
    with pymupdf.open(SAMPLES / label.file_name) as doc:
        data = doc[0].get_pixmap(dpi=150).tobytes(fmt)
    result = extract_text(data, mime)
    assert result.method == "ocr" and result.page_count == 1
    assert label.email in result.text
