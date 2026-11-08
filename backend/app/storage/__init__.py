from app.core.config import Settings
from app.storage.base import Storage, StorageError
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage

__all__ = ["Storage", "StorageError", "LocalStorage", "S3Storage", "build_storage"]


def build_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "s3":
        return S3Storage(settings)
    return LocalStorage(settings.storage_local_dir)
