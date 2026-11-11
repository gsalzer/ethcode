"""Address-list input shared by cache-filling commands."""

from __future__ import annotations

import csv
from pathlib import Path

from ..models import ContractLocation


def read_addresses(path: Path) -> list[ContractLocation]:
    """Read and deduplicate locations from a CSV with chain,address columns."""
    with Path(path).open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if not {"chain", "address"}.issubset(reader.fieldnames or []):
            raise ValueError("address CSV needs chain,address columns")
        locations = {
            ContractLocation(row["address"].strip(), chain_id=int(row["chain"].strip()))
            for row in reader
        }
    return sorted(locations, key=lambda item: (item.chain_id, item.address))
