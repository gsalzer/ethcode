from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Mapping, TypeAlias

from .errors import InvalidArtifactError

JSONValue: TypeAlias = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")


class ArtifactKind(str, Enum):
    SOURCE = "source"
    CREATION = "creation"
    RUNTIME = "runtime"


class ObservationStatus(str, Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"


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
    source: SourceBundle | None = None
    creation_code: bytes | None = None
    runtime_code: bytes | None = None

    def __post_init__(self) -> None:
        for name in ("creation_code", "runtime_code"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, bytes) or not value):
                raise InvalidArtifactError(f"{name} must be nonempty bytes")

    def empty(self) -> bool:
        return self.source is None and self.creation_code is None and self.runtime_code is None


@dataclass(frozen=True)
class ProviderObservation:
    provider: str
    location: ContractLocation
    status: ObservationStatus
    artifacts: ArtifactBundle = field(default_factory=ArtifactBundle)
    provenance: Mapping[str, JSONValue] = field(default_factory=dict)
    cached: bool = False

    def __post_init__(self) -> None:
        if not self.provider:
            raise InvalidArtifactError("provider name must be nonempty")
        if self.status is ObservationStatus.NOT_FOUND and not self.artifacts.empty():
            raise InvalidArtifactError("not_found observation cannot contain artifacts")


@dataclass(frozen=True)
class ReconciliationReport:
    contributors: Mapping[str, tuple[str, ...]]
    source_relation: str | None = None
    selected_source_provider: str | None = None


@dataclass(frozen=True)
class RetrievalResult:
    location: ContractLocation
    artifacts: ArtifactBundle
    observations: tuple[ProviderObservation, ...]
    reconciliation: ReconciliationReport
    errors: Mapping[str, str] = field(default_factory=dict)

