"""Clients for the code-intelligence sources.

  * OSV.dev   — known-vulnerability query  (api.osv.dev, POST)
  * deps.dev  — package licenses/versions   (api.deps.dev, GET)
  * Piston    — sandboxed code execution    (emkc.org, POST)

All key-less and host-pinned via the shared
:class:`~tools.http_client.PublicApiClient`. Methods raise
:class:`~tools.http_client.HttpClientError` on failure.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

from tools.http_client import PublicApiClient

OSV_HOST = "api.osv.dev"
DEPSDEV_HOST = "api.deps.dev"
PISTON_HOST = "emkc.org"
ALLOWED_HOSTS = (OSV_HOST, DEPSDEV_HOST, PISTON_HOST)

OSV_QUERY_URL = f"https://{OSV_HOST}/v1/query"
PISTON_EXECUTE_URL = f"https://{PISTON_HOST}/api/v2/piston/execute"

# Friendly aliases → OSV ecosystem names.
OSV_ECOSYSTEMS = {
    "pypi": "PyPI",
    "pip": "PyPI",
    "python": "PyPI",
    "npm": "npm",
    "node": "npm",
    "cargo": "crates.io",
    "crates": "crates.io",
    "crates.io": "crates.io",
    "rust": "crates.io",
    "go": "Go",
    "golang": "Go",
    "maven": "Maven",
    "java": "Maven",
    "rubygems": "RubyGems",
    "gems": "RubyGems",
    "ruby": "RubyGems",
    "nuget": "NuGet",
    "packagist": "Packagist",
    "composer": "Packagist",
    "php": "Packagist",
}

# Friendly aliases → deps.dev system names.
DEPSDEV_SYSTEMS = {
    "pypi": "pypi",
    "pip": "pypi",
    "python": "pypi",
    "npm": "npm",
    "node": "npm",
    "cargo": "cargo",
    "crates": "cargo",
    "crates.io": "cargo",
    "rust": "cargo",
    "go": "go",
    "golang": "go",
    "maven": "maven",
    "java": "maven",
    "nuget": "nuget",
}


class CodeintelClient:
    def __init__(self, http: Optional[PublicApiClient] = None) -> None:
        self._http = http or PublicApiClient(allowed_hosts=ALLOWED_HOSTS)

    # -- OSV ------------------------------------------------------------------

    @staticmethod
    def resolve_osv_ecosystem(name: str) -> str:
        return OSV_ECOSYSTEMS.get(name.strip().lower(), name.strip())

    def osv_query(self, name: str, ecosystem: str, version: Optional[str]) -> Any:
        body: dict[str, Any] = {
            "package": {"name": name, "ecosystem": ecosystem},
        }
        if version:
            body["version"] = version
        return self._http.post_json(OSV_QUERY_URL, json_body=body)

    # -- deps.dev -------------------------------------------------------------

    @staticmethod
    def resolve_depsdev_system(name: str) -> str:
        return DEPSDEV_SYSTEMS.get(name.strip().lower(), name.strip().lower())

    def depsdev(self, system: str, name: str, version: Optional[str]) -> Any:
        # deps.dev requires the package name URL-encoded (incl. '/' and '@').
        enc = quote(name, safe="")
        base = f"https://{DEPSDEV_HOST}/v3/systems/{system}/packages/{enc}"
        if version:
            return self._http.get_json(f"{base}/versions/{quote(version, safe='')}")
        return self._http.get_json(base)

    # -- Piston ---------------------------------------------------------------

    def piston_execute(
        self,
        language: str,
        content: str,
        *,
        version: str = "*",
        stdin: str = "",
    ) -> Any:
        body = {
            "language": language,
            "version": version,
            "files": [{"content": content}],
            "stdin": stdin,
        }
        return self._http.post_json(PISTON_EXECUTE_URL, json_body=body)
