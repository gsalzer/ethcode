class ArtifactError(Exception):
    """Base class for package errors."""


class InvalidArtifactError(ArtifactError, ValueError):
    """An address, source bundle, bytecode value, or model is malformed."""


class ProviderError(ArtifactError):
    """A provider could not produce an observation."""

    _CATEGORIES = frozenset({
        "credentials_missing", "dns", "tls", "timeout", "connection", "http",
        "rate_limit", "quota", "invalid_json", "invalid_provider_response",
        "cache_corruption", "request_scheduling", "unknown_operational",
    })
    _ORIGINS = frozenset({"cache", "request", "configuration"})

    def __init__(self, detail: str, *, provider: str | None = None,
                 category: str = "unknown_operational", artifact_kind=None,
                 retryable: bool = True, origin: str = "request",
                 completed_kinds=(), http_status: int | None = None,
                 details=None) -> None:
        if category not in self._CATEGORIES:
            raise ValueError(f"invalid provider failure category: {category!r}")
        if origin not in self._ORIGINS:
            raise ValueError(f"invalid provider failure origin: {origin!r}")
        self.provider = provider
        self.detail = detail
        self.category = category
        self.artifact_kind = artifact_kind
        self.retryable = retryable
        self.origin = origin
        self.completed_kinds = tuple(completed_kinds)
        self.http_status = http_status
        self.details = dict(details or {})
        super().__init__(detail)


class ProviderUnavailableError(ProviderError):
    """A configuration or operational failure prevented a lookup."""


class ProviderLimitError(ProviderUnavailableError):
    """A provider rejected a request because a usage limit was reached."""

    kind = "limit"
    category_name = "unknown_operational"

    def __init__(self, provider: str, detail: str, **context) -> None:
        self.limit_detail = detail
        super().__init__(
            f"{provider} {self.kind} limit: {detail}", provider=provider.casefold(),
            category=self.category_name, retryable=self.kind == "rate", **context)
        self.detail = detail


class ProviderRateLimitError(ProviderLimitError):
    kind = "rate"
    category_name = "rate_limit"


class ProviderQuotaError(ProviderLimitError):
    kind = "quota"
    category_name = "quota"


class CacheError(ArtifactError):
    """A cache entry cannot be read or safely written."""
