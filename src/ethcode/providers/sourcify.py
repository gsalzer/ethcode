from __future__ import annotations

from contextlib import contextmanager
import email.utils
import fcntl
import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading
import time
from typing import Any
import urllib.error
import urllib.request
from urllib.parse import quote

from ..cache import DEFAULT_CACHE_ROOT
from ..codec import decode_hex
from ..errors import InvalidArtifactError, ProviderUnavailableError
from ..models import (ArtifactBundle, ContractLocation, ObservationStatus,
                      ProviderObservation, SourceBundle)
from .base import CachedHttpProvider


class SourcifyProvider(CachedHttpProvider):
    name = "sourcify"
    api_url = "https://sourcify.dev/server/v2/contract"
    fields = ",".join((
        "sources",
        "compilation.language",
        "compilation.compilerVersion",
        "compilation.compilerSettings",
        "creationBytecode.onchainBytecode",
        "runtimeBytecode.onchainBytecode",
    ))
    _process_lock = threading.RLock()

    def __init__(self, cache_dir: Path = DEFAULT_CACHE_ROOT / "sourcify",
                 email: str | None = None, *,
                 timeout: float = 30, interval: float = 1.0,
                 retries: int = 3, backoff: float = 2.0,
                 max_wait: float = 60.0,
                 project_url: str = "https://github.com/gsalzer/ethcode") -> None:
        super().__init__(cache_dir, timeout=timeout)
        self.email = os.environ.get("SOURCIFY_EMAIL", "") if email is None else email
        if not isinstance(self.email, str) or (self.email and not re.fullmatch(
                r"[^\s@()<>\x00-\x1f\x7f]+@[^\s@()<>\x00-\x1f\x7f]+", self.email)):
            raise ValueError("email must be an ASCII email address")
        if self.email and not self.email.isascii():
            raise ValueError("email must be an ASCII email address")
        for name, value in (("interval", interval), ("backoff", backoff),
                            ("max_wait", max_wait)):
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0):
                raise ValueError(f"{name} must be finite and nonnegative")
        if backoff == 0:
            raise ValueError("backoff must be positive")
        if isinstance(retries, bool) or not isinstance(retries, int) or not 0 <= retries <= 20:
            raise ValueError("retries must be an integer from 0 to 20")
        if not isinstance(project_url, str) or not project_url.strip():
            raise ValueError("project_url must be nonempty text")
        self.interval = float(interval)
        self.retries = retries
        self.backoff = float(backoff)
        self.max_wait = float(max_wait)
        self.project_url = project_url.strip()
        self.user_agent = (f"ethcode/0.1 (+{self.project_url}; {self.email})"
                           if self.email else f"ethcode/0.1 (+{self.project_url})")

    @property
    def _cooldown_path(self) -> Path:
        return self.cache.root / ".cooldown.json"

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
    def _request_lock(self):
        """Coordinate the request schedule for every process using this cache."""
        with self._process_lock:
            self.cache.root.mkdir(parents=True, exist_ok=True)
            try:
                with (self.cache.root / ".request.lock").open("a") as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    yield
            except (OSError, UnicodeError, ValueError) as exc:
                raise ProviderUnavailableError(f"Sourcify request locking failure: {exc}") from exc

    def _wait_for_cooldown(self) -> None:
        path = self._cooldown_path
        if not path.exists():
            return
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            retry_at = state.get("retry_at") if isinstance(state, dict) else None
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ProviderUnavailableError(f"invalid Sourcify cooldown: {exc}") from exc
        if (isinstance(retry_at, bool) or not isinstance(retry_at, (int, float))
                or not math.isfinite(retry_at)):
            raise ProviderUnavailableError("invalid Sourcify cooldown timestamp")
        delay = max(0.0, retry_at - time.time())
        if delay > self.max_wait:
            raise ProviderUnavailableError(
                f"Sourcify retry delay {delay:.1f}s exceeds max_wait={self.max_wait:g}s")
        if delay:
            time.sleep(delay)

    def _set_cooldown(self, delay: float) -> None:
        self._atomic_json(self._cooldown_path, {"retry_at": time.time() + delay})

    @staticmethod
    def _retry_after(value: str | None) -> float:
        if not value:
            return 0.0
        if re.fullmatch(r"[0-9]+", value.strip()):
            return float(value)
        try:
            parsed = email.utils.parsedate_to_datetime(value)
            return max(0.0, parsed.timestamp() - time.time())
        except (TypeError, ValueError, OverflowError):
            return 0.0

    def _request(self, url: str) -> tuple[int, Any]:
        request = urllib.request.Request(url, headers={
            "User-Agent": self.user_agent, "Accept": "application/json"})
        for attempt in range(self.retries + 1):
            delay = max(self.interval, self.backoff * (2 ** attempt))
            with self._request_lock():
                self._wait_for_cooldown()
                try:
                    with urllib.request.urlopen(request, timeout=self.timeout) as response:
                        status, headers, payload = getattr(response, "status", 200), response.headers, response.read()
                except urllib.error.HTTPError as exc:
                    status, headers, payload = exc.code, exc.headers, exc.read()
                except (OSError, urllib.error.URLError) as exc:
                    self._set_cooldown(delay)
                    failure = f"Sourcify transport failure: {type(exc).__name__}"
                else:
                    if status in (429,) or 500 <= status <= 599:
                        delay = max(delay, self._retry_after(headers.get("Retry-After")))
                        self._set_cooldown(delay)
                        failure = f"Sourcify HTTP {status}"
                    else:
                        self._set_cooldown(self.interval)
                        try:
                            return status, json.loads(payload.decode("utf-8"))
                        except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
                            raise ProviderUnavailableError("Sourcify returned invalid JSON") from exc
            if attempt == self.retries:
                raise ProviderUnavailableError(f"{failure}; retries exhausted")
        raise AssertionError("unreachable")

    @staticmethod
    def _bundle(record, location: ContractLocation) -> ArtifactBundle:
        if not isinstance(record, dict):
            raise InvalidArtifactError("Sourcify contract response is not an object")
        if (str(record.get("chainId")) != str(location.chain_id)
                or str(record.get("address", "")).casefold() != location.address):
            raise InvalidArtifactError("Sourcify contract response identity mismatch")
        if record.get("match") not in ("match", "exact_match"):
            raise InvalidArtifactError("invalid Sourcify match")
        for key in ("creationMatch", "runtimeMatch"):
            if record.get(key) not in (None, "match", "exact_match"):
                raise InvalidArtifactError(f"invalid Sourcify {key}")
        compilation = record.get("compilation") or {}
        raw_sources = record.get("sources") or {}
        source = None
        if compilation and raw_sources:
            try:
                source = SourceBundle(
                    compilation["language"],
                    {path: item["content"] for path, item in raw_sources.items()},
                    str(compilation.get("compilerVersion", "")).removeprefix("v") or None,
                    compilation.get("compilerSettings"),
                )
            except (KeyError, TypeError) as exc:
                raise InvalidArtifactError(f"invalid Sourcify source: {exc}") from exc
        creation_raw = (record.get("creationBytecode") or {}).get("onchainBytecode")
        runtime_raw = (record.get("runtimeBytecode") or {}).get("onchainBytecode")
        return ArtifactBundle(
            source,
            decode_hex(creation_raw, field="creation code") if creation_raw else None,
            decode_hex(runtime_raw, field="runtime code") if runtime_raw else None,
        )

    def store_response(self, location: ContractLocation, response: dict[str, Any], *,
                       provenance: dict[str, Any] | None = None) -> bool:
        """Store an API-shaped successful response when the cache entry is absent.

        The response is fully validated and can come from an offline Sourcify
        dataset importer. Existing entries are preserved. Return whether this
        call wrote the entry.
        """
        try:
            self._bundle(response, location)
        except InvalidArtifactError as exc:
            raise ProviderUnavailableError(str(exc)) from exc
        context = dict(provenance or {"backend": "import"})
        with self._request_lock():
            if self.cache.read("contract", location.chain_id, location.address) is not None:
                return False
            self.cache.write("contract", location.chain_id, location.address, {
                "http_status": 200,
                "response": response,
                "provenance": context,
            })
        return True

    def response_cached(self, location: ContractLocation) -> bool:
        """Return whether a validated cache envelope exists for the location."""
        cached = self.cache.read("contract", location.chain_id, location.address)
        if cached is None:
            return False
        if (cached.get("http_status") not in (200, 404)
                or not isinstance(cached.get("response"), dict)):
            raise ProviderUnavailableError("invalid cached Sourcify response")
        return True

    def fetch(self, location: ContractLocation, kinds) -> ProviderObservation:
        cached_record = self.cache.read("contract", location.chain_id, location.address)
        from_cache = cached_record is not None
        if cached_record is not None:
            try:
                status, record = cached_record["http_status"], cached_record["response"]
            except (KeyError, TypeError) as exc:
                raise ProviderUnavailableError(f"invalid cached Sourcify response: {exc}") from exc
            if status not in (200, 404) or not isinstance(record, dict):
                raise ProviderUnavailableError("invalid cached Sourcify response")
            provenance = cached_record.get("provenance", {"backend": "api-v2"})
            if not isinstance(provenance, dict):
                raise ProviderUnavailableError("invalid cached Sourcify provenance")
        else:
            if not self.email:
                raise ProviderUnavailableError(
                    "provide email= or set SOURCIFY_EMAIL for Sourcify requests")
            url = (f"{self.api_url}/{location.chain_id}/{quote(location.address)}"
                   f"?fields={quote(self.fields)}")
            status, record = self._request(url)
            provenance = {"backend": "api-v2"}
        if status == 404:
            error_absence = (isinstance(record, dict)
                             and isinstance(record.get("customCode"), str))
            contract_absence = (isinstance(record, dict)
                                and str(record.get("chainId")) == str(location.chain_id)
                                and str(record.get("address", "")).casefold() == location.address
                                and record.get("match") is None)
            if not error_absence and not contract_absence:
                raise ProviderUnavailableError("Sourcify returned an invalid 404 response")
            absence = record.get("customCode", "not_verified")
            bundle = ArtifactBundle()
            observation_status = ObservationStatus.NOT_FOUND
        elif status == 200 and isinstance(record, dict):
            try:
                bundle = self._bundle(record, location)
            except InvalidArtifactError as exc:
                raise ProviderUnavailableError(str(exc)) from exc
            absence = None
            observation_status = ObservationStatus.FOUND
        else:
            raise ProviderUnavailableError(f"Sourcify HTTP {status}")
        if not from_cache:
            self.cache.write("contract", location.chain_id, location.address, {
                "http_status": status,
                "response": record,
                "provenance": provenance,
            })
        provenance = dict(provenance)
        if absence is not None:
            provenance["absence"] = absence
        return ProviderObservation(
            self.name, location, observation_status,
            self._select(bundle, kinds), provenance, from_cache)

