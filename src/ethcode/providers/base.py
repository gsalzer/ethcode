from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request

from ..cache import JsonFileCache
from ..errors import ProviderUnavailableError
from ..models import ArtifactBundle


class CachedHttpProvider:
    name: str

    def __init__(self, cache_dir: Path, *, timeout: float = 30) -> None:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError("timeout must be positive")
        self.cache = JsonFileCache(cache_dir)
        self.timeout = float(timeout)

    def _json_request(self, url: str, *, headers: dict[str, str]) -> tuple[int, Any]:
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = getattr(response, "status", 200)
                payload = response.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            payload = exc.read()
        except (OSError, urllib.error.URLError) as exc:
            raise ProviderUnavailableError(f"{self.name} transport failure: {type(exc).__name__}") from None
        try:
            return status, json.loads(payload.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ProviderUnavailableError(f"{self.name} returned invalid JSON") from exc

    @staticmethod
    def _select(bundle: ArtifactBundle, kinds) -> ArtifactBundle:
        from ..models import ArtifactKind
        return ArtifactBundle(
            bundle.source if ArtifactKind.SOURCE in kinds else None,
            bundle.creation_code if ArtifactKind.CREATION in kinds else None,
            bundle.runtime_code if ArtifactKind.RUNTIME in kinds else None,
        )

