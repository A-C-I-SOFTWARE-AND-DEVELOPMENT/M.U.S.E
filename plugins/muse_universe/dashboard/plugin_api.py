"""Authenticated dashboard wrappers for the shared Universe API.

The dashboard host mounts this router below ``/api/plugins/muse-universe``;
its global API middleware requires the ephemeral dashboard session token.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from gateway.cockpit.handlers import Request as CockpitRequest
from plugins.muse_universe import api


router = APIRouter()


def _response(response) -> JSONResponse:
    return JSONResponse(status_code=response.status, content=response.payload)


@router.get("/status")
async def status() -> JSONResponse:
    return _response(api.handle_status(CockpitRequest(method="GET", path="/status")))


@router.get("/catalog")
async def catalog() -> JSONResponse:
    return _response(api.handle_catalog(CockpitRequest(method="GET", path="/catalog")))


@router.get("/snapshot")
async def snapshot(
    realm_id: str | None = None,
    actor_id: str | None = None,
) -> JSONResponse:
    query: dict[str, str] = {}
    if realm_id is not None:
        query["realm_id"] = realm_id
    if actor_id is not None:
        query["actor_id"] = actor_id
    return _response(
        api.handle_snapshot(
            CockpitRequest(
                method="GET",
                path="/snapshot",
                query=query,
            )
        )
    )


@router.get("/events")
async def events(
    realm_id: str | None = None,
    since: str | None = None,
) -> JSONResponse:
    query: dict[str, str] = {}
    if realm_id is not None:
        query["realm_id"] = realm_id
    if since is not None:
        query["since"] = since
    return _response(
        api.handle_events(
            CockpitRequest(method="GET", path="/events", query=query)
        )
    )


@router.get("/entities/{entity_type}/{entity_id}")
async def entity(
    entity_type: str,
    entity_id: str,
    actor_id: str | None = None,
    realm_id: str | None = None,
) -> JSONResponse:
    query: dict[str, str] = {}
    if actor_id is not None:
        query["actor_id"] = actor_id
    if realm_id is not None:
        query["realm_id"] = realm_id
    return _response(
        api.handle_entity(
            CockpitRequest(
                method="GET",
                path=f"/entities/{entity_type}/{entity_id}",
                query=query,
                path_params={
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                },
            )
        )
    )


@router.post("/commands")
async def commands(body: dict[str, Any]) -> JSONResponse:
    return _response(
        api.handle_commands(
            CockpitRequest(method="POST", path="/commands", body=body)
        )
    )


@router.post("/reconcile")
async def reconcile(body: dict[str, Any] | None = None) -> JSONResponse:
    return _response(
        api.handle_reconcile(
            CockpitRequest(method="POST", path="/reconcile", body=body or {})
        )
    )
