"""Populate the Etherscan response cache for a list of contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Iterable

from ..cache import DEFAULT_CACHE_ROOT
from ..errors import ArtifactError, ProviderError
from ..models import ArtifactKind, ContractLocation, ObservationStatus
from ..providers import EtherscanProvider
from .addresses import read_addresses


def fill_cache(addresses: Iterable[ContractLocation], *,
               cache_dir: Path = DEFAULT_CACHE_ROOT / "etherscan",
               api_key: str | None = None,
               calls_per_second: float = 3.0,
               timeout: float = 30) -> dict:
    """Retrieve every artifact kind for each location and return a report."""
    provider = EtherscanProvider(
        cache_dir,
        api_key,
        calls_per_second=calls_per_second,
        timeout=timeout,
    )
    locations = sorted(set(addresses), key=lambda item: (item.chain_id, item.address))
    report = {
        "requested": len(locations),
        "found": 0,
        "not_found": 0,
        "failed": 0,
        "contracts": [],
    }
    for index, location in enumerate(locations, 1):
        print(
            f"[{index}/{len(locations)}] {location.chain_id}:{location.address}",
            file=sys.stderr,
        )
        item = {"chain": location.chain_id, "address": location.address}
        try:
            observation = provider.fetch(location, set(ArtifactKind))
        except ProviderError as exc:
            report["failed"] += 1
            item.update({
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
        else:
            status = ("not_found" if observation.status is ObservationStatus.NOT_FOUND
                      else "found")
            report[status] += 1
            item.update({
                "status": status,
                "cached": observation.cached,
                "endpoints": observation.provenance.get("endpoints", {}),
            })
        report["contracts"].append(item)
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("addresses", type=Path, help="CSV with chain,address columns")
    parser.add_argument("--cache-dir", type=Path,
                        default=DEFAULT_CACHE_ROOT / "etherscan")
    parser.add_argument("--api-key",
                        help="Etherscan API key; defaults to ETHERSCAN_API_KEY")
    parser.add_argument("--calls-per-second", type=float, default=3.0,
                        help="shared Etherscan request rate (default: 3)")
    parser.add_argument("--timeout", type=float, default=30,
                        help="HTTP timeout in seconds (default: 30)")
    parser.add_argument("--report", type=Path,
                        help="write the JSON report to this file instead of stdout")
    args = parser.parse_args(argv)
    try:
        report = fill_cache(
            read_addresses(args.addresses),
            cache_dir=args.cache_dir,
            api_key=args.api_key,
            calls_per_second=args.calls_per_second,
            timeout=args.timeout,
        )
        rendered = json.dumps(report, indent=2) + "\n"
        if args.report is None:
            print(rendered, end="")
        else:
            args.report.write_text(rendered, encoding="utf-8")
    except (ArtifactError, OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
