"""Parser manifest loading and registry helpers."""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Any

from tsa_throughput.exceptions import ManifestError, ParserNotFoundError
from tsa_throughput.models import ThroughputReport
from tsa_throughput.parsing.base import ThroughputParser

MANIFEST_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ParserManifestEntry:
    """Metadata for one parser plugin from the parser manifest."""

    name: str
    module: str
    class_name: str
    valid_from: date | None
    valid_to: date | None
    priority: int
    layout_family: str | None
    description: str | None

    @classmethod
    def from_manifest(cls, data: dict[str, Any]) -> ParserManifestEntry:
        """Create an entry from raw parser manifest JSON."""
        try:
            return cls(
                name=str(data["name"]),
                module=str(data["module"]),
                class_name=str(data["class"]),
                valid_from=_parse_manifest_date(data.get("valid_from")),
                valid_to=_parse_manifest_date(data.get("valid_to")),
                priority=int(data.get("priority", 0)),
                layout_family=data.get("layout_family"),
                description=data.get("description"),
            )
        except KeyError as exc:
            raise ManifestError(f"parser manifest entry missing required field: {exc}") from exc
        except (TypeError, ValueError) as exc:
            raise ManifestError(f"invalid parser manifest entry: {data!r}") from exc

    def is_valid_for_week_end(self, week_end: date) -> bool:
        """Return whether this parser entry is valid for a report week end date."""
        if self.valid_from is not None and week_end < self.valid_from:
            return False
        return not (self.valid_to is not None and week_end > self.valid_to)


def load_parser_manifest(path: Path | None = None) -> dict[str, Any]:
    """Load the parser manifest JSON from a path or the installed package asset."""
    try:
        if path is not None:
            manifest_text = Path(path).read_text(encoding="utf-8")
        else:
            manifest_text = (
                resources.files("tsa_throughput.assets")
                .joinpath("parser_manifest.json")
                .read_text(encoding="utf-8")
            )
        manifest = json.loads(manifest_text)
    except OSError as exc:
        raise ManifestError(f"could not read parser manifest: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"could not decode parser manifest: {exc}") from exc

    if not isinstance(manifest, dict):
        raise ManifestError("parser manifest must be a JSON object")

    schema_version = manifest.get("schema_version")
    if schema_version != MANIFEST_SCHEMA_VERSION:
        raise ManifestError(
            f"unsupported parser manifest schema_version: {schema_version!r}"
        )

    parsers = manifest.get("parsers")
    if not isinstance(parsers, list):
        raise ManifestError("parser manifest must include a parsers list")

    return manifest


def list_parsers(path: Path | None = None) -> list[ParserManifestEntry]:
    """Return parser metadata from the parser manifest."""
    manifest = load_parser_manifest(path)
    return [ParserManifestEntry.from_manifest(entry) for entry in manifest["parsers"]]


def match_parser_manifest_entry(
    week_end: date,
    path: Path | None = None,
) -> ParserManifestEntry:
    """Return the highest-priority parser manifest entry for a report week end date."""
    candidates = [
        entry for entry in list_parsers(path) if entry.is_valid_for_week_end(week_end)
    ]
    candidates = sorted(candidates, key=lambda entry: entry.priority, reverse=True)

    if not candidates:
        raise ParserNotFoundError(f"no parser found for report week_end={week_end.isoformat()}")

    return candidates[0]


def get_parser(
    report: ThroughputReport,
    pdf_path: Path,
    parser_name: str | None = None,
    manifest_path: Path | None = None,
) -> ThroughputParser:
    """Select and instantiate the best parser for a report PDF."""
    entries = list_parsers(manifest_path)

    if parser_name is not None:
        candidates = [entry for entry in entries if entry.name == parser_name]
        if not candidates:
            raise ParserNotFoundError(f"parser not found: {parser_name}")
    else:
        candidates = entries
        if report.week_end is not None:
            candidates = [
                entry for entry in candidates if entry.is_valid_for_week_end(report.week_end)
            ]

    candidates = sorted(candidates, key=lambda entry: entry.priority, reverse=True)

    for entry in candidates:
        parser = _instantiate_parser(entry)
        if parser.can_parse(report, Path(pdf_path)):
            return parser

    if parser_name is not None:
        raise ParserNotFoundError(f"parser cannot parse report: {parser_name}")

    week_end = report.week_end.isoformat() if report.week_end else "unknown"
    raise ParserNotFoundError(f"no parser found for report week_end={week_end}")


def _instantiate_parser(entry: ParserManifestEntry) -> ThroughputParser:
    parser_class = _load_parser_class(entry)
    return parser_class()


def _load_parser_class(entry: ParserManifestEntry) -> type[ThroughputParser]:
    try:
        module = importlib.import_module(entry.module)
        parser_class = getattr(module, entry.class_name)
    except (ImportError, AttributeError) as exc:
        raise ManifestError(f"could not import parser {entry.name}: {exc}") from exc

    if not isinstance(parser_class, type) or not issubclass(parser_class, ThroughputParser):
        raise ManifestError(
            f"parser {entry.name} class must inherit from ThroughputParser"
        )

    return parser_class


def _parse_manifest_date(value: Any) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ManifestError(f"manifest date must be a string or null: {value!r}")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ManifestError(f"invalid manifest date: {value!r}") from exc
