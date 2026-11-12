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


def test_schedule_spaces_request_starts_not_response_completion(tmp_path):
    provider = EtherscanProvider(tmp_path, "key", calls_per_second=5)
    clock = [100.0, 100.0, 107.0]
    with patch("ethcode.providers.etherscan.time.time", side_effect=clock) as now:
        with provider._request_slot():
            pass

    state = json.loads((tmp_path / ".request-schedule.json").read_text())
    assert state == {"next_request": 100.2, "calls_per_second": 5.0}
    assert now.call_count == 2


def test_schedule_waits_until_the_next_allowed_start(tmp_path):
    (tmp_path / ".request-schedule.json").write_text(json.dumps({
        "next_request": 100.2,
        "calls_per_second": 5.0,
    }))
    provider = EtherscanProvider(tmp_path, "key", calls_per_second=5)
    with patch("ethcode.providers.etherscan.time.time",
               side_effect=[100.0, 100.2]), patch(
                   "ethcode.providers.etherscan.time.sleep") as sleep:
        with provider._request_slot():
            pass

    sleep.assert_called_once_with(pytest.approx(0.2))
    state = json.loads((tmp_path / ".request-schedule.json").read_text())
    assert state == {"next_request": 100.4, "calls_per_second": 5.0}
