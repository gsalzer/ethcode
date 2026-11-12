from ethcode import (
    ArtifactCollector, ArtifactKind, ArtifactOutcome, ContractLocation,
    FailureCategory, OutcomeStatus, ProviderObservation, SourceBundle,
)
from ethcode.errors import ProviderUnavailableError
from ethcode.errors import InvalidArtifactError
import pytest


LOCATION = ContractLocation("0x" + "12" * 20)


class Provider:
    def __init__(self, name, outcomes=None, error=None):
        self.name, self.outcomes, self.error = name, outcomes, error

    def fetch(self, location, kinds):
        if self.error:
            raise self.error
        outcomes = self.outcomes or {
            kind: ArtifactOutcome(OutcomeStatus.ABSENT) for kind in kinds}
        return ProviderObservation(self.name, location, outcomes)


def test_location_defaults_to_ethereum_mainnet():
    assert LOCATION.chain_id == 1
    assert ContractLocation(LOCATION.address, chain_id=11155111).chain_id == 11155111


def test_collection_preserves_provider_observations():
    source = SourceBundle("Solidity", {"C.sol": "contract C {}"})
    outcomes = {
        ArtifactKind.SOURCE: ArtifactOutcome(OutcomeStatus.FOUND, source),
        ArtifactKind.CREATION: ArtifactOutcome(OutcomeStatus.FOUND, b"\x60\x00"),
        ArtifactKind.RUNTIME: ArtifactOutcome(OutcomeStatus.FOUND, b"\x00"),
    }
    collection = ArtifactCollector([
        Provider("etherscan", outcomes), Provider("sourcify", outcomes),
    ]).collect(LOCATION)
    assert len(collection.observations) == 2
    assert collection.observations[0].artifacts.source == source
    assert not collection.failures


def test_operational_error_is_distinct_from_absence():
    error = ProviderUnavailableError(
        "offline", category="connection", artifact_kind=ArtifactKind.RUNTIME)
    collection = ArtifactCollector([
        Provider("failed", error=error), Provider("empty"),
    ]).collect(LOCATION)
    assert collection.failures["failed"].category is FailureCategory.CONNECTION
    assert collection.failures["failed"].failed_kind is ArtifactKind.RUNTIME
    assert len(collection.observations) == 1
    assert all(outcome.status is OutcomeStatus.ABSENT
               for outcome in collection.observations[0].outcomes.values())


def test_requested_kinds_reach_provider():
    provider = Provider("recording")
    original = provider.fetch

    def fetch(location, kinds):
        provider.kinds = kinds
        return original(location, kinds)

    provider.fetch = fetch
    collection = ArtifactCollector([provider]).collect(
        LOCATION, kinds={ArtifactKind.SOURCE})
    assert provider.kinds == frozenset({ArtifactKind.SOURCE})
    assert collection.requested_kinds == frozenset({ArtifactKind.SOURCE})


def test_collector_accepts_at_most_two_providers():
    try:
        ArtifactCollector([Provider("a"), Provider("b"), Provider("c")])
    except ValueError as exc:
        assert "one or two" in str(exc)
    else:
        raise AssertionError("expected provider-count error")


def test_collection_requires_complete_exact_outcomes():
    source_only = ProviderObservation("one", LOCATION, {
        ArtifactKind.SOURCE: ArtifactOutcome(OutcomeStatus.ABSENT)})
    with pytest.raises(InvalidArtifactError, match="exactly match"):
        from ethcode import ArtifactCollection
        ArtifactCollection(
            LOCATION,
            frozenset({ArtifactKind.SOURCE, ArtifactKind.RUNTIME}),
            (source_only,),
        )

    with pytest.raises(InvalidArtifactError, match="exactly match"):
        from ethcode import ArtifactCollection
        ArtifactCollection(
            LOCATION,
            frozenset({ArtifactKind.RUNTIME}),
            (source_only,),
        )


def test_provider_error_rejects_invalid_structured_values_immediately():
    with pytest.raises(ValueError, match="category"):
        ProviderUnavailableError("broken", category="typo")
    with pytest.raises(ValueError, match="origin"):
        ProviderUnavailableError("broken", origin="somewhere")
