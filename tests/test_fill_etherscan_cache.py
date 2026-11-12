from unittest.mock import patch

from ethcode import (ArtifactKind, ArtifactOutcome, ContractLocation,
                     OutcomeStatus, ProviderObservation)
from ethcode.errors import ProviderRateLimitError
from ethcode.tools.fill_etherscan_cache import fill_cache


def test_fill_cache_reports_results_and_continues_after_errors(tmp_path):
    first = ContractLocation("0x" + "12" * 20)
    second = ContractLocation("0x" + "34" * 20, chain_id=5)

    def fetch(location, kinds):
        if location == second:
            raise ProviderRateLimitError("Etherscan", "rate exceeded")
        return ProviderObservation(
            "etherscan",
            location,
            {ArtifactKind.RUNTIME: ArtifactOutcome(
                OutcomeStatus.FOUND, b"\x00", cached=True)},
        )

    with patch("ethcode.tools.fill_etherscan_cache.EtherscanProvider") as factory:
        factory.return_value.fetch.side_effect = fetch
        report = fill_cache([second, first, first], cache_dir=tmp_path, api_key="key")

    factory.assert_called_once_with(
        tmp_path, "key", calls_per_second=3.0, timeout=30)
    assert report["requested"] == 2
    assert report["found"] == 1
    assert report["not_found"] == 0
    assert report["failed"] == 1
    assert report["contracts"][0]["cached"] is True
    assert report["contracts"][1]["error_type"] == "ProviderRateLimitError"
