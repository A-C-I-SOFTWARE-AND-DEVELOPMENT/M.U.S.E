"""Regression checks for the hosted relay's explicit policy boundary."""

from pathlib import Path


RELAY = (
    Path(__file__).resolve().parents[2] / "api" / "gateway" / "[...path].ts"
)


def _service_policy(source: str) -> str:
    return source.split(
        "export const SERVICE_RELAY_ROUTES", 1
    )[1].split("export function relayRouteAllowed", 1)[0]


def test_service_relay_policy_allows_only_scoped_control_routes() -> None:
    source = RELAY.read_text(encoding="utf-8")
    service = _service_policy(source)
    for required in (
        "runtime",
        "models",
        "model-routes",
        "schedules",
        "seats",
        "jobs",
        "approvals",
        "emergency-stop",
        "agent",
    ):
        assert required in service
    for forbidden in (
        "secrets",
        "learning/export",
        "oauth",
        "coding",
        "agent\\/chat",
        "publish",
        "DELETE",
    ):
        assert forbidden not in service


def test_relay_rejects_unlisted_and_traversal_paths_before_fetch() -> None:
    source = RELAY.read_text(encoding="utf-8")
    assert "relayRouteAllowed(routePolicy, req.method, parsed.pathname)" in source
    assert "segment === '..'" in source
    assert "decodeURIComponent(encoded)" in source
    assert "redirect: 'manual'" in source


def test_service_mutations_require_request_id_and_forward_identity() -> None:
    source = RELAY.read_text(encoding="utf-8")
    assert "x-muse-service-authorization" in source
    assert "request id required" in source
    assert "headers.Authorization = `Bearer ${serviceToken}`" in source
    assert "headers['X-Muse-Request-Id'] = requestId" in source
