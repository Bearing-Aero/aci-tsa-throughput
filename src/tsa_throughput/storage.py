"""Storage helpers for downloaded reports."""

from __future__ import annotations

import os
import tempfile
from contextlib import suppress
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Protocol

from tsa_throughput.exceptions import StorageError


class Storage(Protocol):
    """Protocol for byte-addressable report storage."""

    def exists(self, key: str) -> bool:
        """Return whether a storage key exists."""

    def write_bytes(self, key: str, data: bytes, overwrite: bool = False) -> Path:
        """Write bytes to a storage key and return the local path."""

    def read_bytes(self, key: str) -> bytes:
        """Read bytes from a storage key."""

    def path_for(self, key: str) -> Path:
        """Return the local path for a storage key."""


class LocalStorage:
    """Local filesystem implementation of :class:`Storage`."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser().resolve(strict=False)
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageError(f"Could not create storage root: {self.root}") from exc

        if not self.root.is_dir():
            raise StorageError(f"Storage root is not a directory: {self.root}")

    def exists(self, key: str) -> bool:
        return self.path_for(key).exists()

    def write_bytes(self, key: str, data: bytes, overwrite: bool = False) -> Path:
        path = self.path_for(key)
        temp_path: Path | None = None

        if path.exists() and not overwrite:
            raise StorageError(f"Storage key already exists: {key}")

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(data)
                temp_file.flush()
                os.fsync(temp_file.fileno())

            if overwrite:
                temp_path.replace(path)
            else:
                try:
                    os.link(temp_path, path)
                except FileExistsError:
                    raise StorageError(f"Storage key already exists: {key}") from None
                except OSError:
                    if path.exists():
                        raise StorageError(f"Storage key already exists: {key}") from None
                    temp_path.rename(path)

            return path
        except StorageError:
            raise
        except OSError as exc:
            raise StorageError(f"Could not write storage key: {key}") from exc
        finally:
            if temp_path is not None and temp_path.exists():
                with suppress(OSError):
                    temp_path.unlink()

    def read_bytes(self, key: str) -> bytes:
        path = self.path_for(key)
        try:
            return path.read_bytes()
        except OSError as exc:
            raise StorageError(f"Could not read storage key: {key}") from exc

    def path_for(self, key: str) -> Path:
        normalized_key = _normalize_key(key)
        candidate = (self.root / normalized_key).resolve(strict=False)
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise StorageError(f"Storage key resolves outside root: {key}") from exc
        return candidate


def _normalize_key(key: str) -> PurePosixPath:
    if not key:
        raise StorageError("Storage key cannot be empty")

    if Path(key).is_absolute() or PureWindowsPath(key).is_absolute():
        raise StorageError(f"Storage key must be relative: {key}")

    normalized = key.replace("\\", "/")
    path = PurePosixPath(normalized)

    if path.is_absolute():
        raise StorageError(f"Storage key must be relative: {key}")

    parts = path.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise StorageError(f"Storage key contains invalid path segments: {key}")

    return path
