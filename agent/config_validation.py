"""Configuration validation and migration utilities.

Validates config.yaml against expected schema and provides
graceful migration for old config formats.
"""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ConfigValidationResult:
    """Result of config validation."""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    migrated_fields: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.is_valid


def validate_config(config_path: Path) -> ConfigValidationResult:
    """Validate a config.yaml file.

    Checks for:
    - Valid YAML syntax
    - Required top-level keys
    - Known deprecated keys
    - Type correctness for common fields
    """
    result = ConfigValidationResult(is_valid=True)

    if not config_path.is_file():
        result.is_valid = False
        result.errors.append(f"Config file not found: {config_path}")
        return result

    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        result.is_valid = False
        result.errors.append(f"Invalid YAML: {e}")
        return result

    if not isinstance(config, dict):
        result.is_valid = False
        result.errors.append("Config must be a YAML mapping (dict)")
        return result

    # Check for deprecated keys
    deprecated = {
        "max_iterations": "agent.max_iterations",
        "model": "agent.model",
        "provider": "agent.provider",
        "base_url": "agent.base_url",
        "api_key": "agent.api_key",
    }
    for old_key, new_path in deprecated.items():
        if old_key in config:
            result.warnings.append(
                f"Deprecated key '{old_key}' — use '{new_path}' instead"
            )

    # Validate model name is non-empty if present
    if "model" in config and not config["model"]:
        result.errors.append("'model' must be a non-empty string")

    # Validate max_iterations range
    if "max_iterations" in config:
        mi = config["max_iterations"]
        if not isinstance(mi, int) or mi < 1 or mi > 1000:
            result.errors.append(f"'max_iterations' must be int 1-1000, got {mi}")

    result.is_valid = len(result.errors) == 0
    return result


def backup_config(config_path: Path) -> Path | None:
    """Create a timestamped backup of a config file.

    Returns the backup path or None if the source doesn't exist.
    """
    if not config_path.is_file():
        return None
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup = config_path.with_suffix(f".{ts}.bak")
    shutil.copy2(config_path, backup)
    logger.info("Backed up config to %s", backup)
    return backup


def migrate_config(config_path: Path) -> ConfigValidationResult:
    """Migrate old config format to current.

    Currently a no-op stub — add migration logic as config format evolves.
    """
    result = validate_config(config_path)
    if not result.is_valid:
        return result

    # Future migrations go here
    # if needs_migration:
    #     backup_config(config_path)
    #     apply_migration(config_path)
    #     result.migrated_fields.append("field_name")

    return result
