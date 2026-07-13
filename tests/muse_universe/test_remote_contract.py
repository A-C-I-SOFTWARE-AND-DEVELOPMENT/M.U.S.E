from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from plugins.muse_universe.models import (
    AuthorizationDecision,
    CommandResult,
    ProvenanceRecord,
    UniverseCommand,
)
from plugins.muse_universe.remote import (
    AuthoritySelectionError,
    MAX_TIMEOUT_SECONDS,
    RemoteAuthorizationError,
    RemoteConflictError,
    RemoteUnavailableError,
    SupabaseUniverseAdapter,
)
from plugins.muse_universe.service import COMMANDS
from plugins.muse_universe.store import ConflictError


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "supabase/migrations/202607120001_muse_universe.sql"
EDGE = ROOT / "supabase/functions/muse-universe/index.ts"
CONTRACT = ROOT / "supabase/functions/_shared/universe-contract.ts"


def test_migration_has_rls_and_immutable_events():
    sql = MIGRATION.read_text(encoding="utf-8")
    lowered = sql.lower()
    for table in (
        "universe_realms",
        "universe_memberships",
        "universe_events",
        "universe_entities",
        "universe_command_results",
    ):
        assert f"alter table public.{table} enable row level security" in lowered
    assert "prevent_universe_event_update" in sql
    assert "prevent_universe_event_delete" in sql
    assert "unique (stream_type, stream_id, stream_version)" in lowered


def test_migration_rederives_identity_scope_and_stream_metadata():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "auth.uid()" in sql
    assert "universe_required_scope" in sql
    assert "universe_command_descriptor" in sql
    assert "MUSE_ACTOR_MISMATCH" in sql
    assert "MUSE_VERSION_CONFLICT" in sql
    assert "security definer" in sql.lower()
    assert "revoke insert, update, delete on public.universe_events" in sql.lower()


def test_edge_function_does_not_trust_client_roles_or_log_bodies():
    source = EDGE.read_text(encoding="utf-8")
    assert "payload.roles" not in source
    assert "auth.getUser" in source
    assert "execute_universe_command" in source
    assert "console.log" not in source
    assert "console.error" not in source
    assert "MUSE_FIRST_PARTY_ORIGINS" in source
    assert '"*"' not in source


def test_shared_contract_is_bounded_and_rejects_secret_shapes():
    source = CONTRACT.read_text(encoding="utf-8")
    assert "MAX_COMMAND_BYTES = 64 * 1024" in source
    assert "Number.isSafeInteger" in source
    assert "credential-shaped" in source
    assert "__muse_internal__" in source


def test_remote_adapter_preserves_command_identity_and_user_bearer():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "event": {"event_id": "evt_1", "stream_version": 1},
                "entity": {"id": "wld_1", "version": 1},
                "idempotent_replay": False,
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = SupabaseUniverseAdapter(
        "https://realm.example/functions/v1/muse-universe",
        "user-token",
        "rlm_network",
        client=client,
    )
    adapter.execute(
        "world.create",
        {"id": "wld_1", "name": "Asterion"},
        0,
        "cmd_world_1",
        correlation_id="corr_1",
    )
    assert seen["authorization"] == "Bearer user-token"
    assert seen["body"] == {
        "command_id": "cmd_world_1",
        "command_type": "world.create",
        "realm_id": "rlm_network",
        "expected_version": 0,
        "payload": {"id": "wld_1", "name": "Asterion"},
        "simulation": False,
        "correlation_id": "corr_1",
    }


def test_remote_adapter_preserves_reconnect_cursor():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["realm_id"] == "rlm_network"
        assert request.url.params["cursor"] == "41"
        assert request.url.params["limit"] == "50"
        return httpx.Response(200, json={"events": [{"sequence": 42}], "cursor": 42})

    adapter = SupabaseUniverseAdapter(
        "https://realm.example/functions/v1/muse-universe",
        "user-token",
        "rlm_network",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    events, cursor = adapter.events_since(41, limit=50)
    assert events == [{"sequence": 42}]
    assert cursor == 42


def test_version_conflict_maps_without_authority_fallback():
    class Local:
        calls = 0

        def snapshot(self, actor_id: str | None, realm_id: str):
            self.calls += 1
            return {"realms": [{"id": realm_id, "owner_id": actor_id}]}

    local = Local()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"error": "MUSE_VERSION_CONFLICT"})

    adapter = SupabaseUniverseAdapter(
        "https://realm.example/functions/v1/muse-universe",
        "user-token",
        "rlm_network",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        local_adapter=local,
        local_realm_id="rlm_local",
    )
    with pytest.raises(RemoteConflictError):
        adapter.execute("world.create", {"id": "wld_1"}, 1, "cmd_1")
    assert local.calls == 0
    assert adapter.local_snapshot("owner", "rlm_local")["realms"][0]["id"] == "rlm_local"
    with pytest.raises(AuthoritySelectionError):
        adapter.local_snapshot("owner", "rlm_network")


def test_network_failure_never_silently_switches_to_local():
    class Local:
        calls = 0

        def snapshot(self, actor_id: str | None, realm_id: str):
            self.calls += 1
            return {}

    local = Local()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    adapter = SupabaseUniverseAdapter(
        "https://realm.example/functions/v1/muse-universe",
        "user-token",
        "rlm_network",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        local_adapter=local,
        local_realm_id="rlm_local",
    )
    with pytest.raises(RemoteUnavailableError):
        adapter.snapshot()
    assert local.calls == 0


def test_project_keys_are_rejected_as_user_tokens():
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(b'{"role":"service_role"}').decode().rstrip("=")
    adapter = SupabaseUniverseAdapter(
        "https://realm.example/functions/v1/muse-universe",
        f"{header}.{payload}.signature",
        "rlm_network",
        client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200))),
    )
    with pytest.raises(RemoteAuthorizationError):
        adapter.snapshot()


def _modern_command(**overrides: object) -> UniverseCommand:
    data: dict[str, Any] = {
        "command_id": "cmd_remote_1",
        "command_type": "realm.create",
        "realm_id": "rlm_network",
        "actor_id": "client-claimed-actor",
        "stream_type": "realm",
        "stream_id": "rlm_network",
        "expected_version": 0,
        "payload": {"id": "rlm_network", "name": "Network", "mode": "team"},
        "authorization": AuthorizationDecision(
            allowed=True,
            reason="client claim must be discarded",
            scopes=("*",),
        ),
        "provenance": ProvenanceRecord(
            source="client claim must be discarded",
            confidence=1.0,
        ),
        "causation_id": "cause_remote_1",
        "correlation_id": "corr_remote_1",
    }
    data.update(overrides)
    return UniverseCommand(**data)


def _modern_result() -> dict[str, Any]:
    event = {
        "sequence": 11,
        "event_id": "evt_remote_1",
        "schema_version": 1,
        "event_type": "realm.created",
        "realm_id": "rlm_network",
        "actor_id": "ply_remote_owner",
        "stream_type": "realm",
        "stream_id": "rlm_network",
        "stream_version": 1,
        "authorization": {
            "allowed": True,
            "reason": "authenticated realm owner",
            "scopes": ["*"],
            "owner_gate": "not_required",
        },
        "causation_id": "cause_remote_1",
        "correlation_id": "corr_remote_1",
        "occurred_at": "2026-07-12T12:00:00+00:00",
        "payload": {"id": "rlm_network", "name": "Network", "mode": "team"},
        "provenance": {
            "source": "supabase_authenticated_user",
            "evidence": ["auth:verified"],
            "confidence": 1.0,
            "signature": None,
        },
        "simulation": False,
        "rollback": {},
    }
    return {
        "event": event,
        "entity": {
            "id": "rlm_network",
            "entity_type": "realm",
            "realm_id": "rlm_network",
            "version": 1,
            "updated_at": "2026-07-12T12:00:00+00:00",
            "simulation": False,
            "name": "Network",
            "mode": "team",
        },
        "idempotent_replay": False,
    }


def test_all_authoritative_tables_force_rls_and_revoke_mutation():
    lowered = MIGRATION.read_text(encoding="utf-8").lower()
    for table in (
        "universe_realms",
        "universe_memberships",
        "universe_events",
        "universe_entities",
        "universe_command_results",
    ):
        assert f"alter table public.{table} force row level security" in lowered
    assert "revoke insert, update, delete, truncate" in lowered
    assert "from anon, authenticated" in lowered
    assert "v_current_version > 0 and not v_current_public" in lowered
    assert "'rollback', case when v_is_public then '{}'::jsonb" in lowered


def test_remote_descriptor_matches_every_local_command_event_pair():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    contract = CONTRACT.read_text(encoding="utf-8")
    for command_type, (stream_type, event_type) in COMMANDS.items():
        assert (
            f"when '{command_type}' then return query select "
            f"'{stream_type}', '{event_type}'"
        ) in sql
        assert (
            f'"{command_type}": {{ streamType: "{stream_type}", '
            f'eventType: "{event_type}"'
        ) in contract


def test_modern_adapter_strips_client_authority_and_preserves_stream_identity():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/functions/v1/muse-universe/commands"
        assert request.headers["authorization"] == "Bearer caller-user-jwt"
        assert request.headers["apikey"] == "public-anon-key"
        sent = json.loads(request.content)
        assert sent["command_id"] == "cmd_remote_1"
        assert sent["stream_id"] == "rlm_network"
        assert "actor_id" not in sent
        assert "authorization" not in sent
        assert "provenance" not in sent
        assert "stream_type" not in sent
        return httpx.Response(200, json=_modern_result())

    with SupabaseUniverseAdapter(
        "https://project.supabase.co",
        "caller-user-jwt",
        anon_key="public-anon-key",
        timeout=4.0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    ) as adapter:
        result = adapter.execute(_modern_command())

    assert isinstance(result, CommandResult)
    assert result.event.actor_id == "ply_remote_owner"


def test_version_conflict_preserves_expected_and_current_versions():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                "error": {
                    "code": "version_conflict",
                    "message": "stream version conflict",
                    "expected_version": 0,
                    "current_version": 3,
                }
            },
        )

    adapter = SupabaseUniverseAdapter(
        "https://project.supabase.co",
        "caller-user-jwt",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(ConflictError) as caught:
        adapter.execute(_modern_command())
    assert caught.value.expected_version == 0
    assert caught.value.current_version == 3


def test_modern_event_page_preserves_server_cursor_and_realm_version():
    event = _modern_result()["event"]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["since"] == "7"
        return httpx.Response(
            200,
            json={
                "events": [event],
                "cursor": 11,
                "realm_version": 4,
                "server_time": "2026-07-12T12:01:00+00:00",
            },
        )

    adapter = SupabaseUniverseAdapter(
        "https://project.supabase.co",
        "caller-user-jwt",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    page = adapter.events_since("rlm_network", 7, limit=25)
    assert page.cursor == 11
    assert page.realm_version == 4
    assert page.events[0].sequence == 11


def test_remote_timeout_must_stay_inside_the_bounded_contract():
    with pytest.raises(ValueError, match="timeout"):
        SupabaseUniverseAdapter(
            "https://project.supabase.co",
            "caller-user-jwt",
            timeout=MAX_TIMEOUT_SECONDS + 0.01,
        )
