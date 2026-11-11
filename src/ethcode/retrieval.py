from __future__ import annotations

from collections.abc import Collection, Iterable

from .errors import ProviderError
from .models import (ArtifactKind, ContractLocation, RetrievalResult,
                     ProviderObservation)
from .protocols import ArtifactProvider
from .reconciliation import ReconciliationPolicy


class ArtifactRetriever:
    def __init__(self, providers: Iterable[ArtifactProvider], *,
                 policy: ReconciliationPolicy | None = None) -> None:
        self.providers = tuple(providers)
        if not self.providers:
            raise ValueError("at least one provider is required")
        names = [provider.name for provider in self.providers]
        if len(names) != len(set(names)):
            raise ValueError("provider names must be unique")
        self.policy = policy or ReconciliationPolicy()

    def retrieve(self, location: ContractLocation, *,
                 kinds: Collection[ArtifactKind] = tuple(ArtifactKind)) -> RetrievalResult:
        requested = frozenset(kinds)
        if not requested or not requested <= frozenset(ArtifactKind):
            raise ValueError("kinds must contain ArtifactKind values")
        observations: list[ProviderObservation] = []
        errors: dict[str, str] = {}
        for provider in self.providers:
            try:
                observation = provider.fetch(location, requested)
            except ProviderError as exc:
                errors[provider.name] = str(exc)
                continue
            if observation.provider != provider.name or observation.location != location:
                raise ValueError(f"provider {provider.name!r} returned a mismatched observation")
            observations.append(observation)
        artifacts, report = self.policy.reconcile(tuple(observations))
        return RetrievalResult(location, artifacts, tuple(observations), report, errors)

