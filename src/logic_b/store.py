"""Minimal injectable object-store adapters; no credentials are loaded here."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import tempfile
from typing import Protocol


class StoreNotConnected(RuntimeError):
    """Raised when a remote adapter has not been explicitly configured."""


class ObjectStore(Protocol):
    def put_bytes(self, key: str, body: bytes) -> None: ...
    def get_bytes(self, key: str) -> bytes: ...
    def actual_bytes(self) -> int: ...


def _key(key: str) -> str:
    path = PurePosixPath(key)
    if not key or path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("object key must be a safe relative POSIX path")
    return path.as_posix()


@dataclass
class LocalStore:
    """Atomic local file store with measured physical bytes."""
    root: Path

    def __post_init__(self):
        self.root = Path(self.root).resolve()

    def _path(self, key: str) -> Path:
        target = (self.root / _key(key)).resolve()
        if target != self.root and self.root not in target.parents:
            raise ValueError("object key escapes LocalStore root")
        return target

    def put_bytes(self, key: str, body: bytes) -> None:
        if not isinstance(body, bytes):
            raise TypeError("body must be bytes")
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".store-", suffix=".tmp", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(body)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temp_name, target)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def actual_bytes(self) -> int:
        if not self.root.exists():
            return 0
        return sum(path.stat().st_size for path in self.root.rglob("*") if path.is_file())


@dataclass
class R2Store:
    """R2/S3-compatible adapter. A client must be injected explicitly.

    The adapter never reads environment variables, creates a client, or emits
    bucket credentials. `actual_bytes` lists object metadata from the bucket;
    it does not substitute local cache size.
    """
    bucket: str
    client: object | None = None
    prefix: str = ""

    def _require_client(self):
        if not self.bucket or self.client is None:
            raise StoreNotConnected("R2 client and bucket are not configured")

    def _object_key(self, key: str) -> str:
        relative = _key(key)
        return f"{self.prefix.strip('/')}/{relative}".lstrip("/") if self.prefix else relative

    def put_bytes(self, key: str, body: bytes) -> None:
        self._require_client()
        if not isinstance(body, bytes):
            raise TypeError("body must be bytes")
        self.client.put_object(Bucket=self.bucket, Key=self._object_key(key), Body=body)

    def get_bytes(self, key: str) -> bytes:
        self._require_client()
        response = self.client.get_object(Bucket=self.bucket, Key=self._object_key(key))
        return response["Body"].read()

    def actual_bytes(self) -> int:
        self._require_client()
        total = 0
        token = None
        while True:
            request = {"Bucket": self.bucket, "Prefix": self.prefix.strip("/")}
            if token:
                request["ContinuationToken"] = token
            response = self.client.list_objects_v2(**request)
            total += sum(int(row["Size"]) for row in response.get("Contents", []))
            if not response.get("IsTruncated"):
                return total
            token = response.get("NextContinuationToken")
            if not token:
                raise RuntimeError("truncated R2 listing did not provide a continuation token")
