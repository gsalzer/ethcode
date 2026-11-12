from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .models import (ArtifactCollection, ArtifactKind, ContractLocation,
                     OutcomeStatus, SourceBundle)


@dataclass(frozen=True)
class BytecodeComparison:
    providers: tuple[str, ...]
    relation: str  # equal, different, or unavailable


@dataclass(frozen=True)
class SourceComparison:
    providers: tuple[str, ...]
    content_relation: str
    language_relation: str
    version_relation: str
    settings_relation: str
    shared_settings: tuple[str, ...] = ()
    complementary_settings: tuple[str, ...] = ()
    conflicting_settings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComparisonAnalysis:
    location: ContractLocation
    requested_kinds: frozenset[ArtifactKind]
    source: SourceComparison | None = None
    creation: BytecodeComparison | None = None
    runtime: BytecodeComparison | None = None


def _line_endings(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return value[:-1] if value.endswith("\n") else value


def _tokens(value: str) -> tuple[str, ...]:
    result: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char.isspace():
            index += 1
        elif value.startswith("//", index):
            end = value.find("\n", index + 2)
            index = len(value) if end < 0 else end + 1
        elif value.startswith("/*", index):
            end = value.find("*/", index + 2)
            if end < 0:
                result.append(value[index:])
                break
            index = end + 2
        elif char in "\"'":
            start, quote = index, char
            index += 1
            while index < len(value):
                if value[index] == "\\":
                    index += 2
                elif value[index] == quote:
                    index += 1
                    break
                else:
                    index += 1
            result.append(value[start:index])
        elif char.isalnum() or char in "_$":
            start = index
            index += 1
            while index < len(value) and (value[index].isalnum() or value[index] in "_$"):
                index += 1
            result.append(value[start:index])
        else:
            result.append(char)
            index += 1
    return tuple(result)


def _content_relation(left: SourceBundle, right: SourceBundle) -> str:
    if left.sources == right.sources:
        return "exact"
    left_paths = {path: _line_endings(text) for path, text in left.sources.items()}
    right_paths = {path: _line_endings(text) for path, text in right.sources.items()}
    if left_paths == right_paths:
        return "line_endings"
    if Counter(left_paths.values()) == Counter(right_paths.values()):
        return "path_insensitive"
    if Counter(_tokens(text) for text in left.sources.values()) == Counter(
            _tokens(text) for text in right.sources.values()):
        return "lexical"
    return "conflict"


def _language(value: str) -> str:
    normalized = value.strip().casefold()
    return {"solidity": "solidity", "vyper": "vyper", "yul": "yul"}.get(
        normalized, normalized)


def _version(value: str | None) -> str | None:
    return value.strip().removeprefix("v").casefold() if value is not None else None


def _scalar_relation(left, right, normalize=lambda value: value) -> str:
    if left is None or right is None:
        return "equal" if left is right else "unavailable"
    return "equal" if normalize(left) == normalize(right) else "different"


def _settings(left: Any, right: Any, path: str = "") -> tuple[list[str], list[str], list[str]]:
    shared: list[str] = []
    complementary: list[str] = []
    conflicts: list[str] = []
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(left.keys() | right.keys()):
            child = f"{path}.{key}" if path else str(key)
            if key not in left or key not in right:
                complementary.extend(_leaf_paths(
                    right[key] if key not in left else left[key], child))
            else:
                same, extra, conflict = _settings(left[key], right[key], child)
                shared.extend(same)
                complementary.extend(extra)
                conflicts.extend(conflict)
    elif type(left) is type(right) and left == right:
        shared.append(path or "$")
    else:
        conflicts.append(path or "$")
    return shared, complementary, conflicts


def _leaf_paths(value: Any, path: str) -> list[str]:
    if isinstance(value, dict) and value:
        return [leaf for key in sorted(value)
                for leaf in _leaf_paths(value[key], f"{path}.{key}")]
    return [path]


def _source(collection: ArtifactCollection) -> SourceComparison:
    supplied = []
    for observation in sorted(collection.observations, key=lambda item: item.provider):
        outcome = observation.outcomes.get(ArtifactKind.SOURCE)
        if outcome is not None and outcome.status is OutcomeStatus.FOUND:
            supplied.append((observation.provider, outcome.value))
    providers = tuple(name for name, _ in supplied)
    if len(supplied) != 2:
        return SourceComparison(providers, "unavailable", "unavailable", "unavailable",
                                "unavailable")
    left, right = supplied[0][1], supplied[1][1]
    assert isinstance(left, SourceBundle) and isinstance(right, SourceBundle)
    shared, complementary, conflicts = _settings(left.settings or {}, right.settings or {})
    settings_relation = ("conflict" if conflicts else
                         "complementary" if complementary else "exact")
    return SourceComparison(
        providers,
        _content_relation(left, right),
        _scalar_relation(left.language, right.language, _language),
        _scalar_relation(left.version, right.version, _version),
        settings_relation,
        tuple(shared), tuple(complementary), tuple(conflicts),
    )


def _bytecode(collection: ArtifactCollection, kind: ArtifactKind) -> BytecodeComparison:
    supplied = []
    for observation in sorted(collection.observations, key=lambda item: item.provider):
        outcome = observation.outcomes.get(kind)
        if outcome is not None and outcome.status is OutcomeStatus.FOUND:
            supplied.append((observation.provider, outcome.value))
    providers = tuple(name for name, _ in supplied)
    if len(supplied) != 2:
        return BytecodeComparison(providers, "unavailable")
    return BytecodeComparison(
        providers, "equal" if supplied[0][1] == supplied[1][1] else "different")


def compare(collection: ArtifactCollection) -> ComparisonAnalysis:
    """Describe relations between at most two provider observations."""
    if len(collection.observations) > 2:
        raise ValueError("comparison supports at most two provider observations")
    return ComparisonAnalysis(
        collection.location,
        collection.requested_kinds,
        _source(collection) if ArtifactKind.SOURCE in collection.requested_kinds else None,
        _bytecode(collection, ArtifactKind.CREATION)
        if ArtifactKind.CREATION in collection.requested_kinds else None,
        _bytecode(collection, ArtifactKind.RUNTIME)
        if ArtifactKind.RUNTIME in collection.requested_kinds else None,
    )
