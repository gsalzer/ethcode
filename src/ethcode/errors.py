class ArtifactError(Exception):
    """Base class for package errors."""


class InvalidArtifactError(ArtifactError, ValueError):
    """An address, source bundle, or bytecode value is malformed."""


class ProviderError(ArtifactError):
    """A provider could not produce an observation."""


class ProviderUnavailableError(ProviderError):
    """A transient or configuration failure prevented a lookup."""


class ProviderLimitError(ProviderUnavailableError):
    """A provider rejected a request because a usage limit was reached."""

    kind = "limit"

    def __init__(self, provider: str, detail: str) -> None:
        self.provider = provider
        self.detail = detail
        super().__init__(f"{provider} {self.kind} limit: {detail}")


class ProviderRateLimitError(ProviderLimitError):
    """The provider's short-window request rate was exceeded."""

    kind = "rate"


class ProviderQuotaError(ProviderLimitError):
    """A daily, community, monthly, or other call quota was exhausted."""

    kind = "quota"


class ArtifactConflictError(ArtifactError, ValueError):
    """Providers supplied incompatible artifacts."""


class CacheError(ArtifactError):
    """A cache entry cannot be read or safely written."""

