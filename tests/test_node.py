from pathlib import Path

import pytest

from ethcode import ArtifactKind, ContractLocation, OutcomeStatus
from ethcode.errors import ProviderUnavailableError
from ethcode.providers import NodeProvider


LOCATION = ContractLocation("0x" + "12" * 20, 1)


def write(root: Path, kind: str, value: str) -> None:
    path = root / kind / "1" / f"{LOCATION.address}.hex"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="ascii")


def test_node_provider_reads_bytecode_and_has_no_source(tmp_path):
    write(tmp_path, "creation", "0x6000\n")
    write(tmp_path, "runtime", "60ab\n")

    observation = NodeProvider(tmp_path).fetch(LOCATION, frozenset(ArtifactKind))

    assert observation.outcomes[ArtifactKind.SOURCE].status is OutcomeStatus.ABSENT
    assert observation.outcomes[ArtifactKind.CREATION].value == b"\x60\x00"
    assert observation.outcomes[ArtifactKind.RUNTIME].value == b"\x60\xab"
    assert observation.cached
    assert observation.provenance == {
        "backend": "file-cache", "directory": str(tmp_path),
    }


def test_node_provider_reports_missing_bytecode_as_absent(tmp_path):
    observation = NodeProvider(tmp_path).fetch(
        LOCATION, {ArtifactKind.CREATION, ArtifactKind.RUNTIME},
    )
    assert all(outcome.status is OutcomeStatus.ABSENT
               for outcome in observation.outcomes.values())


def test_node_provider_rejects_corrupt_bytecode(tmp_path):
    write(tmp_path, "runtime", "not-hex")
    with pytest.raises(ProviderUnavailableError) as raised:
        NodeProvider(tmp_path).fetch(LOCATION, {ArtifactKind.RUNTIME})
    assert raised.value.category == "cache_corruption"
    assert raised.value.artifact_kind is ArtifactKind.RUNTIME
    assert raised.value.origin == "cache"
