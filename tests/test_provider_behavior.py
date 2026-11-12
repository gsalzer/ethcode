import json
import socket
import ssl
import urllib.error

import pytest
from unittest.mock import patch

from ethcode import (
    ArtifactCollector, ArtifactKind, ContractLocation, FailureCategory,
    OutcomeStatus,
)
from ethcode.errors import ProviderUnavailableError
from ethcode.errors import InvalidArtifactError
from ethcode.providers import EtherscanProvider
from ethcode.providers.base import transport_error


LOCATION = ContractLocation("0x" + "12" * 20)


def source_envelope():
    return {"status": "1", "message": "OK", "result": [{
        "SourceCode": "contract C {}",
        "ContractName": "C",
        "ContractFileName": "src/C.sol",
        "CompilerVersion": "v0.8.20",
        "CompilerType": "solc",
        "OptimizationUsed": "1",
        "Runs": "200",
        "EVMVersion": "paris",
    }]}


def creation_envelope():
    return {"status": "1", "message": "OK", "result": [{
        "contractAddress": LOCATION.address,
        "creationBytecode": "0x6000",
    }]}


def test_etherscan_failure_returns_no_observation_and_keeps_completed_caches(tmp_path):
    provider = EtherscanProvider(tmp_path, "key", calls_per_second=1000)
    failure = ProviderUnavailableError(
        "timeout", category="timeout", retryable=True, origin="request")
    with patch.object(provider, "_json_request", side_effect=[
            (200, source_envelope()), (200, creation_envelope()), failure]):
        collection = ArtifactCollector([provider]).collect(LOCATION)

    assert not collection.observations
    recorded = collection.failures["etherscan"]
    assert recorded.failed_kind is ArtifactKind.RUNTIME
    assert recorded.completed_kinds == (ArtifactKind.SOURCE, ArtifactKind.CREATION)
    assert provider.cache.read("source", 1, LOCATION.address) is not None
    assert provider.cache.read("creation", 1, LOCATION.address) is not None
    assert provider.cache.read("runtime", 1, LOCATION.address) is None

    with patch.object(provider, "_json_request", return_value=(200, {"result": "0x00"})) as request:
        retried = ArtifactCollector([provider]).collect(LOCATION)
    assert request.call_count == 1
    assert retried.observations[0].outcomes[ArtifactKind.SOURCE].cached
    assert retried.observations[0].outcomes[ArtifactKind.CREATION].cached
    assert not retried.observations[0].outcomes[ArtifactKind.RUNTIME].cached


def test_corrupt_later_endpoint_cache_retains_completed_context(tmp_path):
    provider = EtherscanProvider(tmp_path, "key", calls_per_second=1000)
    provider.cache.write("source", 1, LOCATION.address, {
        "classification": "found", "response": source_envelope()})
    provider.cache.write("creation", 1, LOCATION.address, {
        "classification": "wrong", "response": creation_envelope()})
    collection = ArtifactCollector([provider]).collect(LOCATION)
    failure = collection.failures["etherscan"]
    assert failure.category is FailureCategory.CACHE_CORRUPTION
    assert failure.failed_kind is ArtifactKind.CREATION
    assert failure.completed_kinds == (ArtifactKind.SOURCE,)


def test_plain_etherscan_source_preserves_settings_and_metadata(tmp_path):
    provider = EtherscanProvider(tmp_path, "key", calls_per_second=1000)
    with patch.object(provider, "_json_request", return_value=(200, source_envelope())):
        observation = provider.fetch(LOCATION, {ArtifactKind.SOURCE})
    outcome = observation.outcomes[ArtifactKind.SOURCE]
    assert outcome.status is OutcomeStatus.FOUND
    assert outcome.value.sources == {"src/C.sol": "contract C {}"}
    assert outcome.value.settings == {
        "optimizer": {"enabled": True, "runs": 200}, "evmVersion": "paris"}
    assert observation.provenance["source_metadata"]["ContractName"] == "C"


@pytest.mark.parametrize(("source_code", "expected"), (
    (json.dumps({"language": "Solidity", "sources": {
        "A.sol": {"content": "contract A {}"},
        "B.sol": {"content": "contract B {}"},
    }, "settings": {"optimizer": {"enabled": False}}}),
     {"A.sol": "contract A {}", "B.sol": "contract B {}"}),
    (json.dumps({
        "A.sol": {"content": "contract A {}"},
        "B.sol": "contract B {}",
    }), {"A.sol": "contract A {}", "B.sol": "contract B {}"}),
    ('{{"language":"Solidity","sources":{"A.sol":{"content":"contract A {}"}}}}',
     {"A.sol": "contract A {}"}),
))
def test_etherscan_accepts_standard_and_direct_source_maps(source_code, expected):
    bundle = EtherscanProvider._source({
        "SourceCode": source_code, "CompilerVersion": "v0.8.20"})
    assert bundle.sources == expected


@pytest.mark.parametrize("source_code", (
    "{not-json", "{}", '{"": "contract A {}"}',
    '{"A.sol": {}}', '{"A.sol": {"content": 3}}',
    '{"A.sol": {"content": ""}}',
))
def test_etherscan_rejects_malformed_source_maps(source_code):
    with pytest.raises(InvalidArtifactError, match="SourceCode JSON"):
        EtherscanProvider._source({"SourceCode": source_code})


def test_explicit_tls_context_reaches_urlopen(tmp_path):
    context = ssl.create_default_context()
    provider = EtherscanProvider(tmp_path, "key", ssl_context=context)

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"result": "0x00"}).encode()

    with patch("urllib.request.urlopen", return_value=Response()) as request:
        provider._json_request("https://example.invalid", headers={})
    assert request.call_args.kwargs["context"] is context


def test_transport_failures_have_safe_distinct_categories():
    dns = transport_error("etherscan", urllib.error.URLError(
        socket.gaierror(-2, "host not found")))
    tls = transport_error("sourcify", urllib.error.URLError(
        ssl.SSLError("certificate verify failed")))
    timeout = transport_error("etherscan", urllib.error.URLError(
        TimeoutError("timed out")))
    assert (dns.category, tls.category, timeout.category) == ("dns", "tls", "timeout")
    assert all("http" not in error.detail.casefold()
               for error in (dns, tls, timeout))


def test_transport_failure_does_not_render_request_url_or_api_key(tmp_path):
    provider = EtherscanProvider(tmp_path, "secret-api-key")
    request_url = "https://api.etherscan.io/v2/api?apikey=secret-api-key"
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError(
            request_url)):
        with pytest.raises(ProviderUnavailableError) as raised:
            provider._json_request(request_url, headers={})
    rendered = str(raised.value)
    assert "secret-api-key" not in rendered
    assert request_url not in rendered


def test_corrupt_cache_is_a_provider_failure_and_other_provider_continues(tmp_path):
    broken = EtherscanProvider(tmp_path / "broken", api_key="")
    path = broken.cache._path("source", 1, LOCATION.address)
    path.parent.mkdir(parents=True)
    path.write_text("not-json")

    class EmptyProvider:
        name = "empty"

        def fetch(self, location, kinds):
            from ethcode import ArtifactOutcome, ProviderObservation
            return ProviderObservation(self.name, location, {
                kind: ArtifactOutcome(OutcomeStatus.ABSENT) for kind in kinds})

    collection = ArtifactCollector([broken, EmptyProvider()]).collect(
        LOCATION, kinds={ArtifactKind.SOURCE})
    assert collection.failures["etherscan"].category is FailureCategory.CACHE_CORRUPTION
    assert collection.observations[0].provider == "empty"
    assert path.read_text() == "not-json"


def test_missing_credentials_report_cached_and_first_unresolved_kinds(tmp_path):
    provider = EtherscanProvider(tmp_path, api_key="")
    provider.cache.write("source", 1, LOCATION.address, {
        "classification": "found", "response": source_envelope()})
    collection = ArtifactCollector([provider]).collect(LOCATION)
    failure = collection.failures["etherscan"]
    assert failure.category is FailureCategory.CREDENTIALS_MISSING
    assert failure.completed_kinds == (ArtifactKind.SOURCE,)
    assert failure.failed_kind is ArtifactKind.CREATION
