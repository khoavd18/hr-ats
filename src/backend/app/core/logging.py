import json
import logging
import re
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from traceback import walk_tb
from types import TracebackType
from typing import Any

REDACTED = "[REDACTED]"
EMAIL_PATTERN = re.compile(r"[\w.!#$%&'*+/=?^`{|}~-]+@[\w-]+(?:\.[\w-]+)+", re.UNICODE)
PHONE_PATTERN = re.compile(r"(?<![\w.])(?:\+84|84(?!\.)|0(?!\.))(?:[\s().-]*\d){8,10}(?!\w)")
URL_CREDENTIALS_PATTERN = re.compile(r"([a-z][a-z0-9+.-]*://)[^/\s@]+@", re.IGNORECASE)
SENSITIVE_KEYS = {
    "text",
    "body",
    "cv",
    "content",
    "password",
    "secret",
    "secret_key",
    "token",
    "authorization",
    "cookie",
    "api_key",
    "access_key",
    "database_url",
    "redis_url",
    "email",
    "phone",
    "full_name",
    "name",
    "candidate_name",
    "address",
    "phone_number",
    "date_of_birth",
}
SENSITIVE_SUFFIXES = (
    "_text",
    "_body",
    "_content",
    "_password",
    "_secret",
    "_secret_key",
    "_token",
    "_api_key",
    "_access_key",
    "_email",
    "_phone",
    "_full_name",
    "_name",
    "_candidate_name",
    "_address",
    "_phone_number",
    "_date_of_birth",
)
DIAGNOSTIC_SUFFIXES = ("_id", "_status", "_count")
ASSIGNMENT_PATTERN = re.compile(r"(?<![\w-])(?P<key>[a-zA-Z_][\w-]*)[\"']?\s*[:=]\s*")
STANDARD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime", "taskName"}


def sensitive_key(key: str) -> bool:
    key = key.casefold().replace("-", "_")
    if key.endswith(DIAGNOSTIC_SUFFIXES):
        return False
    return key in SENSITIVE_KEYS or key.endswith(SENSITIVE_SUFFIXES)


def redact(value: Any, depth: int = 0) -> Any:
    if depth >= 10:
        return REDACTED
    if isinstance(value, Mapping):
        return {
            redact(str(key), depth + 1): (
                REDACTED if sensitive_key(str(key)) else redact(item, depth + 1)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item, depth + 1) for item in value]
    if isinstance(value, str):
        if value.lstrip().startswith(("{", "[")):
            try:
                parsed = json.loads(value)
            except (ValueError, RecursionError):
                pass
            else:
                return json.dumps(redact(parsed, depth + 1), ensure_ascii=False)
        value = URL_CREDENTIALS_PATTERN.sub(r"\1" + REDACTED + "@", value)
        value = EMAIL_PATTERN.sub(REDACTED, value)
        value = PHONE_PATTERN.sub(REDACTED, value)
        for assignment in ASSIGNMENT_PATTERN.finditer(value):
            if sensitive_key(assignment.group("key")):
                return value[: assignment.end()] + REDACTED
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact(str(value), depth + 1)


def safe_traceback(traceback: TracebackType | None) -> list[str]:
    # Walk frame metadata only: no source lookup, exception message, locals or full filesystem path.
    return [
        redact(f"{Path(frame.f_code.co_filename).name}:{line} in {frame.f_code.co_name}")
        for frame, line in walk_tb(traceback)
    ]


class PiiFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Interpolate before redaction so split arguments cannot reconstruct an email or phone.
        message = record.msg if isinstance(record.msg, Mapping) else record.getMessage()
        record.msg = redact(message)
        record.args = ()
        for key, value in list(record.__dict__.items()):
            if key not in STANDARD_FIELDS:
                record.__dict__[key] = REDACTED if sensitive_key(key) else redact(value)
        if record.exc_info and record.exc_info[0] is not None:
            record.__dict__["exception_type"] = record.exc_info[0].__name__
            record.__dict__["stack"] = safe_traceback(record.exc_info[2])
        # Keep only safe frames; raw messages, source lines and locals may contain CV data.
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": redact(record.name),
            "message": record.msg if isinstance(record.msg, Mapping) else record.getMessage(),
        }
        data.update(
            {key: value for key, value in record.__dict__.items() if key not in STANDARD_FIELDS}
        )
        return json.dumps(redact(data), ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(PiiFilter())
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        server_logger = logging.getLogger(name)
        server_logger.handlers.clear()
        server_logger.propagate = True
    # Access URLs may carry arbitrary personal data in their path/query; never log them.
    logging.getLogger("uvicorn.access").disabled = True
