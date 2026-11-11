from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Callable

from .errors import ArtifactConflictError
from .models import ArtifactBundle, ProviderObservation, ReconciliationReport, SourceBundle


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


def source_relation(left: SourceBundle, right: SourceBundle) -> str:
    if left == right:
        return "exact"
    if (left.language.casefold(), left.version, left.settings) != (
            right.language.casefold(), right.version, right.settings):
        return "conflict"
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


@dataclass(frozen=True)
class ReconciliationPolicy:
    """Strict bytecode agreement with configurable equivalent-source selection."""

    preferred_source_providers: tuple[str, ...] = ("sourcify", "etherscan")
    source_selector: Callable[[tuple[tuple[str, SourceBundle], ...]], str] | None = None

    def reconcile(self, observations: tuple[ProviderObservation, ...]) -> tuple[ArtifactBundle, ReconciliationReport]:
        found = tuple(item for item in observations if not item.artifacts.empty())
        contributors: dict[str, tuple[str, ...]] = {}

        def exact(attribute: str, label: str):
            supplied = tuple((item.provider, getattr(item.artifacts, attribute))
                             for item in found if getattr(item.artifacts, attribute) is not None)
            if not supplied:
                return None
            first = supplied[0][1]
            if any(value != first for _, value in supplied[1:]):
                raise ArtifactConflictError(f"providers disagree on {label}")
            contributors[label] = tuple(name for name, _ in supplied)
            return first

        creation = exact("creation_code", "creation")
        runtime = exact("runtime_code", "runtime")
        sources = tuple((item.provider, item.artifacts.source) for item in found
                        if item.artifacts.source is not None)
        selected_source = None
        relation = None
        selected_provider = None
        if sources:
            contributors["source"] = tuple(name for name, _ in sources)
            relation = "exact"
            for _, candidate in sources[1:]:
                relation = source_relation(sources[0][1], candidate)
                if relation == "conflict":
                    raise ArtifactConflictError("providers disagree on source")
            if self.source_selector is not None:
                selected_provider = self.source_selector(sources)
            else:
                selected_provider = next((name for name in self.preferred_source_providers
                                          if any(provider == name for provider, _ in sources)),
                                         sources[0][0])
            selected_source = next(value for name, value in sources if name == selected_provider)
        return ArtifactBundle(selected_source, creation, runtime), ReconciliationReport(
            contributors, relation, selected_provider)

