"""Immutable, content-addressed source file storage."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
import os
import tempfile


class BlobStore(Protocol):
    def put(self, sha256: str, content: bytes, suffix: str = ".xls") -> str: ...
    def path_for(self, storage_key: str) -> Path: ...
    def healthcheck(self) -> None: ...


class LocalBlobStore:
    def __init__(self, root: Path):
        self.root = root

    def put(self, sha256: str, content: bytes, suffix: str = ".xls") -> str:
        storage_key = f"{sha256[:2]}/{sha256}{suffix}"
        target = self.path_for(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() != content:
                raise ValueError("Content-addressed storage collision")
            return storage_key
        fd, temporary = tempfile.mkstemp(dir=target.parent, prefix=".upload-")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return storage_key

    def path_for(self, storage_key: str) -> Path:
        candidate = (self.root / storage_key).resolve()
        root = self.root.resolve()
        if root not in candidate.parents:
            raise ValueError("Invalid storage key")
        return candidate

    def healthcheck(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir() or not os.access(self.root, os.R_OK | os.W_OK | os.X_OK):
            raise OSError(f"Blob root is not accessible: {self.root}")
