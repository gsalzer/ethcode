from __future__ import annotations

from collections.abc import Collection
from typing import Protocol

from .models import ArtifactKind, ContractLocation, ProviderObservation


class ArtifactProvider(Protocol):
    name: str

    def fetch(self, location: ContractLocation,
              kinds: Collection[ArtifactKind]) -> ProviderObservation: ...

