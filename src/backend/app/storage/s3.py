from typing import Any
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings
from app.storage.base import StorageError, validate_key


class S3Storage:
    def __init__(self, settings: Settings, *, client: Any = None) -> None:
        if not settings.s3_bucket:
            raise StorageError("S3 bucket is required")
        self.bucket = settings.s3_bucket
        self.client = (
            client
            if client is not None
            else boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint or None,
                aws_access_key_id=settings.s3_access_key.get_secret_value() or None,
                aws_secret_access_key=settings.s3_secret_key.get_secret_value() or None,
                config=Config(
                    connect_timeout=3,
                    read_timeout=10,
                    retries={"max_attempts": 2, "mode": "standard"},
                    s3={"addressing_style": "path"},
                ),
            )
        )

    def put(self, data: bytes, mime: str) -> str:
        key = uuid4().hex
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=mime)
        except (BotoCoreError, ClientError):
            raise StorageError("Storage unavailable") from None
        return key

    def get(self, key: str) -> bytes:
        validate_key(key)
        try:
            body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"]
            try:
                return body.read()
            finally:
                body.close()
        except (BotoCoreError, ClientError, OSError):
            raise StorageError("Storage unavailable") from None

    def delete(self, key: str) -> None:
        validate_key(key)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except (BotoCoreError, ClientError):
            raise StorageError("Storage unavailable") from None
