"""Revision-bound source metadata for visual selection and structured edits."""
from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping


class SourceRevisionConflict(RuntimeError):
    pass


_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")
_PROPERTY = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,199}$")
_BLOCKED_NAMES = frozenset({".env", "auth.json", "credentials.json", "secrets.json"})
_BLOCKED_PARTS = frozenset({"credential", "password", "secret", "api_key", "access_token", "private_key"})


@dataclass(frozen=True)
class SourceRef:
    component_id: str
    file: str
    line: int
    property_path: str
    revision: str


class SourceRegistry:
    def __init__(
        self,
        workspace: str | Path,
        *,
        revision: str | None = None,
        allowed_properties: Mapping[str, tuple[str, ...]] | None = None,
    ) -> None:
        self.workspace = Path(workspace).resolve()
        if not self.workspace.is_dir():
            raise ValueError("workspace must exist")
        self.revision = revision or self._git_revision()
        self._allowed_properties = dict(allowed_properties or {})
        self._refs: dict[str, SourceRef] = {}

    def register(
        self,
        component_id: str,
        file: str | Path,
        line: int,
        property_path: str,
    ) -> SourceRef:
        if not _COMPONENT.fullmatch(component_id):
            raise ValueError("component_id is invalid")
        if type(line) is not int or line < 1:
            raise ValueError("line must be a 1-based integer")
        if not _PROPERTY.fullmatch(property_path) or _is_sensitive(property_path):
            raise ValueError("property path is invalid or sensitive")
        configured = self._allowed_properties.get(component_id)
        if configured is not None and property_path not in configured:
            raise ValueError("property path is not allowlisted")
        target = (self.workspace / file).resolve()
        if not target.is_relative_to(self.workspace):
            raise ValueError("source path escapes workspace")
        lowered_name = target.name.lower()
        if (
            lowered_name in _BLOCKED_NAMES
            or lowered_name.startswith(".env.")
            or any(_is_sensitive(part) for part in target.parts)
        ):
            raise ValueError("credential/config source cannot be mapped")
        if target.exists() and target.is_symlink():
            raise ValueError("symlink source mappings are forbidden")
        relative = target.relative_to(self.workspace).as_posix()
        ref = SourceRef(component_id, relative, line, property_path, self.revision)
        self._refs[component_id] = ref
        return ref

    def resolve(self, component_id: str, *, revision: str | None = None) -> SourceRef:
        requested_revision = self.revision if revision is None else revision
        if requested_revision != self.revision:
            raise SourceRevisionConflict(
                f"source map revision {self.revision} does not match {requested_revision}"
            )
        try:
            ref = self._refs[component_id]
        except KeyError as exc:
            raise KeyError(f"unknown component: {component_id}") from exc
        target = (self.workspace / ref.file).resolve()
        if not target.is_relative_to(self.workspace):
            raise ValueError("resolved source escaped workspace")
        return ref

    def snapshot(self) -> tuple[dict[str, object], ...]:
        return tuple(asdict(self._refs[key]) for key in sorted(self._refs))

    def _git_revision(self) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.workspace), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        revision = result.stdout.strip()
        return revision if result.returncode == 0 and revision else "unversioned"


def _is_sensitive(value: str) -> bool:
    normalized = value.lower().replace("-", "_").replace(".", "_")
    return any(part in normalized for part in _BLOCKED_PARTS)


__all__ = ["SourceRef", "SourceRegistry", "SourceRevisionConflict"]
