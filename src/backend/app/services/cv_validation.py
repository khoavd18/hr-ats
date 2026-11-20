import hashlib
import zlib
from io import BytesIO
from pathlib import PurePosixPath
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from app.core.errors import AppError

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_FILES = 50
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _invalid() -> AppError:
    return AppError("INVALID_FILE_TYPE", "Chỉ chấp nhận tệp PDF, DOCX, JPG hoặc PNG hợp lệ.", 422)


def _validate_docx(data: bytes) -> None:
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 2000 or sum(entry.file_size for entry in entries) > 50 * 1024 * 1024:
                raise _invalid()
            names = [entry.filename.casefold() for entry in entries]
            if len(names) != len(set(names)) or not {
                "[content_types].xml",
                "word/document.xml",
            }.issubset(names):
                raise _invalid()
            for entry, name in zip(entries, names, strict=True):
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts or "\\" in name or entry.flag_bits & 1:
                    raise _invalid()
                if "vba" in name or name.endswith(".docm"):
                    raise AppError("MACRO_NOT_ALLOWED", "Không chấp nhận tệp có macro.", 422)
            content_types = archive.read("[Content_Types].xml")
            # Also recognize ASCII markup in UTF-16/32 XML before parsing entities.
            lower = content_types.lower().replace(b"\x00", b"")
            if b"macroenabled" in lower or b"vbaproject" in lower:
                raise AppError("MACRO_NOT_ALLOWED", "Không chấp nhận tệp có macro.", 422)
            if b"<!doctype" in lower or b"<!entity" in lower:
                raise _invalid()
            root = ElementTree.fromstring(content_types)
            expected = (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
            )
            if not any(
                node.attrib.get("PartName") == "/word/document.xml"
                and node.attrib.get("ContentType") == expected
                for node in root
            ):
                raise _invalid()
            if archive.testzip() is not None:
                raise _invalid()
    except (
        BadZipFile,
        KeyError,
        ValueError,
        RuntimeError,
        NotImplementedError,
        OSError,
        ElementTree.ParseError,
        EOFError,
        zlib.error,
    ):
        raise _invalid() from None


def validate_file(data: bytes, filename: str) -> tuple[str, str]:
    if len(data) > MAX_FILE_BYTES:
        raise AppError("FILE_TOO_LARGE", "Mỗi tệp được phép tối đa 10 MB.", 422)
    if PurePosixPath(filename.replace("\\", "/")).suffix.casefold() == ".docm":
        raise AppError("MACRO_NOT_ALLOWED", "Không chấp nhận tệp có macro.", 422)
    if data.startswith(b"%PDF-"):
        mime = "application/pdf"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif data.startswith(b"PK\x03\x04"):
        _validate_docx(data)
        mime = DOCX_MIME
    else:
        raise _invalid()
    return mime, hashlib.sha256(data).hexdigest()
