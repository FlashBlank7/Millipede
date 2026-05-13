import io
from functools import lru_cache
from typing import AsyncGenerator

from minio import Minio
from minio.error import S3Error

from app.config import get_settings


class StorageClient:
    def __init__(self):
        settings = get_settings()
        endpoint = settings.storage_endpoint.replace("http://", "").replace("https://", "")
        self._client = Minio(
            endpoint,
            access_key=settings.storage_access_key,
            secret_key=settings.storage_secret_key,
            secure=settings.storage_use_ssl,
        )
        self._bucket = settings.storage_bucket
        self._ensure_bucket()

    def _ensure_bucket(self):
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    async def put_object(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self._client.put_object(
            self._bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return f"{self._bucket}/{key}"

    async def get_object(self, key: str) -> bytes:
        response = self._client.get_object(self._bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    async def delete_object(self, key: str) -> None:
        self._client.remove_object(self._bucket, key)

    def presigned_url(self, key: str, expires_seconds: int = 3600) -> str:
        from datetime import timedelta
        return self._client.presigned_get_object(self._bucket, key, expires=timedelta(seconds=expires_seconds))


_storage: StorageClient | None = None


def get_storage() -> StorageClient:
    global _storage
    if _storage is None:
        _storage = StorageClient()
    return _storage
