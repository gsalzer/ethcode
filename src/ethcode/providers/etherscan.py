from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any
from urllib.parse import urlencode

from ..cache import DEFAULT_CACHE_ROOT
from ..codec import decode_hex
from ..errors import (InvalidArtifactError, ProviderQuotaError,
                      ProviderRateLimitError, ProviderUnavailableError)
from ..models import (ArtifactBundle, ArtifactKind, ContractLocation, ObservationStatus,
                      ProviderObservation, SourceBundle)
from .base import CachedHttpProvider


class EtherscanProvider(CachedHttpProvider):
    """Etherscan V2 adapter with a shared, cache-scoped request schedule."""

    name = "etherscan"
    api_url = "https://api.etherscan.io/v2/api"
    _process_lock = threading.RLock()

    def __init__(self, cache_dir: Path = DEFAULT_CACHE_ROOT / "etherscan",
                 api_key: str | None = None, *,
                 calls_per_second: float = 3.0, timeout: float = 30) -> None:
        super().__init__(cache_dir, timeout=timeout)
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
                        configured_rate = state.get("calls_per_second") if isinstance(state, dict) else None
                        if configured_rate != self.calls_per_second:
                            raise ProviderUnavailableError(
                                "Etherscan calls_per_second differs from another user of this cache")
                        next_request = state.get("next_request") if isinstance(state, dict) else None
                        if (isinstance(next_request, bool)
                                or not isinstance(next_request, (int, float))
                                or not math.isfinite(next_request)):
                            raise ProviderUnavailableError("invalid Etherscan request schedule")
                        delay = next_request - now
                        if delay > 0:
                            time.sleep(delay)
                    try:
                        yield
                    finally:
                        self._atomic_json(self._schedule_path, {
                            "next_request": time.time() + self.request_interval,
                            "calls_per_second": self.calls_per_second,
                        })
            except ProviderUnavailableError:
                raise
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                raise ProviderUnavailableError(
                    f"Etherscan request scheduling failure: {exc}") from exc

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
                "User-Agent": "ethcode/0.1"})
        if status == 429:
            raise ProviderRateLimitError("Etherscan", "HTTP 429 Too Many Requests")
        if status != 200 or not isinstance(value, dict):
            raise ProviderUnavailableError(f"Etherscan request failed with HTTP {status}")
        detail = value.get("result")
        if not isinstance(detail, str) and isinstance(value.get("error"), dict):
            detail = value["error"].get("message")
        if isinstance(detail, str):
            limit = self._limit_error(detail)
            if limit is not None:
                raise limit
        if "error" in value:
            message = detail if isinstance(detail, str) else value.get("message", "unknown error")
            raise ProviderUnavailableError(f"Etherscan API error: {message}")
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
        language = "Vyper" if str(record.get("CompilerVersion", "")).startswith("vyper") else "Solidity"
        version = str(record.get("CompilerVersion", "")).removeprefix("v") or None
        candidate = text[1:-1] if text.startswith("{{") and text.endswith("}}") else text
        if candidate.startswith("{"):
            try:
                value = json.loads(candidate)
                sources = {path: item["content"] for path, item in value["sources"].items()}
                return SourceBundle(value.get("language", language), sources, version,
                                    value.get("settings"))
            except (KeyError, TypeError, json.JSONDecodeError):
                pass
        name = record.get("ContractName") or "Contract"
        return SourceBundle(language, {f"{name}.sol": text}, version)

    def _normalize_endpoint(self, kind: ArtifactKind,
                            envelope: dict[str, Any]) -> tuple[str, SourceBundle | bytes | None]:
        error = self._api_error(envelope)
        if error is not None:
            if kind is ArtifactKind.SOURCE and "source code not verified" in error.casefold():
                return "not_found", None
            raise ProviderUnavailableError(f"Etherscan {kind.value} API error: {error}")
        result = envelope.get("result")
        if kind is ArtifactKind.RUNTIME:
            if result == "0x":
                return "not_found", None
            try:
                return "found", decode_hex(result, field="runtime code")
            except InvalidArtifactError as exc:
                raise ProviderUnavailableError(f"invalid Etherscan runtime response: {exc}") from exc
        if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
            raise ProviderUnavailableError(
                f"Etherscan returned no single {kind.value} record")
        record = result[0]
        if kind is ArtifactKind.SOURCE:
            source = self._source(record)
            return ("found", source) if source is not None else ("not_found", None)
        raw = record.get("creationBytecode")
        if raw == "0x":
            return "not_found", None
        try:
            return "found", decode_hex(raw, field="creation code")
        except InvalidArtifactError as exc:
            raise ProviderUnavailableError(f"invalid Etherscan creation response: {exc}") from exc

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
                  kind: ArtifactKind) -> tuple[SourceBundle | bytes | None, bool, str]:
        cached = self.cache.read(kind.value, location.chain_id, location.address)
        if cached is not None:
            try:
                classification = cached["classification"]
                envelope = cached["response"]
            except (KeyError, TypeError) as exc:
                raise ProviderUnavailableError(
                    f"invalid cached Etherscan {kind.value} response: {exc}") from exc
            if classification not in ("found", "not_found") or not isinstance(envelope, dict):
                raise ProviderUnavailableError(
                    f"invalid cached Etherscan {kind.value} response")
            actual, value = self._normalize_endpoint(kind, envelope)
            if actual != classification:
                raise ProviderUnavailableError(
                    f"cached Etherscan {kind.value} classification mismatch")
            return value, True, classification

        envelope = self._query(location, **self._parameters(kind, location.address))
        classification, value = self._normalize_endpoint(kind, envelope)
        # Only recognized successful values and recognized absences reach here.
        # Rate, quota, transport, and ambiguous API errors never create entries.
        self.cache.write(kind.value, location.chain_id, location.address, {
            "classification": classification,
            "response": envelope,
            "backend": "api-v2",
        })
        return value, False, classification

    def fetch(self, location: ContractLocation, kinds) -> ProviderObservation:
        if not self.api_key:
            # Cached endpoint responses remain usable without credentials.
            if any(self.cache.read(kind.value, location.chain_id, location.address) is None
                   for kind in kinds):
                raise ProviderUnavailableError("provide api_key or set ETHERSCAN_API_KEY")
        values: dict[ArtifactKind, SourceBundle | bytes | None] = {}
        endpoint_context: dict[str, Any] = {}
        for kind in ArtifactKind:
            if kind not in kinds:
                continue
            value, cached, classification = self._endpoint(location, kind)
            values[kind] = value
            endpoint_context[kind.value] = {
                "cached": cached, "classification": classification,
            }
        source = values.get(ArtifactKind.SOURCE)
        creation = values.get(ArtifactKind.CREATION)
        runtime = values.get(ArtifactKind.RUNTIME)
        bundle = ArtifactBundle(source, creation, runtime)
        status = ObservationStatus.NOT_FOUND if bundle.empty() else ObservationStatus.FOUND
        all_cached = bool(endpoint_context) and all(
            value["cached"] for value in endpoint_context.values())
        return ProviderObservation(
            self.name, location, status, bundle,
            {"backend": "api-v2", "endpoints": endpoint_context}, all_cached)
