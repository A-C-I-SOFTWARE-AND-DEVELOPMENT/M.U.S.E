"""Public Vercel cloud server for M.U.S.E (hermes-agent).

This is a **dedicated, self-contained** FastAPI app that Vercel builds and
serves at the project's public URL. It is intentionally *not* the localhost
dashboard in ``hermes_cli/web_server.py`` — that app is a security-hardened
**admin** surface (config editing, env-var reveal, ephemeral session tokens
injected into the SPA HTML) meant to bind to loopback only. Exposing it on a
public Vercel URL would publish a secrets/config console to the internet, so
the cloud entrypoint is a separate, read-only, public-safe server instead.

Why a separate module (not ``hermes_cli.web_server:app``):
  * **Security** — no config, env, OAuth, or reveal endpoints are reachable.
  * **Build determinism** — it imports only ``fastapi`` plus the stdlib-only
    version constants from ``hermes_cli``. It does *not* drag in the whole
    first-party tree (gateway, agent, providers, …) or their third-party
    deps, so the Vercel install stays small and the cold start is fast.

Vercel locates this app via ``[tool.vercel] entrypoint = "vercel_app:app"`` in
``pyproject.toml`` and installs ``requirements.txt`` (fastapi + starlette +
pydantic). Vercel provides the ASGI host in production; ``uvicorn`` is only
used for the local ``__main__`` convenience runner below.
"""

from __future__ import annotations

# fastapi lives in the optional `web` extra (installed for the Vercel build via
# requirements.txt), so the strict lint env that runs `ty` doesn't resolve it —
# same as hermes_cli/web_server.py. Suppress the env-specific unresolved-import.
from fastapi import FastAPI  # ty: ignore[unresolved-import]
from fastapi.responses import HTMLResponse, JSONResponse  # ty: ignore[unresolved-import]

# Single source of truth for the version. hermes_cli/__init__.py is stdlib-only
# (just version constants + a Windows UTF-8 shim), so this import is cheap and
# import-safe on Vercel. Fall back gracefully if the package path isn't on
# sys.path for any reason — the cloud server must still boot. (ty narrows the
# imported names to their literal values, so the str fallbacks need the ignore.)
try:
    from hermes_cli import __version__, __release_date__
except Exception:  # pragma: no cover - defensive: never let the deploy 500
    __version__ = "unknown"  # ty: ignore[invalid-assignment]
    __release_date__ = "unknown"  # ty: ignore[invalid-assignment]

app = FastAPI(
    title="M.U.S.E — public cloud server",
    version=__version__,
    description=(
        "Read-only public endpoint for M.U.S.E (hermes-agent). The admin "
        "dashboard is loopback-only and is not served here."
    ),
)


def _info() -> dict:
    return {
        "service": "muse-cloud",
        "ok": True,
        "version": __version__,
        "release_date": __release_date__,
    }


@app.get("/health")
@app.get("/api/health")
def health() -> dict:
    """Liveness probe — safe to expose publicly."""
    return _info()


@app.get("/api/version")
def version() -> dict:
    """Report the running M.U.S.E version + release date."""
    return _info()


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    """Minimal public landing page.

    Deliberately carries no controls — the configuration/secret-management
    surface lives only in the loopback ``hermes dashboard`` app.
    """
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>M.U.S.E</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{
    margin: 0; min-height: 100vh; display: grid; place-items: center;
    background: #0b0d12; color: #e6e8ee;
    font: 16px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  }}
  main {{ text-align: center; padding: 2rem; }}
  h1 {{ font-size: 2.25rem; margin: 0 0 .5rem; letter-spacing: .04em; }}
  p {{ margin: .25rem 0; opacity: .8; }}
  code {{ background: #161a22; padding: .15rem .4rem; border-radius: .35rem; }}
  a {{ color: #8ab4ff; }}
</style>
</head>
<body>
<main>
  <h1>M.U.S.E</h1>
  <p>Public cloud server is live.</p>
  <p>Version <code>{__version__}</code> · released {__release_date__}</p>
  <p>Health: <a href="/api/health">/api/health</a></p>
</main>
</body>
</html>"""


@app.exception_handler(404)
async def _not_found(_request, _exc):  # type: ignore[no-untyped-def]
    return JSONResponse(status_code=404, content={"ok": False, "error": "not_found"})


if __name__ == "__main__":  # pragma: no cover - local convenience only
    import uvicorn  # ty: ignore[unresolved-import]

    uvicorn.run("vercel_app:app", host="127.0.0.1", port=8000, reload=True)
