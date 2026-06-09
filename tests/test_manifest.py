from __future__ import annotations

import json
import socket
from datetime import date
from pathlib import Path

import pytest

from tsa_throughput.exceptions import ManifestError
from tsa_throughput.manifest import (
    create_empty_runtime_manifest,
    find_manifest_entry,
    load_runtime_manifest,
    save_runtime_manifest,
    upsert_downloaded_report,
)
from tsa_throughput.models import RuntimeManifest, RuntimeManifestEntry


def test_loading_missing_manifest_returns_empty_manifest(tmp_path: Path) -> None:
    manifest = load_runtime_manifest(tmp_path / "manifest.json")

    assert manifest.schema_version == 1
    assert manifest.reports == []


def test_saving_manifest_creates_file(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"

    save_runtime_manifest(create_empty_runtime_manifest(), manifest_path)

    assert manifest_path.is_file()


def test_saving_manifest_creates_parent_directories(tmp_path: Path) -> None:
    manifest_path = tmp_path / "nested" / "raw" / "manifest.json"

    save_runtime_manifest(create_empty_runtime_manifest(), manifest_path)

    assert manifest_path.is_file()


def test_loading_saved_manifest_round_trips(tmp_path: Path) -> None:
    entry = _entry()
    manifest = RuntimeManifest(
        schema_version=1,
        updated_at="2026-06-08T00:00:00Z",
        reports=[entry],
    )
    manifest_path = tmp_path / "manifest.json"

    save_runtime_manifest(manifest, manifest_path)
    loaded = load_runtime_manifest(manifest_path)

    assert loaded == manifest


def test_date_fields_serialize_and_deserialize_as_iso_strings(tmp_path: Path) -> None:
    entry = _entry(week_start=date(2026, 5, 31), week_end=date(2026, 6, 6))
    manifest_path = tmp_path / "manifest.json"

    save_runtime_manifest(
        RuntimeManifest(
            schema_version=1,
            updated_at="2026-06-08T00:00:00Z",
            reports=[entry],
        ),
        manifest_path,
    )

    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    loaded = load_runtime_manifest(manifest_path)

    assert raw_manifest["reports"][0]["week_start"] == "2026-05-31"
    assert raw_manifest["reports"][0]["week_end"] == "2026-06-06"
    assert loaded.reports[0].week_start == date(2026, 5, 31)
    assert loaded.reports[0].week_end == date(2026, 6, 6)


def test_malformed_json_raises_manifest_error(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{", encoding="utf-8")

    with pytest.raises(ManifestError):
        load_runtime_manifest(manifest_path)


def test_unsupported_schema_version_raises_manifest_error(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"schema_version": 2, "updated_at": "2026-06-08T00:00:00Z", "reports": []}),
        encoding="utf-8",
    )

    with pytest.raises(ManifestError):
        load_runtime_manifest(manifest_path)


def test_missing_required_report_fields_raise_manifest_error(tmp_path: Path) -> None:
    report = _report_json()
    report.pop("sha256")
    report["week_start"] = "2026-05-31"
    report["week_end"] = "2026-06-06"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-06-08T00:00:00Z",
                "reports": [report],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="sha256"):
        load_runtime_manifest(manifest_path)


def test_upsert_downloaded_report_adds_new_entry() -> None:
    manifest = RuntimeManifest(
        schema_version=1,
        updated_at="2000-01-01T00:00:00Z",
        reports=[],
    )
    entry = _entry()

    updated = upsert_downloaded_report(manifest, entry)

    assert updated.reports == [entry]
    assert updated.updated_at != manifest.updated_at


def test_upsert_downloaded_report_replaces_existing_entry_with_same_id() -> None:
    manifest = RuntimeManifest(
        schema_version=1,
        updated_at="2000-01-01T00:00:00Z",
        reports=[_entry(sha256="old")],
    )
    replacement = _entry(sha256="new")

    updated = upsert_downloaded_report(manifest, replacement)

    assert updated.reports == [replacement]
    assert updated.updated_at != manifest.updated_at


def test_reports_are_sorted_deterministically() -> None:
    first = _entry(
        canonical_id="tsa-throughput-week-ending-2026-06-06-a",
        week_end=date(2026, 6, 6),
    )
    second = _entry(
        canonical_id="tsa-throughput-week-ending-2026-06-06-b",
        week_end=date(2026, 6, 6),
    )
    third = _entry(
        canonical_id="tsa-throughput-week-ending-2026-06-13",
        week_start=date(2026, 6, 7),
        week_end=date(2026, 6, 13),
    )
    undated = _entry(canonical_id="tsa-throughput-week-ending-unknown", week_end=None)
    manifest = RuntimeManifest(
        schema_version=1,
        updated_at="2000-01-01T00:00:00Z",
        reports=[third, undated, second, first],
    )

    updated = upsert_downloaded_report(manifest, second)

    assert [entry.canonical_id for entry in updated.reports] == [
        first.canonical_id,
        second.canonical_id,
        third.canonical_id,
        undated.canonical_id,
    ]


def test_find_manifest_entry_returns_expected_entry() -> None:
    expected = _entry()
    manifest = RuntimeManifest(
        schema_version=1,
        updated_at="2026-06-08T00:00:00Z",
        reports=[expected],
    )

    assert find_manifest_entry(manifest, expected.canonical_id) == expected


def test_find_manifest_entry_returns_none_for_missing_id() -> None:
    manifest = RuntimeManifest(
        schema_version=1,
        updated_at="2026-06-08T00:00:00Z",
        reports=[_entry()],
    )

    assert find_manifest_entry(manifest, "missing") is None


def test_runtime_manifest_makes_no_network_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("Runtime manifest should not open network sockets")

    monkeypatch.setattr(socket, "socket", fail_socket)
    manifest_path = tmp_path / "manifest.json"
    manifest = upsert_downloaded_report(create_empty_runtime_manifest(), _entry())

    save_runtime_manifest(manifest, manifest_path)

    assert load_runtime_manifest(manifest_path) == manifest


def _entry(**overrides: object) -> RuntimeManifestEntry:
    data = _report_json()
    data.update(overrides)
    return RuntimeManifestEntry(**data)


def _report_json() -> dict[str, object]:
    return {
        "canonical_id": "tsa-throughput-week-ending-2026-06-06",
        "week_start": date(2026, 5, 31),
        "week_end": date(2026, 6, 6),
        "source_url": (
            "https://www.tsa.gov/sites/default/files/foia-readingroom/"
            "tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf"
        ),
        "source_filename": "tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf",
        "canonical_filename": "tsa-throughput-week-ending-2026-06-06.pdf",
        "local_path": "tsa-throughput-week-ending-2026-06-06.pdf",
        "sha256": "abc123",
        "bytes": 123456,
        "downloaded_at": "2026-06-08T00:00:00Z",
        "date_confidence": "title_url_match",
    }
