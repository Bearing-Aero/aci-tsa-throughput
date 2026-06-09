from tsa_throughput.exceptions import (
    DiscoveryError,
    DownloadError,
    ManifestError,
    NormalizationError,
    PaginationError,
    ParseError,
    ParserNotFoundError,
    StorageError,
    TSAThroughputError,
    TSAThroughputHTTPError,
)


def test_custom_exceptions_inherit_from_base_error() -> None:
    exception_types = [
        TSAThroughputHTTPError,
        DiscoveryError,
        PaginationError,
        NormalizationError,
        DownloadError,
        ManifestError,
        StorageError,
        ParserNotFoundError,
        ParseError,
    ]

    for exception_type in exception_types:
        assert issubclass(exception_type, TSAThroughputError)


def test_pagination_error_inherits_from_discovery_error() -> None:
    assert issubclass(PaginationError, DiscoveryError)
