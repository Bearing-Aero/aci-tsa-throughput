"""Package-specific exceptions for tsa-throughput."""


class TSAThroughputError(Exception):
    """Base exception for tsa-throughput errors."""


class TSAThroughputHTTPError(TSAThroughputError):
    """Raised when an HTTP operation fails."""


class DiscoveryError(TSAThroughputError):
    """Raised when report discovery fails."""


class PaginationError(DiscoveryError):
    """Raised when listing pagination cannot be followed safely."""


class NormalizationError(TSAThroughputError):
    """Raised when source metadata cannot be normalized."""


class DownloadError(TSAThroughputError):
    """Raised when a report download fails."""


class ManifestError(TSAThroughputError):
    """Raised when manifest loading or writing fails."""


class StorageError(TSAThroughputError):
    """Raised when local storage operations fail."""


class ParserNotFoundError(TSAThroughputError):
    """Raised when no parser can be selected for a report."""


class ParseError(TSAThroughputError):
    """Raised when parsing a report fails."""
