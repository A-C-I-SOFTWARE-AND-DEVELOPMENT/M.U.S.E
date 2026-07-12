from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
import re
from typing import Any


class SecretFieldError(ValueError):
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"secret-like field is not allowed at {path}")


class NonFiniteNumberError(ValueError):
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"non-finite number is not allowed at {path}")


_SECRET_SEGMENTS = frozenset(
    {
        "bearer",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "passwd",
        "password",
        "pwd",
        "secret",
    }
)
_SECRET_EXACT = frozenset(
    {
        "api_key",
        "authorization",
        "owner_authorization",
        "owner_phrase",
        "private_key",
        "provider_key",
        "token",
    }
)
_SENSITIVE_KEY_QUALIFIERS = frozenset(
    {"api", "encryption", "private", "provider", "signing"}
)


def validate_no_secret_fields(value: Any, *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"non-string mapping key is not allowed at {path}")
            normalized = _normalize_key(key)
            item_path = f"{path}.{key}"
            if _is_secret_key(normalized):
                raise SecretFieldError(item_path)
            validate_no_secret_fields(item, path=item_path)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            validate_no_secret_fields(item, path=f"{path}[{index}]")


def validate_finite_numbers(value: Any, *, path: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise NonFiniteNumberError(path)
    if isinstance(value, Mapping):
        for key, item in value.items():
            validate_finite_numbers(item, path=f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            validate_finite_numbers(item, path=f"{path}[{index}]")


def _normalize_key(key: str) -> str:
    snake_case = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
    return re.sub(r"[^a-z0-9]+", "_", snake_case.casefold()).strip("_")


def _is_secret_key(normalized: str) -> bool:
    if normalized in _SECRET_EXACT or normalized.endswith("_token"):
        return True
    segments = frozenset(normalized.split("_"))
    if segments & _SECRET_SEGMENTS:
        return True
    return normalized.endswith("_key") and bool(segments & _SENSITIVE_KEY_QUALIFIERS)
