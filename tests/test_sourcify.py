import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ethcode import ArtifactKind, ContractLocation
from ethcode.errors import ProviderUnavailableError
from ethcode.providers import SourcifyProvider


LOCATION = ContractLocation("0x" + "12" * 20)


def sourcify_record():
    return {
        "chainId": "1", "address": LOCATION.address,
        "match": "exact_match", "creationMatch": None,
        "runtimeMatch": "exact_match",
        "sources": {"C.sol": {"content": "contract C {}"}},
        "compilation": {"language": "Solidity", "compilerVersion": "0.8.20",
                        "compilerSettings": {}},
        "creationBytecode": {"onchainBytecode": None},
        "runtimeBytecode": {"onchainBytecode": "0x00"},
    }


class Response:
    status = 200
    headers = {}

    def __init__(self, value):
        self.payload = json.dumps(value).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


def test_email_from_environment_and_selective_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCIFY_EMAIL", "research@example.org")
    provider = SourcifyProvider(tmp_path, interval=0)
    record = {
        "chainId": "1", "address": LOCATION.address,
        "match": "exact_match", "creationMatch": "exact_match",
        "runtimeMatch": "exact_match",
        "sources": {"C.sol": {"content": "contract C {}"}},
        "compilation": {"language": "Solidity", "compilerVersion": "0.8.20",
                        "compilerSettings": {}},
        "creationBytecode": {"onchainBytecode": "0x6000"},
        "runtimeBytecode": {"onchainBytecode": "0x00"},
    }
    with patch("urllib.request.urlopen", return_value=Response(record)) as request:
        result = provider.fetch(LOCATION, set(ArtifactKind))
    url = request.call_args.args[0].full_url
    assert "fields=all" not in url
    assert "sources%2Ccompilation.language" in url
    assert "research@example.org" in request.call_args.args[0].headers["User-agent"]
    assert result.artifacts.runtime_code == b"\x00"


def test_cache_read_does_not_require_email(tmp_path):
    with patch.dict("os.environ", {}, clear=True):
        writer = SourcifyProvider(tmp_path, email="research@example.org", interval=0)
        writer.cache.write("contract", LOCATION.chain_id, LOCATION.address, {
            "http_status": 404,
            "response": {"chainId": "1", "address": LOCATION.address,
                         "match": None, "creationMatch": None, "runtimeMatch": None},
            "backend": "fixture",
        })
        reader = SourcifyProvider(tmp_path, interval=0)
        assert reader.fetch(LOCATION, set(ArtifactKind)).cached


def test_cache_miss_requires_contact_email(tmp_path):
    with patch.dict("os.environ", {}, clear=True):
        provider = SourcifyProvider(tmp_path)
        with pytest.raises(ProviderUnavailableError, match="SOURCIFY_EMAIL"):
            provider.fetch(LOCATION, set(ArtifactKind))


def test_store_response_validates_and_preserves_existing_entry(tmp_path):
    provider = SourcifyProvider(tmp_path, email="")
    assert not provider.response_cached(LOCATION)
    assert provider.store_response(
        LOCATION, sourcify_record(), provenance={"backend": "dataset"})
    assert provider.response_cached(LOCATION)
    assert not provider.store_response(LOCATION, sourcify_record())

    result = provider.fetch(LOCATION, set(ArtifactKind))
    assert result.cached
    assert result.artifacts.creation_code is None
    assert result.artifacts.runtime_code == b"\x00"
    assert result.provenance["backend"] == "dataset"
