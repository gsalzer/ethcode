import json
from unittest.mock import patch

import pytest

from ethcode import ArtifactKind, ContractLocation
from ethcode.errors import (ProviderQuotaError, ProviderRateLimitError,
                            ProviderUnavailableError)
from ethcode.providers import EtherscanProvider


LOCATION = ContractLocation("0x" + "12" * 20)


def test_default_and_configured_rates(tmp_path):
    assert EtherscanProvider(tmp_path, "key").calls_per_second == 3
    assert EtherscanProvider(tmp_path, "key", calls_per_second=10).request_interval == .1
    with pytest.raises(ValueError):
        EtherscanProvider(tmp_path, "key", calls_per_second=0)


@pytest.mark.parametrize(("detail", "error_type"), (
    ("Max rate limit reached, please use API Key for higher rate limit",
     ProviderRateLimitError),
    ("Community Free API limit reached. Resets tomorrow", ProviderQuotaError),
    ("Daily limit reached", ProviderQuotaError),
))
def test_limit_envelopes_are_typed_and_not_cached(tmp_path, detail, error_type):
    provider = EtherscanProvider(tmp_path, "key", calls_per_second=1000)
    envelope = {"status": "0", "message": "NOTOK", "result": detail}
    with patch.object(provider, "_json_request", return_value=(200, envelope)):
        with pytest.raises(error_type) as raised:
            provider.fetch(LOCATION, {ArtifactKind.SOURCE})
    assert raised.value.detail == detail
    assert provider.cache.read("source", LOCATION.chain_id, LOCATION.address) is None


def test_http_429_is_rate_limit(tmp_path):
    provider = EtherscanProvider(tmp_path, "key")
    with patch.object(provider, "_json_request", return_value=(429, {})):
        with pytest.raises(ProviderRateLimitError):
            provider._query(LOCATION, module="proxy", action="eth_getCode")


def test_processes_must_use_same_rate_for_shared_cache(tmp_path):
    path = tmp_path / ".request-schedule.json"
    path.write_text(json.dumps({"next_request": 0, "calls_per_second": 3}))
    provider = EtherscanProvider(tmp_path, "key", calls_per_second=10)
    with pytest.raises(ProviderUnavailableError, match="differs"):
        with provider._request_slot():
            pass
