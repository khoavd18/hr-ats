import os
from pathlib import Path
from uuid import uuid4

from app.storage.base import StorageError, validate_key


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        validate_key(key)
        path = self.root / key
        if path.is_symlink() or path.resolve().parent != self.root:
            raise StorageError("Invalid storage key")
        return path

    def put(self, data: bytes, mime: str) -> str:
        key = uuid4().hex
        path = self._path(key)
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(descriptor, "wb") as output:
                    output.write(data)
            except Exception:
                path.unlink(missing_ok=True)
                raise
        except OSError:
            raise StorageError("Storage unavailable") from None
        return key

    def get(self, key: str) -> bytes:
        path = self._path(key)
        try:
            return path.read_bytes()
        except OSError:
            raise StorageError("Storage unavailable") from None

    def delete(self, key: str) -> None:
        path = self._path(key)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            raise StorageError("Storage unavailable") from None
