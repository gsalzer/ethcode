from ethcode import (
    ArtifactBundle, ArtifactConflictError, ArtifactKind, ArtifactRetriever,
    ContractLocation, ObservationStatus, ProviderObservation, SourceBundle,
)
from ethcode.errors import ProviderUnavailableError


LOCATION = ContractLocation("0x" + "12" * 20)


def test_location_defaults_to_ethereum_mainnet():
    assert LOCATION.chain_id == 1
    assert ContractLocation(LOCATION.address, chain_id=11155111).chain_id == 11155111


class Provider:
    def __init__(self, name, bundle=None, error=None):
        self.name, self.bundle, self.error = name, bundle or ArtifactBundle(), error

    def fetch(self, location, kinds):
        if self.error:
            raise ProviderUnavailableError(self.error)
        return ProviderObservation(self.name, location, ObservationStatus.FOUND,
                                   self.bundle)


def test_retrieval_reconciles_and_preserves_observations():
    bundle = ArtifactBundle(SourceBundle("Solidity", {"C.sol": "contract C {}"}),
                            b"\x60\x00", b"\x00")
    result = ArtifactRetriever([Provider("etherscan", bundle),
                                Provider("sourcify", bundle)]).retrieve(LOCATION)
    assert result.artifacts == bundle
    assert result.reconciliation.contributors["runtime"] == ("etherscan", "sourcify")
    assert len(result.observations) == 2


def test_operational_error_is_distinct_from_absence():
    result = ArtifactRetriever([Provider("failed", error="offline"),
                                Provider("empty")]).retrieve(LOCATION)
    assert result.artifacts.empty()
    assert result.errors == {"failed": "offline"}
    assert len(result.observations) == 1


def test_bytecode_disagreement_is_an_error():
    retriever = ArtifactRetriever([
        Provider("one", ArtifactBundle(runtime_code=b"\x00")),
        Provider("two", ArtifactBundle(runtime_code=b"\x01")),
    ])
    try:
        retriever.retrieve(LOCATION)
    except ArtifactConflictError as exc:
        assert "runtime" in str(exc)
    else:
        raise AssertionError("expected conflict")


def test_requested_kinds_reach_provider():
    class Recording(Provider):
        def fetch(self, location, kinds):
            self.kinds = kinds
            return super().fetch(location, kinds)
    provider = Recording("recording")
    ArtifactRetriever([provider]).retrieve(LOCATION, kinds={ArtifactKind.SOURCE})
    assert provider.kinds == frozenset({ArtifactKind.SOURCE})

