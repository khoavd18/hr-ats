import re
from typing import Protocol


class StorageError(Exception):
    """Storage failures never expose paths, credentials or provider messages."""


def validate_key(key: str) -> None:
    if re.fullmatch(r"[0-9a-f]{32}", key) is None:
        raise StorageError("Invalid storage key")


class Storage(Protocol):
    def put(self, data: bytes, mime: str) -> str: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...
