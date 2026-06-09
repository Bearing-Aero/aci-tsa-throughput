"""Base parser interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from tsa_throughput.models import ParseResult, ThroughputReport


class ThroughputParser(ABC):
    """Base interface for TSA throughput PDF parser plugins."""

    parser_name: str
    parser_version: str
    layout_family: str

    @abstractmethod
    def parse(
        self,
        source_file: Path,
        *,
        max_pages: int | None = None,
        report: ThroughputReport | None = None,
    ) -> ParseResult:
        """Parse a source PDF into canonical throughput records."""
