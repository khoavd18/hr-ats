"""Extract CVs locally. Never log document bytes, extracted text or OCR stderr."""

import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from io import BytesIO

import pymupdf
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from PIL import Image, ImageFilter, ImageOps

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.enums import ExtractionMethod
from app.services.cv_validation import DOCX_MIME, validate_file

OCR_DPI = 300
OCR_TIMEOUT_SECONDS = 60
MAX_OCR_PIXELS = 25_000_000
MAX_PDF_PAGES = 100


class ExtractionError(AppError):
    """A safe, catchable per-file failure for the T10 pipeline."""

    def __init__(
        self, code: str = "EXTRACTION_FAILED", message: str = "Không đọc được nội dung CV"
    ):
        super().__init__(code, message, 422)


@dataclass(frozen=True)
class ExtractResult:
    text: str = field(repr=False)
    method: ExtractionMethod
    # DOCX has no reliable pagination without a layout engine.
    page_count: int | None


@dataclass(frozen=True)
class _Block:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str = field(repr=False)


def _reading_order(blocks: list[_Block]) -> list[_Block]:
    """Find a vertical gutter; spanning headings/footers divide horizontal bands.

    A gutter needs text on both sides at the same height. This avoids treating
    indentation in an ordinary paragraph as another column. Otherwise retain
    top-to-bottom order. This is a geometric heuristic, not a layout model.
    """
    candidates = set()
    for left in blocks:
        for right in blocks:
            if left.x1 + 12 <= right.x0 and min(left.y1, right.y1) > max(left.y0, right.y0):
                candidates.add((left.x1 + right.x0) / 2)
    best = None
    best_score = 0
    for gutter in sorted(candidates):
        left_side = [b for b in blocks if b.x1 <= gutter]
        right_side = [b for b in blocks if b.x0 >= gutter]
        spanning = [b for b in blocks if b.x0 < gutter < b.x1]
        # A block crossing the gutter inside the body means this cut is unsafe.
        if any(
            min(span.y1, b.y1) > max(span.y0, b.y0)
            for span in spanning
            for b in left_side + right_side
        ):
            continue
        score = min(len(left_side), len(right_side))
        if score > best_score:
            best = left_side, right_side, spanning
            best_score = score
    if best is None:
        return sorted(blocks, key=lambda b: (b.y0, b.x0))
    left_side, right_side, spanning = best
    ordered = []
    for span in sorted(spanning, key=lambda b: (b.y0, b.x0)):
        for side in (left_side, right_side):
            ordered.extend(_reading_order([b for b in side if b.y1 <= span.y0]))
            side[:] = [b for b in side if b.y1 > span.y0]
        ordered.append(span)
    ordered.extend(_reading_order(left_side))
    ordered.extend(_reading_order(right_side))
    return ordered


def _normalize(text: str) -> str:
    lines = [" ".join(line.split()) for line in unicodedata.normalize("NFC", text).splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _ocr(png: bytes) -> str:
    settings = get_settings()
    if not settings.ocr_enabled:
        raise ExtractionError("OCR_DISABLED", "Máy chủ chưa bật OCR")
    executable = shutil.which("tesseract")
    if executable is None:
        raise ExtractionError("OCR_NOT_INSTALLED", "Máy chủ chưa cài OCR")
    if not re.fullmatch(r"[a-zA-Z0-9_]+(?:\+[a-zA-Z0-9_]+)*", settings.tesseract_langs):
        raise ExtractionError("OCR_FAILED", "Cấu hình ngôn ngữ OCR không hợp lệ")
    # A small median filter removes isolated scanner noise without inventing
    # contact characters or repairing OCR text from fixture-specific patterns.
    with Image.open(BytesIO(png)) as image:
        prepared = image.convert("L").filter(ImageFilter.MedianFilter(3))
        output = BytesIO()
        prepared.save(output, format="PNG", dpi=(OCR_DPI, OCR_DPI))
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW
    try:
        # Pipe both directions: no CV files on disk and no CV text in argv/logs.
        result = subprocess.run(
            [executable, "stdin", "stdout", "-l", settings.tesseract_langs, "--dpi", str(OCR_DPI)],
            input=output.getvalue(),
            capture_output=True,
            timeout=OCR_TIMEOUT_SECONDS,
            check=False,
            creationflags=creationflags,
        )
    except FileNotFoundError:
        raise ExtractionError("OCR_NOT_INSTALLED", "Máy chủ chưa cài OCR") from None
    except subprocess.TimeoutExpired:
        raise ExtractionError("OCR_TIMEOUT", "Đọc CV bằng OCR quá thời gian cho phép") from None
    except OSError:
        raise ExtractionError("OCR_FAILED", "Không thể khởi chạy OCR") from None
    if result.returncode:
        raise ExtractionError(
            "OCR_FAILED", "Không thể đọc CV bằng OCR. Vui lòng kiểm tra OCR và gói ngôn ngữ"
        )
    return result.stdout.decode("utf-8", errors="replace")


def _require_ocr() -> None:
    # Check before rendering/decoding an image when OCR cannot run anyway.
    if not get_settings().ocr_enabled:
        raise ExtractionError("OCR_DISABLED", "Máy chủ chưa bật OCR")
    if shutil.which("tesseract") is None:
        raise ExtractionError("OCR_NOT_INSTALLED", "Máy chủ chưa cài OCR")


def _pdf_blocks(page: pymupdf.Page) -> list[_Block]:
    blocks = []
    flags = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES
    for block in page.get_text("dict", flags=flags)["blocks"]:
        if block["type"] != 0:
            continue
        lines = []
        for line in block["lines"]:
            # MuPDF can join separate columns into a block or even one line.
            # Split a line at a geometric gap between spans before ordering it.
            groups: list[list[dict]] = []
            for span in line["spans"]:
                if not groups or span["bbox"][0] > groups[-1][-1]["bbox"][2] + 12:
                    groups.append([])
                groups[-1].append(span)
            for group in groups:
                text = "".join(span["text"] for span in group)
                if text.strip():
                    lines.append(
                        _Block(
                            min(s["bbox"][0] for s in group),
                            min(s["bbox"][1] for s in group),
                            max(s["bbox"][2] for s in group),
                            max(s["bbox"][3] for s in group),
                            text,
                        )
                    )
        if any(
            left.x1 + 12 <= right.x0 and min(left.y1, right.y1) > max(left.y0, right.y0)
            for left in lines
            for right in lines
        ):
            blocks.extend(lines)
        elif lines:
            x0, y0, x1, y1 = block["bbox"]
            blocks.append(_Block(x0, y0, x1, y1, "\n".join(line.text for line in lines)))
    return blocks


def _extract_pdf(data: bytes) -> ExtractResult:
    pages = []
    method = ExtractionMethod.pdf_text
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        if doc.needs_pass or not 0 < doc.page_count <= MAX_PDF_PAGES:
            raise ExtractionError()
        for page in doc:
            blocks = _pdf_blocks(page)
            text = "\n".join(block.text for block in _reading_order(blocks))
            if len(_normalize(text)) < 50:
                _require_ocr()
                if page.rect.width * page.rect.height * (OCR_DPI / 72) ** 2 > MAX_OCR_PIXELS:
                    raise ExtractionError("OCR_IMAGE_TOO_LARGE", "Trang CV quá lớn để đọc bằng OCR")
                pixmap = page.get_pixmap(dpi=OCR_DPI, colorspace=pymupdf.csRGB, alpha=False)
                text = _ocr(pixmap.tobytes("png"))
                method = ExtractionMethod.ocr
            pages.append(text)
        return ExtractResult("\n\n".join(pages), method, doc.page_count)


def _docx_parts(parent):
    # iter_inner_content preserves paragraph/table position, including nested tables.
    for item in parent.iter_inner_content():
        if isinstance(item, Paragraph):
            yield item.text
        elif isinstance(item, Table):
            seen = set()
            for row in item.rows:
                for cell in row.cells:
                    # Merged cells appear repeatedly in python-docx's row API.
                    if cell._tc not in seen:
                        seen.add(cell._tc)
                        yield from _docx_parts(cell)


def _extract_docx(data: bytes) -> ExtractResult:
    doc = Document(BytesIO(data))
    parts = []
    seen = set()
    for section in doc.sections:
        for header in (section.header, section.first_page_header, section.even_page_header):
            if header._element not in seen:
                seen.add(header._element)
                parts.extend(_docx_parts(header))
    parts.extend(_docx_parts(doc))
    for section in doc.sections:
        for footer in (section.footer, section.first_page_footer, section.even_page_footer):
            if footer._element not in seen:
                seen.add(footer._element)
                parts.extend(_docx_parts(footer))
    return ExtractResult("\n".join(parts), ExtractionMethod.docx, None)


def _extract_image(data: bytes) -> ExtractResult:
    _require_ocr()
    with Image.open(BytesIO(data)) as source:
        if source.width * source.height > MAX_OCR_PIXELS:
            raise ExtractionError("OCR_IMAGE_TOO_LARGE", "Ảnh CV quá lớn để đọc bằng OCR")
        image = ImageOps.exif_transpose(source)
        # Flatten transparency onto white so transparent PNG text remains readable.
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        output = BytesIO()
        background.convert("RGB").save(output, format="PNG", dpi=(OCR_DPI, OCR_DPI))
    return ExtractResult(_ocr(output.getvalue()), ExtractionMethod.ocr, 1)


def extract_text(data: bytes, mime: str) -> ExtractResult:
    """Extract one validated CV or raise a safe per-file ExtractionError.

    Does not persist data or change worker/DB status; the T10 caller owns that.
    """
    try:
        actual_mime, _ = validate_file(data, "")
        if actual_mime != mime:
            raise ExtractionError("UNSUPPORTED_CV_TYPE", "Định dạng CV không hợp lệ")
        if mime == "application/pdf":
            result = _extract_pdf(data)
        elif mime == DOCX_MIME:
            result = _extract_docx(data)
        elif mime in {"image/png", "image/jpeg"}:
            result = _extract_image(data)
        else:
            raise ExtractionError("UNSUPPORTED_CV_TYPE", "Định dạng CV không hợp lệ")
        text = _normalize(result.text)
        if not text:
            raise ExtractionError()
        return ExtractResult(text, result.method, result.page_count)
    except ExtractionError:
        raise
    except Exception:
        # Parsers and OCR errors can contain document text or filenames.
        raise ExtractionError() from None
