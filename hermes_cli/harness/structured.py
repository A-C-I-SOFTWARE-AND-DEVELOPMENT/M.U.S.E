"""Optional structured-output validation against structured_schemas.yaml."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from hermes_cli.harness.config import HarnessSettings

logger = logging.getLogger(__name__)


@dataclass
class StructuredResult:
    ok: bool
    detail: str = ""


def validate_json_payload(
    settings: HarnessSettings,
    text: str,
    schema_name: Optional[str] = None,
) -> StructuredResult:
    """Validate *text* as JSON; optionally against a named schema if present."""
    if not settings.enabled or not settings.structured_enabled:
        return StructuredResult(ok=True, detail="structured validation disabled")
    if not settings.enforce_json and not settings.validate_structured:
        return StructuredResult(ok=True, detail="enforce_json off")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return StructuredResult(ok=False, detail=f"invalid JSON: {exc}")

    schemas_path = settings.structured_schemas
    if not settings.validate_structured or schemas_path is None or not schemas_path.is_file():
        return StructuredResult(ok=True, detail="json ok")

    try:
        import yaml
    except ImportError:
        return StructuredResult(ok=True, detail="json ok (no yaml)")

    try:
        data = yaml.safe_load(schemas_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug("structured schemas load failed: %s", exc)
        return StructuredResult(ok=True, detail="json ok")

    if not isinstance(data, Mapping):
        return StructuredResult(ok=True, detail="json ok")

    schemas = data.get("schemas") if isinstance(data.get("schemas"), Mapping) else data
    if schema_name and isinstance(schemas, Mapping) and schema_name in schemas:
        schema = schemas[schema_name]
        if isinstance(schema, Mapping) and "required" in schema:
            required = schema.get("required") or []
            if isinstance(payload, Mapping):
                missing = [k for k in required if k not in payload]
                if missing:
                    return StructuredResult(ok=False, detail=f"missing keys: {missing}")
    return StructuredResult(ok=True, detail="json+schema ok")
