"""Bound multipart input before spooling; preserve per-file oversized errors."""

from collections.abc import AsyncGenerator

from starlette.datastructures import FormData
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.requests import Request

from app.core.errors import AppError
from app.services.cv_validation import MAX_FILE_BYTES, MAX_FILES

MAX_BATCH_BYTES = MAX_FILES * MAX_FILE_BYTES + 1024 * 1024
MAX_PART_HEADER_BYTES = 16 * 1024


class BoundedMultiPartParser(MultiPartParser):
    def on_part_begin(self) -> None:
        super().on_part_begin()
        self.file_bytes = 0
        self.header_bytes = 0

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._current_part.file is not None:
            # Keep the one-byte sentinel used by validate_file, discard the rest.
            end = min(end, start + max(0, MAX_FILE_BYTES + 1 - self.file_bytes))
            self.file_bytes += end - start
        super().on_part_data(data, start, end)

    def _count_header(self, size: int) -> None:
        self.header_bytes += size
        if self.header_bytes > MAX_PART_HEADER_BYTES:
            raise MultiPartException("Multipart headers too large")

    def on_header_field(self, data: bytes, start: int, end: int) -> None:
        self._count_header(end - start)
        super().on_header_field(data, start, end)

    def on_header_value(self, data: bytes, start: int, end: int) -> None:
        self._count_header(end - start)
        super().on_header_value(data, start, end)


async def parse_upload(request: Request) -> FormData:
    def too_large() -> AppError:
        return AppError("UPLOAD_TOO_LARGE", "Lượt tải vượt giới hạn dung lượng.", 413)

    length = request.headers.get("content-length")
    if length is not None:
        try:
            size = int(length)
            if size < 0:
                raise ValueError
        except ValueError:
            raise MultiPartException("Invalid content length") from None
        if size > MAX_BATCH_BYTES:
            raise too_large()
    content_type = request.headers.get("content-type", "")
    if len(content_type) > MAX_PART_HEADER_BYTES or not content_type.lower().startswith(
        "multipart/form-data;"
    ):
        raise MultiPartException("Multipart required")

    async def bounded_stream() -> AsyncGenerator[bytes, None]:
        received = 0
        async for chunk in request.stream():
            received += len(chunk)
            if received > MAX_BATCH_BYTES:
                raise too_large()
            yield chunk

    parser = BoundedMultiPartParser(
        request.headers,
        bounded_stream(),
        max_files=MAX_FILES,
        max_fields=1,
        max_part_size=1024,
    )
    return await parser.parse()
