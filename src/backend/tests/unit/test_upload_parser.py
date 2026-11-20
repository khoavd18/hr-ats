import asyncio
from tempfile import SpooledTemporaryFile

import pytest
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException
from starlette.requests import Request

from app.api import upload_parser
from app.core.errors import AppError


def request_for(chunks, extra_headers=()):
    pieces = iter(chunks)

    async def receive():
        piece = next(pieces, None)
        return {"type": "http.request", "body": piece or b"", "more_body": piece is not None}

    return Request(
        {
            "type": "http",
            "headers": [
                (b"content-type", b"multipart/form-data; boundary=synthetic"),
                *extra_headers,
            ],
        },
        receive,
    )


def multipart(data):
    return [
        b'--synthetic\r\nContent-Disposition: form-data; name="files"; filename="cv.pdf"\r\n\r\n',
        data,
        b"\r\n--synthetic--\r\n",
    ]


def test_per_file_spool_is_bounded_and_keeps_oversize_sentinel(monkeypatch):
    monkeypatch.setattr(upload_parser, "MAX_FILE_BYTES", 8)

    async def check():
        form = await upload_parser.parse_upload(request_for(multipart(b"x" * 100)))
        try:
            file = form["files"]
            assert isinstance(file, UploadFile)
            assert file.size == 9 and await file.read() == b"x" * 9
        finally:
            await form.close()
        assert file.file.closed

    asyncio.run(check())


@pytest.mark.parametrize("length", [None, b"1", b"9999"])
def test_stream_budget_cannot_be_bypassed_by_missing_or_forged_length(monkeypatch, length):
    monkeypatch.setattr(upload_parser, "MAX_BATCH_BYTES", 120)
    opened = []

    def temporary(*args, **kwargs):
        file = SpooledTemporaryFile(*args, **kwargs)
        opened.append(file)
        return file

    monkeypatch.setattr("starlette.formparsers.SpooledTemporaryFile", temporary)
    headers = [(b"content-length", length)] if length else []
    with pytest.raises(AppError) as error:
        asyncio.run(upload_parser.parse_upload(request_for(multipart(b"x" * 100), headers)))
    assert error.value.status == 413
    assert all(file.closed for file in opened)


def test_multipart_headers_are_bounded(monkeypatch):
    monkeypatch.setattr(upload_parser, "MAX_PART_HEADER_BYTES", 100)
    with pytest.raises(MultiPartException):
        asyncio.run(
            upload_parser.parse_upload(
                request_for(
                    [
                        b'--synthetic\r\nContent-Disposition: form-data; name="' + b"x" * 150,
                    ]
                )
            )
        )
