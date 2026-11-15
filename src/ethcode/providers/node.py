from __future__ import annotations

from pathlib import Path

from ..codec import decode_hex
from ..errors import InvalidArtifactError, ProviderUnavailableError
from ..models import (ArtifactKind, ArtifactOutcome, ContractLocation,
                      OutcomeStatus, ProviderObservation)


class NodeProvider:
    """Read externally obtained creation/runtime bytecode from a file cache."""

    name = "node"

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = Path(cache_dir)

    def _path(self, location: ContractLocation, kind: ArtifactKind) -> Path:
        return (self.cache_dir / kind.value / str(location.chain_id)
                / f"{location.address}.hex")

    def _bytecode(self, location: ContractLocation,
                  kind: ArtifactKind) -> bytes | None:
        path = self._path(location, kind)
        if not path.exists():
            return None
        try:
            text = path.read_text(encoding="ascii").strip()
            return decode_hex(text, field=f"node {kind.value} code")
        except (OSError, UnicodeError, InvalidArtifactError) as exc:
            raise ProviderUnavailableError(
                f"invalid node {kind.value} cache entry: {exc}",
                provider=self.name, category="cache_corruption",
                artifact_kind=kind, retryable=False, origin="cache",
                details={"path": str(path)},
            ) from exc

    def fetch(self, location: ContractLocation, kinds) -> ProviderObservation:
        outcomes = {}
        for kind in ArtifactKind:
            if kind not in kinds:
                continue
            value = None if kind is ArtifactKind.SOURCE else self._bytecode(location, kind)
            outcomes[kind] = ArtifactOutcome(
                OutcomeStatus.FOUND if value is not None else OutcomeStatus.ABSENT,
                value, cached=True,
            )
        return ProviderObservation(
            self.name, location, outcomes,
            {"backend": "file-cache", "directory": str(self.cache_dir)},
        )
