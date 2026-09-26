"""
Object storage abstraction.

For the hackathon prototype we save files to local disk under UPLOAD_DIR and
serve them via a static mount (see main.py). To go to production, implement
a new class with the same `save()` / `url_for()` interface backed by S3 / GCS
/ Azure Blob, and switch it on via STORAGE_BACKEND in the environment --
nothing else in the app needs to change.
"""
import os
import uuid
from abc import ABC, abstractmethod
from fastapi import UploadFile

from app.config import settings


class StorageBackend(ABC):
    @abstractmethod
    def save(self, file: UploadFile) -> str:
        """Persist the file and return a stable identifier/path."""

    @abstractmethod
    def url_for(self, stored_path: str) -> str:
        """Return a URL the frontend can use to fetch the file."""


class LocalStorage(StorageBackend):
    def __init__(self, upload_dir: str):
        self.upload_dir = upload_dir
        os.makedirs(self.upload_dir, exist_ok=True)

    def save(self, file: UploadFile) -> str:
        ext = os.path.splitext(file.filename or "")[1] or ".jpg"
        filename = f"{uuid.uuid4().hex}{ext}"
        dest_path = os.path.join(self.upload_dir, filename)
        with open(dest_path, "wb") as out:
            out.write(file.file.read())
        return filename  # stored relative to upload_dir

    def url_for(self, stored_path: str) -> str:
        return f"/uploads/{stored_path}"


# class S3Storage(StorageBackend):
#     """Sketch for a production swap-in. Implement using boto3.
#     def save(self, file: UploadFile) -> str: upload to bucket, return object key
#     def url_for(self, stored_path: str) -> str: return signed/public S3 URL
#     """


def get_storage() -> StorageBackend:
    if settings.STORAGE_BACKEND == "local":
        return LocalStorage(settings.UPLOAD_DIR)
    # Extend here: elif settings.STORAGE_BACKEND == "s3": return S3Storage(...)
    return LocalStorage(settings.UPLOAD_DIR)


storage = get_storage()
