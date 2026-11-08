import io
import json
import logging

import pytest

from app.core.logging import REDACTED, JsonFormatter, PiiFilter

# Synthetic examples explicitly required by T02; no candidate information is used.
FAKE_EMAIL = "abc@gmail.com"
FAKE_PHONE = "0912 345 678"
FAKE_CV = "Nội dung CV giả dùng kiểm tra bộ lọc."


@pytest.fixture
def log_output():
    output = io.StringIO()
    logger = logging.Logger("t02.synthetic", level=logging.DEBUG)
    handler = logging.StreamHandler(output)
    handler.addFilter(PiiFilter())
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    return logger, output


def test_emails_and_spaced_phones_are_redacted_in_interpolated_logs(log_output) -> None:
    logger, output = log_output
    logger.info("Synthetic input %s %s", FAKE_EMAIL, FAKE_PHONE)
    record = json.loads(output.getvalue())
    assert record["message"] == f"Synthetic input {REDACTED} {REDACTED}"
    assert FAKE_EMAIL not in output.getvalue()
    assert FAKE_PHONE not in output.getvalue()
    assert record["level"] == "INFO"
    assert record["timestamp"].endswith("+00:00")


def test_split_log_arguments_cannot_reconstruct_pii(log_output) -> None:
    logger, output = log_output
    logger.info("%s@%s %s%s", "abc", "gmail.com", "0912 ", "345 678")
    assert json.loads(output.getvalue())["message"] == f"{REDACTED} {REDACTED}"


@pytest.mark.parametrize("key", ["text", "body", "cv", "content", "CV_TEXT", "email_body"])
def test_sensitive_fields_are_removed_recursively_without_mutating_input(log_output, key) -> None:
    logger, output = log_output
    payload = {"items": [{key: FAKE_CV, "email": FAKE_EMAIL}], "count": 1}
    logger.info("Synthetic event", extra={"payload": payload})
    result = json.loads(output.getvalue())
    assert result["payload"]["items"] == [{key: REDACTED, "email": REDACTED}]
    assert result["payload"]["count"] == 1
    assert payload["items"][0][key] == FAKE_CV
    assert FAKE_CV not in output.getvalue()


def test_dict_message_and_json_message_are_redacted(log_output) -> None:
    logger, output = log_output
    logger.info({"body": FAKE_CV, "phone": FAKE_PHONE})
    logger.info(json.dumps({"text": FAKE_CV, "email": FAKE_EMAIL}))
    first, second = map(json.loads, output.getvalue().splitlines())
    assert first["message"] == {"body": REDACTED, "phone": REDACTED}
    assert json.loads(second["message"]) == {"text": REDACTED, "email": REDACTED}


def test_key_value_messages_and_secrets_are_redacted(log_output) -> None:
    logger, output = log_output
    logger.info("Synthetic body=%s", FAKE_CV, extra={"api_key": "synthetic-secret"})
    result = json.loads(output.getvalue())
    assert result["message"] == f"Synthetic body={REDACTED}"
    assert result["api_key"] == REDACTED
    assert FAKE_CV not in output.getvalue()
    assert "synthetic-secret" not in output.getvalue()


def test_exception_content_is_omitted_but_safe_frames_are_logged(log_output) -> None:
    logger, output = log_output
    try:
        raise ValueError(FAKE_CV)
    except ValueError:
        logger.exception("Synthetic exception")
    result = json.loads(output.getvalue())
    assert result["exception_type"] == "ValueError"
    assert FAKE_CV not in output.getvalue()
    assert "Traceback" not in output.getvalue()
    assert result["stack"]
    assert result["stack"][-1].startswith("test_logging.py:")
    assert result["stack"][-1].endswith(
        " in test_exception_content_is_omitted_but_safe_frames_are_logged"
    )
    assert "raise ValueError" not in output.getvalue()


def test_cyclic_payload_is_bounded(log_output) -> None:
    logger, output = log_output
    payload = {}
    payload["nested"] = payload
    logger.info("Synthetic cycle", extra={"payload": payload})
    assert REDACTED in output.getvalue()
    json.loads(output.getvalue())


def test_url_credentials_and_numeric_phone_fields_are_redacted(log_output) -> None:
    logger, output = log_output
    logger.info(
        "Connection postgresql+psycopg://synthetic:synthetic-secret@localhost/hr_ats_test",
        extra={"phone": 912345678, "database_url": "synthetic-db-url"},
    )
    result = json.loads(output.getvalue())
    assert "synthetic-secret" not in output.getvalue()
    assert "synthetic-db-url" not in output.getvalue()
    assert result["phone"] == REDACTED


def test_pii_in_mapping_keys_is_redacted(log_output) -> None:
    logger, output = log_output
    logger.info("Synthetic keyed data", extra={"payload": {FAKE_EMAIL: FAKE_PHONE}})
    assert FAKE_EMAIL not in output.getvalue()
    assert json.loads(output.getvalue())["payload"] == {REDACTED: REDACTED}


@pytest.mark.parametrize(
    "key", ["cv_file_id", "email_status", "context", "cv_count", "body_id", "content_type"]
)
def test_diagnostic_fields_are_preserved(log_output, key: str) -> None:
    logger, output = log_output
    logger.info("Synthetic diagnostic", extra={key: "synthetic-diagnostic"})
    assert json.loads(output.getvalue())[key] == "synthetic-diagnostic"


@pytest.mark.parametrize(
    "message",
    [
        "Processing context: job 42",
        "Content-Type: application/json",
        "Retry in 0.1234567890 seconds",
        "Retry in 10.0912345678 seconds",
        "email_status=sent cv_file_id=synthetic-id cv_count=2",
    ],
)
def test_diagnostic_messages_are_preserved(log_output, message: str) -> None:
    logger, output = log_output
    logger.info(message)
    assert json.loads(output.getvalue())["message"] == message


@pytest.mark.parametrize(
    "key",
    ["note_text", "email_body", "access_token", "smtp_password", "secret_key", "s3_secret_key"],
)
def test_sensitive_suffix_assignments_are_redacted(log_output, key: str) -> None:
    logger, output = log_output
    logger.info("%s=%s", key, FAKE_CV)
    assert FAKE_CV not in output.getvalue()
    assert json.loads(output.getvalue())["message"] == f"{key}={REDACTED}"


def test_diagnostic_field_values_still_mask_pii(log_output) -> None:
    logger, output = log_output
    logger.info("Synthetic diagnostic", extra={"cv_file_id": FAKE_EMAIL, "context": FAKE_PHONE})
    result = json.loads(output.getvalue())
    assert result["cv_file_id"] == result["context"] == REDACTED
