from io import BytesIO
from uuid import uuid4

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import ANY, Stubber

from app.core.config import Settings
from app.storage import LocalStorage, S3Storage, StorageError, build_storage


def test_local_storage_roundtrip_random_keys_and_idempotent_delete(tmp_path):
    storage = LocalStorage(tmp_path / "private")
    keys = [storage.put(b"synthetic bytes", "application/pdf") for _ in range(2)]
    assert keys[0] != keys[1]
    assert all(len(key) == 32 and "synthetic" not in key for key in keys)
    for key in keys:
        assert storage.get(key) == b"synthetic bytes"
        storage.delete(key)
        storage.delete(key)
        with pytest.raises(StorageError, match="Storage unavailable"):
            storage.get(key)
    assert not list(storage.root.iterdir())


@pytest.mark.parametrize(
    "key", ["../outside", "/etc/passwd", "C:\\outside", "", "A" * 32, "a" * 31, "a" * 32 + ".pdf"]
)
def test_storage_rejects_non_opaque_keys(tmp_path, key):
    storage = LocalStorage(tmp_path)
    for operation in (storage.get, storage.delete):
        with pytest.raises(StorageError, match="Invalid storage key"):
            operation(key)


def test_local_io_failure_is_sanitized(tmp_path):
    root = tmp_path / "unavailable"
    root.write_bytes(b"synthetic")
    with pytest.raises(StorageError) as caught:
        LocalStorage(root).put(b"synthetic", "image/png")
    assert str(tmp_path) not in str(caught.value)


@pytest.fixture
def s3():
    settings = Settings(_env_file=None, s3_bucket="synthetic-cvs")
    client = boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id="synthetic-key",
        aws_secret_access_key="synthetic-secret",
    )
    with Stubber(client) as stub:
        yield S3Storage(settings, client=client), stub
        stub.assert_no_pending_responses()


def test_s3_roundtrip_is_private_and_closes_stream(s3):
    storage, stub = s3
    stub.add_response(
        "put_object",
        {},
        {"Bucket": storage.bucket, "Key": ANY, "Body": b"synthetic", "ContentType": "image/png"},
    )
    key = storage.put(b"synthetic", "image/png")
    assert len(key) == 32
    stream = BytesIO(b"synthetic")
    stub.add_response(
        "get_object", {"Body": StreamingBody(stream, 9)}, {"Bucket": storage.bucket, "Key": key}
    )
    assert storage.get(key) == b"synthetic"
    assert stream.closed
    stub.add_response("delete_object", {}, {"Bucket": storage.bucket, "Key": key})
    storage.delete(key)


def test_s3_errors_and_bad_keys_are_sanitized(s3):
    storage, stub = s3
    stub.add_client_error(
        "get_object",
        service_error_code="NoSuchKey",
        service_message="synthetic private provider detail",
    )
    with pytest.raises(StorageError, match="^Storage unavailable$"):
        storage.get(uuid4().hex)
    for operation in (storage.get, storage.delete):
        with pytest.raises(StorageError, match="Invalid storage key"):
            operation("../outside")


def test_storage_factory_and_s3_configuration(tmp_path):
    local = build_storage(Settings(_env_file=None, storage_local_dir=tmp_path))
    assert isinstance(local, LocalStorage)
    with pytest.raises(StorageError, match="S3 bucket is required"):
        build_storage(Settings(_env_file=None, storage_backend="s3", s3_bucket=""))
