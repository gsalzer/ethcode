from __future__ import annotations

from collections.abc import Collection, Iterable

from .errors import CacheError, ProviderError
from .models import (ArtifactCollection, ArtifactKind, ContractLocation,
                     FailureCategory, FailureOrigin, ProviderFailure,
                     ProviderObservation)
from .protocols import ArtifactProvider


class ArtifactCollector:
    """Collect normalized observations from one or more providers."""

    def __init__(self, providers: Iterable[ArtifactProvider]) -> None:
        self.providers = tuple(providers)
        if not self.providers:
            raise ValueError("ArtifactCollector requires at least one provider")
        names = [provider.name for provider in self.providers]
        if len(names) != len(set(names)):
            raise ValueError("provider names must be unique")

    def collect(self, location: ContractLocation, *,
                kinds: Collection[ArtifactKind] = tuple(ArtifactKind)) -> ArtifactCollection:
        requested = frozenset(kinds)
        if not requested or not requested <= frozenset(ArtifactKind):
            raise ValueError("kinds must contain ArtifactKind values")
        observations: list[ProviderObservation] = []
        failures: dict[str, ProviderFailure] = {}
        for provider in self.providers:
            try:
                observation = provider.fetch(location, requested)
            except ProviderError as exc:
                failures[provider.name] = ProviderFailure(
                    provider.name, FailureCategory(exc.category), exc.detail,
                    exc.retryable, FailureOrigin(exc.origin), exc.artifact_kind,
                    exc.completed_kinds, exc.http_status, exc.details)
                continue
            except CacheError as exc:
                failures[provider.name] = ProviderFailure(
                    provider.name, FailureCategory.CACHE_CORRUPTION, str(exc), False,
                    FailureOrigin.CACHE)
                continue
            if observation.provider != provider.name or observation.location != location:
                raise ValueError(f"provider {provider.name!r} returned a mismatched observation")
            if set(observation.outcomes) != requested:
                raise ValueError(f"provider {provider.name!r} did not return every requested outcome")
            observations.append(observation)
        return ArtifactCollection(location, requested, tuple(observations), failures)
