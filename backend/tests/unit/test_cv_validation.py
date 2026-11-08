from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.core.errors import AppError
from app.services.cv_validation import DOCX_MIME, MAX_FILE_BYTES, validate_file
from tests.cv_helpers import PDF, docx_bytes, image_bytes


@pytest.mark.parametrize(
    ("data", "filename", "mime"),
    [
        (PDF, "synthetic.pdf", "application/pdf"),
        (image_bytes(), "synthetic.png", "image/png"),
        (image_bytes("JPEG"), "synthetic.jpg", "image/jpeg"),
        (docx_bytes(), "synthetic.docx", DOCX_MIME),
        (PDF, "synthetic.bin", "application/pdf"),
    ],
)
def test_detects_content_instead_of_filename_or_declared_mime(data, filename, mime):
    detected, digest = validate_file(data, filename)
    assert detected == mime and len(digest) == 64
    assert validate_file(data, filename)[1] == digest


@pytest.mark.parametrize(
    "data", [b"MZ synthetic executable", b"", b"PK\x03\x04invalid zip", b"<html>synthetic</html>"]
)
def test_rejects_disguised_executable_empty_or_unsupported_file(data):
    with pytest.raises(AppError) as caught:
        validate_file(data, "renamed.pdf")
    assert caught.value.code == "INVALID_FILE_TYPE"
    assert "PDF" in caught.value.message and "MZ" not in caught.value.message


def test_size_boundary():
    assert validate_file(PDF + b" " * (MAX_FILE_BYTES - len(PDF)), "synthetic.pdf")
    with pytest.raises(AppError) as caught:
        validate_file(PDF + b" " * MAX_FILE_BYTES, "synthetic.pdf")
    assert caught.value.code == "FILE_TOO_LARGE"


@pytest.mark.parametrize("filename", ["synthetic.docm", "synthetic.DOCM"])
def test_rejects_docm_even_with_accepted_magic(filename):
    with pytest.raises(AppError) as caught:
        validate_file(PDF, filename)
    assert caught.value.code == "MACRO_NOT_ALLOWED"


@pytest.mark.parametrize("kind", ["vba", "content_type", "not_docx", "traversal", "expanded_size"])
def test_rejects_macro_disguised_as_docx_and_unsafe_archives(kind):
    output = BytesIO()
    with ZipFile(BytesIO(docx_bytes())) as source, ZipFile(output, "w", ZIP_DEFLATED) as target:
        for entry in source.infolist():
            data = source.read(entry.filename)
            if kind == "content_type" and entry.filename == "[Content_Types].xml":
                data = data.replace(b"wordprocessingml.document.main+xml", b"macroEnabled.main+xml")
            if kind != "not_docx" or entry.filename != "word/document.xml":
                target.writestr(entry.filename, data)
        if kind == "vba":
            target.writestr("word/vbaProject.bin", b"synthetic macro marker")
        if kind == "traversal":
            target.writestr("../outside", b"synthetic")
        if kind == "expanded_size":
            target.writestr("word/large.bin", b" " * (50 * 1024 * 1024))
    with pytest.raises(AppError):
        validate_file(output.getvalue(), "renamed.docx")
