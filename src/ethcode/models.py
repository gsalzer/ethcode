from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Mapping, TypeAlias

from .errors import InvalidArtifactError

JSONValue: TypeAlias = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")


class ArtifactKind(str, Enum):
    SOURCE = "source"
    CREATION = "creation"
    RUNTIME = "runtime"


class OutcomeStatus(str, Enum):
    FOUND = "found"
    ABSENT = "absent"


class FailureCategory(str, Enum):
    CREDENTIALS_MISSING = "credentials_missing"
    DNS = "dns"
    TLS = "tls"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    HTTP = "http"
    RATE_LIMIT = "rate_limit"
    QUOTA = "quota"
    INVALID_JSON = "invalid_json"
    INVALID_PROVIDER_RESPONSE = "invalid_provider_response"
    CACHE_CORRUPTION = "cache_corruption"
    REQUEST_SCHEDULING = "request_scheduling"
    UNKNOWN_OPERATIONAL = "unknown_operational"


class FailureOrigin(str, Enum):
    CACHE = "cache"
    REQUEST = "request"
    CONFIGURATION = "configuration"


@dataclass(frozen=True)
class ContractLocation:
    address: str
    chain_id: int = 1

    def __post_init__(self) -> None:
        if isinstance(self.chain_id, bool) or not isinstance(self.chain_id, int) or self.chain_id <= 0:
            raise InvalidArtifactError("chain_id must be a positive integer")
        if not isinstance(self.address, str) or not _ADDRESS.fullmatch(self.address):
            raise InvalidArtifactError("address must be 0x followed by 40 hexadecimal characters")
        object.__setattr__(self, "address", self.address.lower())


@dataclass(frozen=True)
class SourceBundle:
    language: str
    sources: Mapping[str, str]
    version: str | None = None
    settings: Mapping[str, JSONValue] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.language, str) or not self.language.strip():
            raise InvalidArtifactError("source language must be nonempty text")
        if not self.sources or any(not isinstance(path, str) or not path or
                                   not isinstance(content, str)
                                   for path, content in self.sources.items()):
            raise InvalidArtifactError("sources must map nonempty paths to text")
        if self.version is not None and (not isinstance(self.version, str) or not self.version):
            raise InvalidArtifactError("compiler version must be nonempty text")


@dataclass(frozen=True)
class ArtifactBundle:
    """Computed view of artifacts found by one provider."""

    source: SourceBundle | None = None
    creation_code: bytes | None = None
    runtime_code: bytes | None = None

    def __post_init__(self) -> None:
        if self.source is not None and not isinstance(self.source, SourceBundle):
            raise InvalidArtifactError("source must be a SourceBundle")
        for name in ("creation_code", "runtime_code"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, bytes) or not value):
                raise InvalidArtifactError(f"{name} must be nonempty bytes")

    def empty(self) -> bool:
        return self.source is None and self.creation_code is None and self.runtime_code is None


@dataclass(frozen=True)
class ArtifactOutcome:
    status: OutcomeStatus
    value: SourceBundle | bytes | None = None
    cached: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.cached, bool):
            raise InvalidArtifactError("outcome cached flag must be boolean")
        if self.status is OutcomeStatus.FOUND and self.value is None:
            raise InvalidArtifactError("found outcome needs an artifact value")
        if self.status is OutcomeStatus.ABSENT and self.value is not None:
            raise InvalidArtifactError("absent outcome cannot contain an artifact value")


@dataclass(frozen=True)
class ProviderObservation:
    provider: str
    location: ContractLocation
    outcomes: Mapping[ArtifactKind, ArtifactOutcome]
    provenance: Mapping[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or not self.provider:
            raise InvalidArtifactError("provider name must be nonempty")
        if not self.outcomes:
            raise InvalidArtifactError("provider observation needs outcomes")
        for kind, outcome in self.outcomes.items():
            if not isinstance(kind, ArtifactKind) or not isinstance(outcome, ArtifactOutcome):
                raise InvalidArtifactError("outcomes must map ArtifactKind to ArtifactOutcome")
            value = outcome.value
            if value is not None and kind is ArtifactKind.SOURCE and not isinstance(value, SourceBundle):
                raise InvalidArtifactError("source outcome needs a SourceBundle")
            if value is not None and kind is not ArtifactKind.SOURCE and (
                    not isinstance(value, bytes) or not value):
                raise InvalidArtifactError(f"{kind.value} outcome needs nonempty bytes")

    @property
    def artifacts(self) -> ArtifactBundle:
        def value(kind: ArtifactKind):
            outcome = self.outcomes.get(kind)
            return outcome.value if outcome is not None else None
        return ArtifactBundle(value(ArtifactKind.SOURCE), value(ArtifactKind.CREATION),
                              value(ArtifactKind.RUNTIME))

    @property
    def cached(self) -> bool:
        return bool(self.outcomes) and all(outcome.cached for outcome in self.outcomes.values())


@dataclass(frozen=True)
class ProviderFailure:
    provider: str
    category: FailureCategory
    detail: str
    retryable: bool
    origin: FailureOrigin
    failed_kind: ArtifactKind | None = None
    completed_kinds: tuple[ArtifactKind, ...] = ()
    http_status: int | None = None
    details: Mapping[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.provider or not self.detail:
            raise InvalidArtifactError("provider failure needs provider and detail")
        if self.http_status is not None and (
                isinstance(self.http_status, bool) or not isinstance(self.http_status, int)):
            raise InvalidArtifactError("HTTP status must be an integer")

    def as_dict(self) -> dict[str, JSONValue]:
        result: dict[str, JSONValue] = {
            "provider": self.provider, "category": self.category.value,
            "detail": self.detail, "retryable": self.retryable,
            "origin": self.origin.value,
            "completed_kinds": [kind.value for kind in self.completed_kinds],
        }
        if self.failed_kind is not None:
            result["failed_kind"] = self.failed_kind.value
        if self.http_status is not None:
            result["http_status"] = self.http_status
        if self.details:
            result["details"] = dict(self.details)
        return result


@dataclass(frozen=True)
class ArtifactCollection:
    location: ContractLocation
    requested_kinds: frozenset[ArtifactKind]
    observations: tuple[ProviderObservation, ...]
    failures: Mapping[str, ProviderFailure] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.requested_kinds:
            raise InvalidArtifactError("collection needs requested kinds")
        if not self.requested_kinds <= frozenset(ArtifactKind):
            raise InvalidArtifactError("requested kinds must be ArtifactKind values")
        names = [observation.provider for observation in self.observations]
        if len(names) != len(set(names)):
            raise InvalidArtifactError("collection contains duplicate provider observations")
        if set(names) & set(self.failures):
            raise InvalidArtifactError("provider cannot have both an observation and failure")
        for observation in self.observations:
            if observation.location != self.location:
                raise InvalidArtifactError("provider observation location mismatch")
            if set(observation.outcomes) != self.requested_kinds:
                raise InvalidArtifactError(
                    "provider outcomes must exactly match requested artifact kinds")
        for name, failure in self.failures.items():
            if name != failure.provider:
                raise InvalidArtifactError("provider failure key mismatch")
            if failure.failed_kind is not None and failure.failed_kind not in self.requested_kinds:
                raise InvalidArtifactError("failure refers to an unrequested artifact kind")
            if not set(failure.completed_kinds) <= self.requested_kinds:
                raise InvalidArtifactError("failure completed unrequested artifact kinds")
