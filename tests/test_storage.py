from __future__ import annotations

import socket
from pathlib import Path

import pytest

from tsa_throughput.exceptions import StorageError
from tsa_throughput.storage import LocalStorage


def test_local_storage_creates_root_directory(tmp_path: Path) -> None:
    root = tmp_path / "storage"

    storage = LocalStorage(root)

    assert storage.root == root.resolve()
    assert root.is_dir()


def test_write_bytes_writes_file(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "storage")

    path = storage.write_bytes("example.pdf", b"pdf bytes")

    assert path == storage.path_for("example.pdf")
    assert path.read_bytes() == b"pdf bytes"


def test_read_bytes_reads_written_bytes(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "storage")
    storage.write_bytes("example.pdf", b"pdf bytes")

    assert storage.read_bytes("example.pdf") == b"pdf bytes"


def test_exists_reports_existing_and_missing_keys(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "storage")
    storage.write_bytes("example.pdf", b"pdf bytes")

    assert storage.exists("example.pdf") is True
    assert storage.exists("missing.pdf") is False


def test_nested_keys_create_parent_directories(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "storage")

    path = storage.write_bytes("reports/example.pdf", b"pdf bytes")

    assert path.parent == storage.root / "reports"
    assert path.is_file()


def test_backslash_separators_are_normalized(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "storage")

    path = storage.write_bytes("reports\\example.pdf", b"pdf bytes")

    assert path == storage.root / "reports" / "example.pdf"
    assert path.read_bytes() == b"pdf bytes"


def test_write_bytes_does_not_overwrite_by_default(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "storage")
    storage.write_bytes("example.pdf", b"original")

    with pytest.raises(StorageError):
        storage.write_bytes("example.pdf", b"replacement")

    assert storage.read_bytes("example.pdf") == b"original"


def test_write_bytes_overwrites_when_requested(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "storage")
    storage.write_bytes("example.pdf", b"original")

    storage.write_bytes("example.pdf", b"replacement", overwrite=True)

    assert storage.read_bytes("example.pdf") == b"replacement"


def test_path_for_returns_path_inside_storage_root(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "storage")

    path = storage.path_for("reports/example.pdf")

    assert path == storage.root / "reports" / "example.pdf"
    assert path.is_relative_to(storage.root)


@pytest.mark.parametrize(
    "key",
    [
        "/absolute/example.pdf",
        "C:\\absolute\\example.pdf",
        "\\\\server\\share\\example.pdf",
        str(Path.cwd() / "example.pdf"),
    ],
)
def test_absolute_keys_are_rejected(tmp_path: Path, key: str) -> None:
    storage = LocalStorage(tmp_path / "storage")

    with pytest.raises(StorageError):
        storage.path_for(key)


@pytest.mark.parametrize(
    "key",
    [
        "../example.pdf",
        "reports/../example.pdf",
        "reports/../../example.pdf",
    ],
)
def test_traversal_keys_are_rejected(tmp_path: Path, key: str) -> None:
    storage = LocalStorage(tmp_path / "storage")

    with pytest.raises(StorageError):
        storage.path_for(key)


def test_keys_that_resolve_outside_root_are_rejected(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "storage")
    outside = tmp_path / "outside"
    outside.mkdir()
    (storage.root / "linked").symlink_to(outside)

    with pytest.raises(StorageError):
        storage.path_for("linked/example.pdf")


@pytest.mark.parametrize("key", ["", ".", "./"])
def test_empty_keys_are_rejected(tmp_path: Path, key: str) -> None:
    storage = LocalStorage(tmp_path / "storage")

    with pytest.raises(StorageError):
        storage.path_for(key)


def test_storage_failures_raise_package_specific_exceptions(tmp_path: Path) -> None:
    root = tmp_path / "storage"
    root.write_bytes(b"I am a file, not a directory")

    with pytest.raises(StorageError):
        LocalStorage(root)


def test_local_storage_makes_no_network_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("LocalStorage should not open network sockets")

    monkeypatch.setattr(socket, "socket", fail_socket)
    storage = LocalStorage(tmp_path / "storage")

    storage.write_bytes("example.pdf", b"pdf bytes")

    assert storage.read_bytes("example.pdf") == b"pdf bytes"
