from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import math
import os
from pathlib import Path
import ssl
import tempfile
import threading
import time
from typing import Any
from urllib.parse import urlencode

from ..cache import DEFAULT_CACHE_ROOT
from ..codec import decode_hex
from ..errors import (CacheError, InvalidArtifactError, ProviderQuotaError,
                      ProviderRateLimitError, ProviderUnavailableError)
from ..models import (ArtifactKind, ArtifactOutcome, ContractLocation,
                      OutcomeStatus, ProviderObservation, SourceBundle)
from .base import CachedHttpProvider


class EtherscanProvider(CachedHttpProvider):
    """Etherscan V2 adapter with a shared, cache-scoped request schedule."""

    name = "etherscan"
    api_url = "https://api.etherscan.io/v2/api"
    _process_lock = threading.RLock()

    def __init__(self, cache_dir: Path = DEFAULT_CACHE_ROOT / "etherscan",
                 api_key: str | None = None, *,
                 calls_per_second: float = 3.0, timeout: float = 30,
                 ssl_context: ssl.SSLContext | None = None,
                 ca_file: str | os.PathLike | None = None) -> None:
        super().__init__(cache_dir, timeout=timeout, ssl_context=ssl_context, ca_file=ca_file)
        key = os.environ.get("ETHERSCAN_API_KEY", "") if api_key is None else api_key
        if not isinstance(key, str):
            raise ValueError("api_key must be text")
        self.api_key = key.strip()
        if (isinstance(calls_per_second, bool)
                or not isinstance(calls_per_second, (int, float))
                or not math.isfinite(calls_per_second) or calls_per_second <= 0):
            raise ValueError("calls_per_second must be finite and positive")
        self.calls_per_second = float(calls_per_second)
        self.request_interval = 1.0 / self.calls_per_second

    @property
    def _schedule_path(self) -> Path:
        return self.cache.root / ".request-schedule.json"

    @staticmethod
    def _atomic_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                             prefix=f".{path.name}.", delete=False) as output:
                temporary = Path(output.name)
                json.dump(value, output, allow_nan=False, separators=(",", ":"))
                output.write("\n")
            os.replace(temporary, path)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @contextmanager
    def _request_slot(self):
        """Space calls across all processes using the same cache directory."""
        with self._process_lock:
            self.cache.root.mkdir(parents=True, exist_ok=True)
            try:
                with (self.cache.root / ".request.lock").open("a") as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    now = time.time()
                    if self._schedule_path.exists():
                        state = json.loads(self._schedule_path.read_text(encoding="utf-8"))
                        next_request = state.get("next_request") if isinstance(state, dict) else None
                        if (isinstance(next_request, bool)
                                or not isinstance(next_request, (int, float))
                                or not math.isfinite(next_request)):
                            raise ProviderUnavailableError(
                                "invalid Etherscan request schedule", provider=self.name,
                                category="request_scheduling", retryable=False, origin="cache")
                        delay = next_request - now
                        if delay > 0:
                            time.sleep(delay)
                    request_started = time.time()
                    self._atomic_json(self._schedule_path, {
                        "next_request": request_started + self.request_interval,
                    })
            except ProviderUnavailableError:
                raise
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                raise ProviderUnavailableError(
                    f"Etherscan request scheduling failure: {exc}", provider=self.name,
                    category="request_scheduling", retryable=True, origin="cache") from exc
        # The slot is reserved durably before releasing the process and file
        # locks. Network latency can therefore overlap without permitting
        # request starts faster than the rate of the worker that reserved the
        # preceding slot. Different users of one cache may choose different
        # rates; the resulting shared stream falls between those rates.
        yield

    @staticmethod
    def _limit_error(detail: str):
        normalized = detail.casefold()
        if "rate limit" in normalized or "too many request" in normalized:
            return ProviderRateLimitError("Etherscan", detail)
        if any(marker in normalized for marker in (
                "daily limit", "daily call", "call limit", "quota",
                "community free api limit", "monthly spend cap")):
            return ProviderQuotaError("Etherscan", detail)
        return None

    def _query(self, location: ContractLocation, **parameters):
        query = urlencode({"chainid": location.chain_id, "apikey": self.api_key,
                           **parameters})
        with self._request_slot():
            status, value = self._json_request(f"{self.api_url}?{query}", headers={
                "User-Agent": "ethcode/0.2"})
        if status == 429:
            raise ProviderRateLimitError(
                "Etherscan", "HTTP 429 Too Many Requests", http_status=429)
        if status != 200 or not isinstance(value, dict):
            raise ProviderUnavailableError(
                f"Etherscan request failed with HTTP {status}", provider=self.name,
                category="http", retryable=status >= 500, origin="request",
                http_status=status)
        detail = value.get("result")
        if not isinstance(detail, str) and isinstance(value.get("error"), dict):
            detail = value["error"].get("message")
        if isinstance(detail, str):
            limit = self._limit_error(detail)
            if limit is not None:
                raise limit
        if "error" in value:
            message = detail if isinstance(detail, str) else value.get("message", "unknown error")
            raise ProviderUnavailableError(
                f"Etherscan API error: {message}", provider=self.name,
                category="invalid_provider_response", retryable=True, origin="request")
        return value

    @staticmethod
    def _api_error(envelope: dict[str, Any]) -> str | None:
        if envelope.get("status") == "0" or str(envelope.get("message", "")).upper() == "NOTOK":
            result = envelope.get("result")
            return result if isinstance(result, str) else "unknown API error"
        return None

    @staticmethod
    def _source(record) -> SourceBundle | None:
        text = record.get("SourceCode")
        if not isinstance(text, str) or not text:
            return None
        compiler_type = str(record.get("CompilerType", "")).casefold()
        compiler_version = str(record.get("CompilerVersion", ""))
        language = ("Yul" if compiler_type == "yul" else "Vyper"
                    if "vyper" in compiler_type or compiler_version.casefold().startswith("vyper:")
                    else "Solidity")
        version = compiler_version.removeprefix("vyper:").removeprefix("v") or None
        candidate = text[1:-1] if text.startswith("{{") and text.endswith("}}") else text
        if candidate.startswith("{"):
            try:
                decoded = json.loads(candidate)
                if not isinstance(decoded, dict) or not decoded:
                    raise ValueError("SourceCode JSON must be a nonempty object")
                source_map = decoded.get("sources") if "sources" in decoded else decoded
                if not isinstance(source_map, dict) or not source_map:
                    raise ValueError("source map must be a nonempty object")
                sources = {}
                for path, entry in source_map.items():
                    content = entry.get("content") if isinstance(entry, dict) else entry
                    if (not isinstance(path, str) or not path
                            or not isinstance(content, str) or not content):
                        raise ValueError("source entries need nonempty paths and text content")
                    sources[path] = content
                return SourceBundle(decoded.get("language", language), sources, version,
                                    decoded.get("settings"))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise InvalidArtifactError(f"invalid Etherscan SourceCode JSON: {exc}") from exc
        suffix = "vy" if language == "Vyper" else "yul" if language == "Yul" else "sol"
        name = record.get("ContractFileName") or f"{record.get('ContractName') or 'Contract'}.{suffix}"
        settings = {}
        if language == "Solidity" and record.get("OptimizationUsed") in ("0", "1"):
            optimizer = {"enabled": record["OptimizationUsed"] == "1"}
            runs = record.get("Runs")
            if isinstance(runs, str) and runs.isascii() and runs.isdecimal():
                optimizer["runs"] = int(runs)
            settings["optimizer"] = optimizer
        evm = record.get("EVMVersion")
        if isinstance(evm, str) and evm and evm.casefold() != "default":
            settings["evmVersion"] = evm
        return SourceBundle(language, {str(name): text}, version, settings or None)

    def _normalize_endpoint(self, kind: ArtifactKind,
                            envelope: dict[str, Any]) -> tuple[str, SourceBundle | bytes | None]:
        error = self._api_error(envelope)
        if error is not None:
            if kind is ArtifactKind.SOURCE and "source code not verified" in error.casefold():
                return "not_found", None
            raise ProviderUnavailableError(
                f"Etherscan {kind.value} API error: {error}", provider=self.name,
                category="invalid_provider_response", artifact_kind=kind,
                retryable=True, origin="request")
        result = envelope.get("result")
        if kind is ArtifactKind.RUNTIME:
            if result == "0x":
                return "not_found", None
            try:
                return "found", decode_hex(result, field="runtime code")
            except InvalidArtifactError as exc:
                raise ProviderUnavailableError(
                    f"invalid Etherscan runtime response: {exc}", provider=self.name,
                    category="invalid_provider_response", artifact_kind=kind,
                    retryable=True, origin="request") from exc
        if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
            raise ProviderUnavailableError(
                f"Etherscan returned no single {kind.value} record", provider=self.name,
                category="invalid_provider_response", artifact_kind=kind,
                retryable=True, origin="request")
        record = result[0]
        if kind is ArtifactKind.SOURCE:
            try:
                source = self._source(record)
            except InvalidArtifactError as exc:
                raise ProviderUnavailableError(
                    str(exc), provider=self.name, category="invalid_provider_response",
                    artifact_kind=kind, retryable=True, origin="request") from exc
            return ("found", source) if source is not None else ("not_found", None)
        raw = record.get("creationBytecode")
        if raw == "0x":
            return "not_found", None
        try:
            return "found", decode_hex(raw, field="creation code")
        except InvalidArtifactError as exc:
            raise ProviderUnavailableError(
                f"invalid Etherscan creation response: {exc}", provider=self.name,
                category="invalid_provider_response", artifact_kind=kind,
                retryable=True, origin="request") from exc

    @staticmethod
    def _parameters(kind: ArtifactKind, address: str) -> dict[str, str]:
        if kind is ArtifactKind.SOURCE:
            return {"module": "contract", "action": "getsourcecode", "address": address}
        if kind is ArtifactKind.CREATION:
            return {"module": "contract", "action": "getcontractcreation",
                    "contractaddresses": address}
        return {"module": "proxy", "action": "eth_getCode",
                "address": address, "tag": "latest"}

    def _endpoint(self, location: ContractLocation,
                  kind: ArtifactKind) -> tuple[SourceBundle | bytes | None, bool, str, dict[str, Any]]:
        cached = self.cache.read(kind.value, location.chain_id, location.address)
        if cached is not None:
            try:
                classification = cached["classification"]
                envelope = cached["response"]
            except (KeyError, TypeError) as exc:
                raise ProviderUnavailableError(
                    f"invalid cached Etherscan {kind.value} response: {exc}",
                    provider=self.name, category="cache_corruption",
                    artifact_kind=kind, retryable=False, origin="cache") from exc
            if classification not in ("found", "not_found") or not isinstance(envelope, dict):
                raise ProviderUnavailableError(
                    f"invalid cached Etherscan {kind.value} response",
                    provider=self.name, category="cache_corruption",
                    artifact_kind=kind, retryable=False, origin="cache")
            try:
                actual, value = self._normalize_endpoint(kind, envelope)
            except ProviderUnavailableError as exc:
                raise ProviderUnavailableError(
                    f"invalid cached Etherscan {kind.value} response: {exc.detail}",
                    provider=self.name, category="cache_corruption",
                    artifact_kind=kind, retryable=False, origin="cache") from exc
            if actual != classification:
                raise ProviderUnavailableError(
                    f"cached Etherscan {kind.value} classification mismatch",
                    provider=self.name, category="cache_corruption",
                    artifact_kind=kind, retryable=False, origin="cache")
            return value, True, classification, envelope

        envelope = self._query(location, **self._parameters(kind, location.address))
        classification, value = self._normalize_endpoint(kind, envelope)
        # Only recognized successful values and recognized absences reach here.
        # Rate, quota, transport, and ambiguous API errors never create entries.
        self.cache.write(kind.value, location.chain_id, location.address, {
            "classification": classification,
            "response": envelope,
            "backend": "api-v2",
        })
        return value, False, classification, envelope

    def fetch(self, location: ContractLocation, kinds) -> ProviderObservation:
        if not self.api_key:
            # Cached endpoint responses remain usable without credentials.
            cached_kinds = tuple(kind for kind in ArtifactKind if kind in kinds
                                 and self.cache.read(
                                     kind.value, location.chain_id, location.address) is not None)
            missing_kinds = tuple(kind for kind in ArtifactKind
                                  if kind in kinds and kind not in cached_kinds)
            if missing_kinds:
                raise ProviderUnavailableError(
                    "provide api_key or set ETHERSCAN_API_KEY", provider=self.name,
                    category="credentials_missing", retryable=False,
                    origin="configuration", artifact_kind=missing_kinds[0],
                    completed_kinds=cached_kinds)
        outcomes: dict[ArtifactKind, ArtifactOutcome] = {}
        endpoint_context: dict[str, Any] = {}
        metadata: dict[str, Any] = {}
        for kind in ArtifactKind:
            if kind not in kinds:
                continue
            try:
                value, cached, classification, envelope = self._endpoint(location, kind)
            except CacheError as exc:
                raise ProviderUnavailableError(
                    str(exc), provider=self.name, category="cache_corruption",
                    artifact_kind=kind, retryable=False, origin="cache",
                    completed_kinds=tuple(outcomes)) from exc
            except ProviderUnavailableError as exc:
                if exc.artifact_kind is None:
                    exc.artifact_kind = kind
                exc.completed_kinds = tuple(outcomes)
                raise
            outcomes[kind] = ArtifactOutcome(
                OutcomeStatus.FOUND if classification == "found" else OutcomeStatus.ABSENT,
                value, cached)
            endpoint_context[kind.value] = {
                "cached": cached, "classification": classification,
            }
            if kind is ArtifactKind.SOURCE and isinstance(envelope.get("result"), list):
                record = envelope["result"][0] if envelope["result"] else {}
                if isinstance(record, dict):
                    for field in ("ContractName", "ContractFileName", "CompilerVersion",
                                  "CompilerType", "OptimizationUsed", "Runs", "EVMVersion"):
                        if isinstance(record.get(field), (str, int, bool)):
                            metadata[field] = record[field]
        return ProviderObservation(
            self.name, location, outcomes,
            {"backend": "api-v2", "endpoints": endpoint_context,
             "source_metadata": metadata})
