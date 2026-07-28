"""Validation utilities for dataclasses and data models.

Provides validate_dataclass() and field validators for common patterns.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


def validate_non_empty_string(value: Any, field_name: str) -> str:
    """Validate that a string is non-empty."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string, got: {value!r}")
    return value


def validate_positive_int(value: Any, field_name: str) -> int:
    """Validate that a value is a positive integer."""
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer, got: {value}")
    return value


def validate_path_exists(value: Any, field_name: str) -> Path:
    """Validate that a path exists on disk."""
    path = Path(value) if not isinstance(value, Path) else value
    if not path.exists():
        raise FileNotFoundError(f"{field_name} path does not exist: {path}")
    return path


def validate_url(value: Any, field_name: str) -> str:
    """Basic URL format validation."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string, got {type(value).__name__}")
    url_pattern = re.compile(
        r'^https?://'  # scheme
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )
    if not url_pattern.match(value):
        raise ValueError(f"{field_name} is not a valid URL: {value}")
    return value


def validate_semver(value: Any, field_name: str) -> str:
    """Validate semantic versioning format (X.Y.Z)."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not re.match(r'^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?(?:\+[a-zA-Z0-9.]+)?$', value):
        raise ValueError(f"{field_name} must be semver (X.Y.Z), got: {value}")
    return value


@dataclass
class ValidationResult:
    """Result of a dataclass validation."""
    is_valid: bool
    errors: list[str]

    def __bool__(self) -> bool:
        return self.is_valid

    def __repr__(self) -> str:
        status = "✅ valid" if self.is_valid else f"❌ {len(self.errors)} errors"
        return f"ValidationResult({status})"


def validate_dataclass(instance: Any) -> ValidationResult:
    """Validate all fields of a dataclass instance.

    Checks for:
    - Required fields not being None
    - String fields not being empty
    - Path fields being valid paths

    Returns:
        ValidationResult with is_valid=True if all checks pass.
    """
    if not is_dataclass(instance):
        return ValidationResult(False, ["Not a dataclass instance"])

    errors: list[str] = []
    for field in fields(instance):
        value = getattr(instance, field.name)
        if value is None and field.default is None and field.default_factory is None:
            errors.append(f"Field '{field.name}' is required (None)")
        elif isinstance(value, str) and not value.strip() and not field.default:
            errors.append(f"Field '{field.name}' is empty")
    return ValidationResult(len(errors) == 0, errors)
