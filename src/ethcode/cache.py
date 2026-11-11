from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .errors import CacheError


DEFAULT_CACHE_ROOT = Path.home() / ".cache" / "ethcode"


class JsonFileCache:
    """Small provider cache with atomic replacement and validated envelopes."""

    FORMAT = 1

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _path(self, namespace: str, chain_id: int, address: str) -> Path:
        return self.root / namespace / str(chain_id) / f"{address}.json"

    def read(self, namespace: str, chain_id: int, address: str) -> dict[str, Any] | None:
        path = self._path(namespace, chain_id, address)
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
            raise CacheError(f"cannot read cache entry {path}: {exc}") from exc
        if not isinstance(value, dict) or value.get("format") != self.FORMAT:
            raise CacheError(f"invalid cache entry {path}")
        return value

    def write(self, namespace: str, chain_id: int, address: str,
              value: dict[str, Any]) -> None:
        path = self._path(namespace, chain_id, address)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"format": self.FORMAT, **value}
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                             prefix=f".{path.name}.", delete=False) as output:
                temporary = Path(output.name)
                json.dump(record, output, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)
                output.write("\n")
            os.replace(temporary, path)
            temporary = None
        except (OSError, TypeError, ValueError) as exc:
            raise CacheError(f"cannot write cache entry {path}: {exc}") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

