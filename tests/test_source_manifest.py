from __future__ import annotations

import json
import socket
from datetime import date
from pathlib import Path

import pytest

from tsa_throughput.exceptions import ManifestError
from tsa_throughput.models import SourceManifest, ThroughputReport
from tsa_throughput.source_manifest import (
    create_source_manifest,
    find_source_report,
    list_source_reports,
    load_installed_source_manifest,
    load_source_manifest,
    save_source_manifest,
)

MODERN_CANONICAL_ID = "tsa-throughput-week-ending-2026-06-06"
MODERN_TITLE = "TSA Throughput Data to May 31, 2026 to June 6, 2026"
MODERN_FILENAME = "tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf"
MODERN_CANONICAL_FILENAME = "tsa-throughput-week-ending-2026-06-06.pdf"
MODERN_URL = f"https://www.tsa.gov/sites/default/files/foia-readingroom/{MODERN_FILENAME}"
LISTING_URL = (
    "https://www.tsa.gov/foia/readingroom?title=&field_foia_tax_category_target_id=1132&page=0"
)


def test_load_installed_source_manifest_loads_package_asset() -> None:
    manifest = load_installed_source_manifest()

    assert manifest.schema_version == 1
    assert manifest.source_name == "TSA FOIA Reading Room"


def test_installed_source_manifest_contains_at_least_one_report() -> None:
    manifest = load_installed_source_manifest()

    assert manifest.reports


def test_installed_source_manifest_contains_modern_fixture_report() -> None:
    report = find_source_report(MODERN_CANONICAL_ID, load_installed_source_manifest())

    assert report is not None
    assert report.title == MODERN_TITLE


def test_load_source_manifest_loads_temporary_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "source_manifest.json"
    manifest_path.write_text(json.dumps(_manifest_json()), encoding="utf-8")

    manifest = load_source_manifest(manifest_path)

    assert manifest.reports == [_report()]


def test_save_source_manifest_writes_manifest_file(tmp_path: Path) -> None:
    manifest_path = tmp_path / "source_manifest.json"

    save_source_manifest(_manifest(), manifest_path)

    assert manifest_path.is_file()


def test_save_source_manifest_creates_parent_directories(tmp_path: Path) -> None:
    manifest_path = tmp_path / "nested" / "sources" / "source_manifest.json"

    save_source_manifest(_manifest(), manifest_path)

    assert manifest_path.is_file()


def test_save_and_load_round_trip_correctly(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest_path = tmp_path / "source_manifest.json"

    save_source_manifest(manifest, manifest_path)
    loaded = load_source_manifest(manifest_path)

    assert loaded == manifest


def test_date_fields_serialize_and_deserialize_as_iso_strings(tmp_path: Path) -> None:
    manifest_path = tmp_path / "source_manifest.json"

    save_source_manifest(_manifest(), manifest_path)

    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    loaded = load_source_manifest(manifest_path)

    assert raw_manifest["reports"][0]["week_start"] == "2026-05-31"
    assert raw_manifest["reports"][0]["week_end"] == "2026-06-06"
    assert loaded.reports[0].week_start == date(2026, 5, 31)
    assert loaded.reports[0].week_end == date(2026, 6, 6)


def test_create_source_manifest_sorts_reports_deterministically() -> None:
    older = _report()
    newer = _report(
        canonical_id="tsa-throughput-week-ending-2026-06-13",
        week_start=date(2026, 6, 7),
        week_end=date(2026, 6, 13),
        canonical_filename="tsa-throughput-week-ending-2026-06-13.pdf",
    )
    undated = _report(
        canonical_id="tsa-throughput-week-ending-unknown",
        week_start=None,
        week_end=None,
        canonical_filename="tsa-throughput-week-ending-unknown.pdf",
    )

    manifest = create_source_manifest(
        [undated, older, newer],
        generated_at="2026-06-08T00:00:00Z",
    )

    assert [report.canonical_id for report in manifest.reports] == [
        "tsa-throughput-week-ending-2026-06-13",
        MODERN_CANONICAL_ID,
        "tsa-throughput-week-ending-unknown",
    ]


def test_list_source_reports_returns_reports_from_provided_manifest() -> None:
    manifest = _manifest()

    assert list_source_reports(manifest) == manifest.reports


def test_find_source_report_returns_expected_report() -> None:
    expected = _report()
    manifest = _manifest(reports=[expected])

    assert find_source_report(expected.canonical_id or "", manifest) == expected


def test_find_source_report_returns_none_for_missing_canonical_id() -> None:
    assert find_source_report("missing", _manifest()) is None


def test_unsupported_schema_version_raises_manifest_error(tmp_path: Path) -> None:
    manifest = _manifest_json()
    manifest["schema_version"] = 2
    manifest_path = tmp_path / "source_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ManifestError):
        load_source_manifest(manifest_path)


def test_malformed_json_raises_manifest_error(tmp_path: Path) -> None:
    manifest_path = tmp_path / "source_manifest.json"
    manifest_path.write_text("{", encoding="utf-8")

    with pytest.raises(ManifestError):
        load_source_manifest(manifest_path)


def test_missing_required_report_fields_raise_manifest_error(tmp_path: Path) -> None:
    manifest = _manifest_json()
    manifest["reports"][0].pop("source_url")
    manifest_path = tmp_path / "source_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ManifestError, match="source_url"):
        load_source_manifest(manifest_path)


def test_source_manifest_makes_no_network_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("Source manifest should not open network sockets")

    monkeypatch.setattr(socket, "socket", fail_socket)
    manifest_path = tmp_path / "source_manifest.json"
    save_source_manifest(_manifest(), manifest_path)

    assert load_source_manifest(manifest_path) == _manifest()


def _manifest(
    reports: list[ThroughputReport] | None = None,
) -> SourceManifest:
    return SourceManifest(
        schema_version=1,
        generated_at="2026-06-08T00:00:00Z",
        source_name="TSA FOIA Reading Room",
        source_listing_url=LISTING_URL,
        reports=reports if reports is not None else [_report()],
    )


def _report(**overrides: object) -> ThroughputReport:
    data = {
        "canonical_id": MODERN_CANONICAL_ID,
        "week_start": date(2026, 5, 31),
        "week_end": date(2026, 6, 6),
        "title": MODERN_TITLE,
        "source_url": MODERN_URL,
        "source_filename": MODERN_FILENAME,
        "canonical_filename": MODERN_CANONICAL_FILENAME,
        "date_confidence": "title_url_match",
        "listing_url": LISTING_URL,
        "alternate_urls": [],
    }
    data.update(overrides)
    return ThroughputReport(**data)


def _manifest_json() -> dict[str, object]:
    return {
        "schema_version": 1,
        "generated_at": "2026-06-08T00:00:00Z",
        "source": {
            "name": "TSA FOIA Reading Room",
            "listing_url": LISTING_URL,
        },
        "reports": [
            {
                "canonical_id": MODERN_CANONICAL_ID,
                "week_start": "2026-05-31",
                "week_end": "2026-06-06",
                "title": MODERN_TITLE,
                "source_url": MODERN_URL,
                "source_filename": MODERN_FILENAME,
                "canonical_filename": MODERN_CANONICAL_FILENAME,
                "date_confidence": "title_url_match",
                "listing_url": LISTING_URL,
                "alternate_urls": [],
            }
        ],
    }
