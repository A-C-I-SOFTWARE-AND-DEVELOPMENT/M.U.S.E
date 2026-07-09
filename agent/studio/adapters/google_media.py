"""Google Vertex AI media adapters for Axiom Studio.

Supports Imagen (image/storyboard frames) and Veo (video clips) through
Vertex AI REST endpoints, with safe stub fallback when Google credentials are
not present. The adapters intentionally use only stdlib urllib/subprocess so
Hermes does not need a heavyweight Google SDK in the core environment.

Required for real calls:
  GOOGLE_CLOUD_PROJECT or GOOGLE_PROJECT_ID
  GOOGLE_CLOUD_LOCATION (default: us-central1)
  one of:
    GOOGLE_OAUTH_ACCESS_TOKEN
    GOOGLE_APPLICATION_CREDENTIALS (service-account JSON; token is minted)
    gcloud authenticated on PATH (uses `gcloud auth print-access-token`)

Optional:
  GOOGLE_IMAGEN_MODEL (default: imagen-4.0-generate-preview-06-06)
  GOOGLE_VEO_MODEL (default: veo-3.0-generate-preview)
  GOOGLE_VEO_GCS_BUCKET (recommended for video output)
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from agent.studio.adapters.base import Adapter, default_registry
from agent.studio.types import Provider


_LOCATION_DEFAULT = "us-central1"
_IMAGEN_MODEL_DEFAULT = "imagen-4.0-generate-preview-06-06"
_VEO_MODEL_DEFAULT = "veo-3.0-generate-preview"


def _project() -> str:
    return (os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GOOGLE_PROJECT_ID") or "").strip()


def _location() -> str:
    return (os.environ.get("GOOGLE_CLOUD_LOCATION") or _LOCATION_DEFAULT).strip()


def _vertex_base() -> str:
    loc = _location()
    host = f"{loc}-aiplatform.googleapis.com" if loc != "global" else "aiplatform.googleapis.com"
    return f"https://{host}/v1/projects/{_project()}/locations/{loc}/publishers/google/models"


def _gcloud_token() -> Optional[str]:
    try:
        proc = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    token = proc.stdout.strip()
    return token if proc.returncode == 0 and token else None


def _service_account_token() -> Optional[str]:
    """Mint an OAuth token from GOOGLE_APPLICATION_CREDENTIALS without google-auth.

    This path uses PyJWT when available (already in Hermes core). If PyJWT is not
    available for any reason, return None and let callers fall through to gcloud.
    """
    key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not key_path:
        return None
    p = Path(key_path)
    if not p.exists():
        return None
    try:
        import jwt  # type: ignore
    except Exception:
        return None
    try:
        info = json.loads(p.read_text(encoding="utf-8"))
        now = int(time.time())
        payload = {
            "iss": info["client_email"],
            "scope": "https://www.googleapis.com/auth/cloud-platform",
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now,
            "exp": now + 3600,
        }
        assertion = jwt.encode(payload, info["private_key"], algorithm="RS256")
        body = urllib.parse.urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("access_token")
    except Exception:
        return None


def _access_token() -> Optional[str]:
    return (
        os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN")
        or _service_account_token()
        or _gcloud_token()
    )


def google_vertex_available() -> bool:
    return bool(_project() and _access_token())


def _headers() -> Dict[str, str]:
    token = _access_token()
    if not token:
        raise RuntimeError("Google Vertex AI credentials not available")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }


def _post_json(url: str, payload: Dict[str, Any], timeout: float = 600.0) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"Vertex HTTP {exc.code}: {detail[:1200]}") from exc


def _get_json(url: str, timeout: float = 120.0) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers=_headers(), method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _save_json(workdir: Path, prefix: str, payload: Dict[str, Any]) -> str:
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / f"{prefix}_{int(time.time() * 1000)}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(out)


def _decode_b64_to_file(workdir: Path, prefix: str, b64: str, suffix: str) -> str:
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / f"{prefix}_{int(time.time() * 1000)}.{suffix}"
    out.write_bytes(base64.b64decode(b64))
    return str(out)


def _first_base64_image(response: Dict[str, Any]) -> Optional[str]:
    candidates: Iterable[Any] = (
        response.get("predictions")
        or response.get("instances")
        or response.get("images")
        or []
    )
    for item in candidates:
        if isinstance(item, dict):
            for key in ("bytesBase64Encoded", "image", "b64_json", "base64"):
                val = item.get(key)
                if isinstance(val, str) and len(val) > 100:
                    return val
    return None


class GoogleImagenAdapter(Adapter):
    """Vertex AI Imagen adapter for concept art / boards / key frames."""

    capability = "concept_art"
    provider = Provider.IMAGEN4 if hasattr(Provider, "IMAGEN4") else Provider.FLUX_PRO
    requires_env: List[str] = []
    est_unit_cost_usd = 0.04

    def available(self) -> bool:
        return google_vertex_available()

    def _real(self, prompt: str, workdir: Path, **kwargs):
        model = kwargs.get("model") or os.environ.get("GOOGLE_IMAGEN_MODEL") or _IMAGEN_MODEL_DEFAULT
        url = f"{_vertex_base()}/{model}:predict"
        width = int(kwargs.get("width", 1024))
        height = int(kwargs.get("height", 1024))
        sample_count = int(kwargs.get("sample_count", kwargs.get("units", 1)))
        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "sampleCount": sample_count,
                "aspectRatio": kwargs.get("aspect_ratio", kwargs.get("aspect", "16:9")),
                "outputOptions": {"mimeType": "image/png"},
                "personGeneration": kwargs.get("person_generation", "allow_adult"),
                "safetySetting": kwargs.get("safety_setting", "block_few"),
            },
        }
        # Some Imagen endpoints reject explicit dimensions; keep them as advisory
        # in the saved request, not mandatory endpoint fields.
        payload["parameters"]["axiomRequestedSize"] = {"width": width, "height": height}
        data = _post_json(url, payload, timeout=float(kwargs.get("timeout", 600)))
        artifacts: List[str] = []
        b64 = _first_base64_image(data)
        if b64:
            artifacts.append(_decode_b64_to_file(workdir, "imagen", b64, "png"))
        artifacts.append(_save_json(workdir, "imagen_response", data))
        return artifacts, f"Vertex Imagen {model} x{sample_count}"


class GoogleVeoAdapter(Adapter):
    """Vertex AI Veo adapter for shot clips.

    The endpoint is long-running. We save both the operation/result JSON and any
    direct base64 video payload returned. If Google returns GCS URIs, they remain
    in the JSON so downstream Cloud/gsutil download can fetch them without losing
    provenance.
    """

    capability = "video"
    provider = Provider.VEO3
    requires_env: List[str] = []
    est_unit_cost_usd = 0.75  # conservative budget line; exact Google price varies by Veo SKU/quality.

    def available(self) -> bool:
        return google_vertex_available()

    def _estimate_cost(self, **kwargs) -> float:
        return self.est_unit_cost_usd * max(1, int(kwargs.get("duration_s", 8)))

    def _real(self, prompt: str, workdir: Path, **kwargs):
        model = kwargs.get("model") or os.environ.get("GOOGLE_VEO_MODEL") or _VEO_MODEL_DEFAULT
        url = f"{_vertex_base()}/{model}:predictLongRunning"
        duration_s = int(kwargs.get("duration_s", 8))
        sample_count = int(kwargs.get("sample_count", kwargs.get("units", 1)))
        parameters: Dict[str, Any] = {
            "sampleCount": sample_count,
            "durationSeconds": duration_s,
            "aspectRatio": kwargs.get("aspect", "16:9"),
            "resolution": kwargs.get("resolution", "1080p"),
        }
        bucket = kwargs.get("gcs_bucket") or os.environ.get("GOOGLE_VEO_GCS_BUCKET")
        if bucket:
            parameters["storageUri"] = bucket if str(bucket).startswith("gs://") else f"gs://{bucket}"
        if kwargs.get("seed") is not None:
            parameters["seed"] = int(kwargs["seed"])
        payload = {"instances": [{"prompt": prompt}], "parameters": parameters}
        op = _post_json(url, payload, timeout=float(kwargs.get("submit_timeout", 180)))
        artifacts = [_save_json(workdir, "veo_operation", op)]

        op_name = op.get("name")
        result = op
        poll = bool(kwargs.get("poll", True))
        deadline = time.time() + float(kwargs.get("poll_timeout", 1800))
        while poll and op_name and not result.get("done") and time.time() < deadline:
            time.sleep(float(kwargs.get("poll_interval", 10)))
            result = _get_json(f"https://{_location()}-aiplatform.googleapis.com/v1/{op_name}")
        if result is not op:
            artifacts.append(_save_json(workdir, "veo_result", result))

        # Best-effort extraction for APIs that return inline video bytes.
        for container in (result.get("response") or {}).get("videos", []) or result.get("videos", []):
            if isinstance(container, dict):
                b64 = container.get("bytesBase64Encoded") or container.get("video") or container.get("base64")
                if isinstance(b64, str) and len(b64) > 100:
                    artifacts.append(_decode_b64_to_file(workdir, "veo_clip", b64, "mp4"))
        return artifacts, f"Vertex Veo {model} {duration_s}s x{sample_count}"


# Register above generic / free adapters when available; harmless in stub mode.
for cls in [GoogleImagenAdapter, GoogleVeoAdapter]:
    default_registry.register(cls(), priority=95)
