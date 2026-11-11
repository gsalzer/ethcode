from __future__ import annotations

from typing import Any

from .errors import InvalidArtifactError


def decode_hex(value: Any, *, field: str = "bytecode") -> bytes:
    if not isinstance(value, str):
        raise InvalidArtifactError(f"{field} must be hexadecimal text")
    text = value.removeprefix("0x").removeprefix("0X")
    if not text or len(text) % 2:
        raise InvalidArtifactError(f"{field} must contain nonempty even-length hexadecimal")
    try:
        return bytes.fromhex(text)
    except ValueError as exc:
        raise InvalidArtifactError(f"{field} is not hexadecimal") from exc

