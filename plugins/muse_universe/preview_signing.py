"""Short-lived, path- and origin-bound private preview claims."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable
from urllib.parse import unquote

from hermes_constants import get_hermes_home


class PreviewTokenError(ValueError):
    pass


@dataclass(frozen=True)
class PreviewClaims:
    lease_id: str
    path_prefix: str
    issued_at: int
    expires_at: int
    nonce: str
    origin: str
    visibility: str = "private"
    production_eligible: bool = False


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _path_prefix(value: str) -> str:
    if not isinstance(value, str) or not value.startswith("/"):
        raise PreviewTokenError("path prefix must be absolute")
    decoded = unquote(value)
    if "\\" in decoded or "\x00" in decoded:
        raise PreviewTokenError("path prefix contains forbidden characters")
    path = PurePosixPath(decoded)
    if ".." in path.parts:
        raise PreviewTokenError("path prefix cannot traverse")
    normalized = "/" + "/".join(part for part in path.parts if part not in {"/", ""})
    return normalized.rstrip("/") + "/"


class PreviewSigner:
    def __init__(
        self,
        secret: bytes | None = None,
        *,
        secret_path: str | Path | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.clock = clock
        self._secret = secret or self._load_secret(secret_path)
        if len(self._secret) < 32:
            raise ValueError("preview signing secret must be at least 32 bytes")

    @staticmethod
    def _load_secret(secret_path: str | Path | None) -> bytes:
        path = Path(secret_path) if secret_path else Path(get_hermes_home()) / "universe/private/preview-signing.key"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            secret = path.read_bytes()
            if len(secret) < 32:
                raise ValueError("stored preview signing secret is invalid")
            return secret
        secret = secrets.token_bytes(32)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(path, flags, 0o600)
        try:
            os.write(descriptor, secret)
        finally:
            os.close(descriptor)
        return secret

    def issue(
        self,
        lease_id: str,
        path_prefix: str,
        *,
        ttl_seconds: int = 300,
        now: int | None = None,
        origin: str = "muse://desktop",
    ) -> str:
        if not isinstance(lease_id, str) or not lease_id:
            raise PreviewTokenError("lease_id is required")
        if not isinstance(origin, str) or "://" not in origin:
            raise PreviewTokenError("preview origin must be an absolute origin")
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 900:
            raise PreviewTokenError("preview TTL must be between 1 and 900 seconds")
        issued = int(self.clock()) if now is None else now
        if type(issued) is not int:
            raise PreviewTokenError("issued time must be an integer")
        payload = {
            "lease_id": lease_id,
            "path_prefix": _path_prefix(path_prefix),
            "issued_at": issued,
            "expires_at": issued + ttl_seconds,
            "nonce": secrets.token_urlsafe(16),
            "origin": origin,
            "visibility": "private",
            "production_eligible": False,
        }
        encoded = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        signature = _b64(hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).digest())
        return f"{encoded}.{signature}"

    def verify(
        self,
        token: str,
        request_path: str,
        *,
        now: int | None = None,
        origin: str = "muse://desktop",
    ) -> PreviewClaims:
        try:
            encoded, supplied_signature = token.split(".", 1)
            expected_signature = _b64(
                hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).digest()
            )
            if not hmac.compare_digest(supplied_signature, expected_signature):
                raise PreviewTokenError("invalid preview signature")
            payload = json.loads(_unb64(encoded))
        except PreviewTokenError:
            raise
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PreviewTokenError("malformed preview token") from exc
        if not isinstance(payload, dict):
            raise PreviewTokenError("malformed preview claims")
        required = {
            "lease_id", "path_prefix", "issued_at", "expires_at", "nonce",
            "origin", "visibility", "production_eligible",
        }
        if set(payload) != required:
            raise PreviewTokenError("preview claim fields are invalid")
        checked_at = int(self.clock()) if now is None else now
        if (
            type(checked_at) is not int
            or type(payload["issued_at"]) is not int
            or type(payload["expires_at"]) is not int
        ):
            raise PreviewTokenError("preview timestamps are invalid")
        if payload["issued_at"] > checked_at:
            raise PreviewTokenError("preview token is not yet valid")
        if payload["expires_at"] <= payload["issued_at"]:
            raise PreviewTokenError("preview token lifetime is invalid")
        if payload["expires_at"] - payload["issued_at"] > 900:
            raise PreviewTokenError("preview token lifetime is invalid")
        if checked_at > payload["expires_at"]:
            raise PreviewTokenError("preview token expired")
        if payload["origin"] != origin:
            raise PreviewTokenError("preview origin mismatch")
        prefix = _path_prefix(payload["path_prefix"])
        requested = _path_prefix(request_path if request_path.endswith("/") else request_path + "/")
        if not requested.startswith(prefix):
            raise PreviewTokenError("preview path is outside the claim")
        if payload["visibility"] != "private" or payload["production_eligible"] is not False:
            raise PreviewTokenError("preview claim cannot authorize production")
        return PreviewClaims(**payload)


__all__ = ["PreviewClaims", "PreviewSigner", "PreviewTokenError"]
