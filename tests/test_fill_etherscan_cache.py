import json
from unittest.mock import patch

from ethcode import (ArtifactKind, ArtifactOutcome, ContractLocation,
                     OutcomeStatus, ProviderObservation)
from ethcode.errors import ProviderQuotaError, ProviderRateLimitError
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
        report = fill_cache([second, first, first], cache_dir=tmp_path, api_key="key",
                            event_log=tmp_path / "events.jsonl")

    factory.assert_called_once_with(
        tmp_path, "key", calls_per_second=3.0, timeout=30)
    assert report["requested"] == 2
    assert report["found"] == 1
    assert report["not_found"] == 0
    assert report["failed"] == 1
    assert report["contracts"][0]["cached"] is True
    assert report["contracts"][1]["error_type"] == "ProviderRateLimitError"
    assert report["complete"] is True
    events = [json.loads(line) for line in
              (tmp_path / "events.jsonl").read_text().splitlines()]
    assert [event["status"] for event in events] == ["found", "failed"]
    assert len({event["run_id"] for event in events}) == 1
    assert [event["index"] for event in events] == [1, 2]
    assert all(event["total"] == 2 for event in events)


def test_fill_cache_stops_after_quota_error_and_keeps_partial_report(tmp_path):
    locations = [
        ContractLocation("0x" + "12" * 20),
        ContractLocation("0x" + "34" * 20),
        ContractLocation("0x" + "56" * 20),
    ]

    with patch("ethcode.tools.fill_etherscan_cache.EtherscanProvider") as factory:
        factory.return_value.fetch.side_effect = [
            ProviderObservation("etherscan", locations[0], {
                ArtifactKind.RUNTIME: ArtifactOutcome(
                    OutcomeStatus.FOUND, b"\x00", cached=False),
            }),
            ProviderQuotaError("Etherscan", "daily limit"),
        ]
        report = fill_cache(locations, cache_dir=tmp_path, api_key="key")

    assert report["complete"] is False
    assert report["stop_reason"] == "provider_quota"
    assert report["found"] == 1
    assert report["failed"] == 1
    assert len(report["contracts"]) == 2
    assert factory.return_value.fetch.call_count == 2
def test_event_log_survives_interruption(tmp_path):
    locations = [
        ContractLocation("0x" + "12" * 20),
        ContractLocation("0x" + "34" * 20),
    ]
    observation = ProviderObservation("etherscan", locations[0], {
        ArtifactKind.RUNTIME: ArtifactOutcome(
            OutcomeStatus.FOUND, b"\x00", cached=False),
    })
    events = tmp_path / "events.jsonl"

    with patch("ethcode.tools.fill_etherscan_cache.EtherscanProvider") as factory:
        factory.return_value.fetch.side_effect = [observation, KeyboardInterrupt]
        try:
            fill_cache(locations, cache_dir=tmp_path, api_key="key", event_log=events)
        except KeyboardInterrupt:
            pass

    records = [json.loads(line) for line in events.read_text().splitlines()]
    assert len(records) == 1
    assert records[0]["address"] == locations[0].address
    assert records[0]["status"] == "found"
