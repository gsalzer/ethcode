from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import ssl
from typing import Any
import urllib.error
import urllib.request

from ..cache import JsonFileCache
from ..errors import ProviderUnavailableError


def transport_error(provider: str, exc: BaseException) -> ProviderUnavailableError:
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(reason, socket.gaierror):
        category, detail = "dns", f"{provider} DNS resolution failure"
    elif isinstance(reason, (ssl.SSLError, ssl.CertificateError)):
        category, detail = "tls", f"{provider} TLS failure"
    elif isinstance(reason, (TimeoutError, socket.timeout)):
        category, detail = "timeout", f"{provider} network timeout"
    elif isinstance(reason, ConnectionError):
        category, detail = "connection", f"{provider} connection failure"
    else:
        category, detail = "connection", f"{provider} transport failure"
    return ProviderUnavailableError(
        detail, provider=provider.casefold(), category=category, retryable=True,
        origin="request")


class CachedHttpProvider:
    name: str

    def __init__(self, cache_dir: Path, *, timeout: float = 30,
                 ssl_context: ssl.SSLContext | None = None,
                 ca_file: str | os.PathLike | None = None) -> None:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError("timeout must be positive")
        if ssl_context is not None and ca_file is not None:
            raise ValueError("provide ssl_context or ca_file, not both")
        self.cache = JsonFileCache(cache_dir)
        self.timeout = float(timeout)
        if ssl_context is not None:
            self.ssl_context = ssl_context
        else:
            selected_ca = os.environ.get("SSL_CERT_FILE") if ca_file is None else os.fspath(ca_file)
            try:
                self.ssl_context = ssl.create_default_context(cafile=selected_ca)
            except (OSError, ssl.SSLError) as exc:
                raise ValueError(f"cannot initialize TLS trust from {selected_ca}") from exc

    def _json_request(self, url: str, *, headers: dict[str, str]) -> tuple[int, Any]:
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(
                    request, timeout=self.timeout, context=self.ssl_context) as response:
                status = getattr(response, "status", 200)
                payload = response.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            payload = exc.read()
        except (OSError, urllib.error.URLError) as exc:
            raise transport_error(self.name, exc) from None
        try:
            return status, json.loads(payload.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ProviderUnavailableError(
                f"{self.name} returned invalid JSON", provider=self.name,
                category="invalid_json", retryable=True, origin="request") from exc
