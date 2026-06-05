"""Supabase memory provider — persistent recall backed by a Postgres table.

A :class:`~agent.memory_provider.MemoryProvider` that stores each completed turn
in a Supabase table via PostgREST and surfaces the most recent turns for the
session before the next reply. Recall is **recency-based** (most recent N turns
for the session); semantic / pgvector search is a documented follow-up. Built on
``httpx`` (a base dep) — no SDK and no dependency on the ``supabase`` *tool*
plugin, so it loads cleanly under the memory-plugin discovery loader.

Activate with ``memory.provider: supabase`` in ``~/.hermes/config.yaml``.

Config (env, or ``$HERMES_HOME/supabase_memory.json``):
  ``SUPABASE_URL``           — project URL ``https://<ref>.supabase.co``  (required)
  ``SUPABASE_ANON_KEY``      — anon key                                   (required)
  ``SUPABASE_MEMORY_TABLE``  — table name (default ``hermes_memory``)

Create the table once — e.g. via the ``supabase`` tool plugin's
``supabase_apply_migration``:

    create table if not exists hermes_memory (
      id bigserial primary key,
      session_id text not null,
      user_content text,
      assistant_content text,
      created_at timestamptz default now()
    );
    create index if not exists hermes_memory_session_idx
      on hermes_memory (session_id, created_at desc);

The anon key is used (row-level security applies); content is the user's own
conversation stored in the user's own project. Network calls degrade silently —
a memory backend must never break the turn loop.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)

DEFAULT_TABLE = "hermes_memory"
_RECALL_LIMIT = 6
_TIMEOUT = 10.0


def _load_config() -> dict:
    """Env vars first, then ``$HERMES_HOME/supabase_memory.json`` overrides."""
    cfg = {
        "url": (os.environ.get("SUPABASE_URL") or "").rstrip("/"),
        "key": os.environ.get("SUPABASE_ANON_KEY") or "",
        "table": os.environ.get("SUPABASE_MEMORY_TABLE") or DEFAULT_TABLE,
    }
    try:
        from hermes_constants import get_hermes_home

        path = get_hermes_home() / "supabase_memory.json"
        if path.exists():
            file_cfg = json.loads(path.read_text(encoding="utf-8"))
            cfg.update({k: v for k, v in file_cfg.items() if v})
    except Exception:  # pragma: no cover — home/path resolution varies
        pass
    return cfg


class SupabaseMemoryProvider(MemoryProvider):
    """Recency-based persistent memory over a Supabase PostgREST table."""

    def __init__(self) -> None:
        self._cfg: dict = {}
        self._session_id = ""
        self._ready = False
        # Injectable for tests (an httpx.Client with a MockTransport); when None
        # each call uses a short-lived client.
        self._client: Optional[httpx.Client] = None

    @property
    def name(self) -> str:
        return "supabase"

    # -- lifecycle ---------------------------------------------------------

    def is_available(self) -> bool:
        cfg = _load_config()
        return bool(cfg.get("url") and cfg.get("key"))

    def initialize(self, session_id: str, **kwargs) -> None:
        # Non-primary contexts (cron system prompts, flush) must not pollute
        # the user's conversational memory.
        if kwargs.get("agent_context", "primary") in {"cron", "flush"}:
            return
        self._cfg = _load_config()
        self._session_id = session_id or ""
        self._ready = bool(self._cfg.get("url") and self._cfg.get("key"))

    def on_session_switch(
        self,
        new_session_id: str,
        *,
        parent_session_id: str = "",
        reset: bool = False,
        **kwargs,
    ) -> None:
        self._session_id = new_session_id or self._session_id

    def system_prompt_block(self) -> str:
        if not self._ready:
            return ""
        return (
            "# Supabase memory\n"
            "Persistent recall is active: recent turns from past sessions are "
            "surfaced automatically before each reply."
        )

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        # Context-only provider — recall is injected via prefetch(), no tools.
        return []

    # -- recall / persist --------------------------------------------------

    def _http(self) -> httpx.Client:
        return self._client or httpx.Client(timeout=_TIMEOUT)

    def _headers(self, *, write: bool = False) -> dict[str, str]:
        key = self._cfg.get("key", "")
        h = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "hermes-agent/supabase-memory",
        }
        if write:
            h["Content-Type"] = "application/json"
            h["Prefer"] = "return=minimal"
        return h

    def _table_url(self) -> str:
        return f"{self._cfg['url']}/rest/v1/{self._cfg.get('table', DEFAULT_TABLE)}"

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if not self._ready:
            return ""
        sid = session_id or self._session_id
        params = {
            "select": "user_content,assistant_content,created_at",
            "order": "created_at.desc",
            "limit": str(_RECALL_LIMIT),
        }
        if sid:
            params["session_id"] = f"eq.{sid}"
        client = self._http()
        owns = self._client is None
        try:
            resp = client.get(self._table_url(), headers=self._headers(), params=params)
            if resp.status_code >= 400:
                return ""
            rows = resp.json() if resp.text else []
        except Exception:
            return ""
        finally:
            if owns:
                client.close()
        if not isinstance(rows, list) or not rows:
            return ""
        lines: list[str] = []
        for row in reversed(rows):  # oldest-first for readability
            if not isinstance(row, dict):
                continue
            user = (row.get("user_content") or "").strip()
            asst = (row.get("assistant_content") or "").strip()
            if user:
                lines.append(f"User: {user}")
            if asst:
                lines.append(f"Assistant: {asst}")
        if not lines:
            return ""
        return "Relevant past conversation (Supabase memory):\n" + "\n".join(lines)

    def sync_turn(
        self, user_content: str, assistant_content: str, *, session_id: str = ""
    ) -> None:
        if not self._ready:
            return
        sid = session_id or self._session_id
        body = {
            "session_id": sid,
            "user_content": user_content,
            "assistant_content": assistant_content,
        }
        client = self._http()
        owns = self._client is None
        try:
            client.post(self._table_url(), headers=self._headers(write=True), json=body)
        except Exception:
            pass  # a memory write must never break the turn loop
        finally:
            if owns:
                client.close()

    # -- setup -------------------------------------------------------------

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "url",
                "description": "Supabase project URL (https://<ref>.supabase.co)",
                "secret": False,
                "required": True,
                "env_var": "SUPABASE_URL",
                "url": "https://app.supabase.com",
            },
            {
                "key": "key",
                "description": "Supabase anon key",
                "secret": True,
                "required": True,
                "env_var": "SUPABASE_ANON_KEY",
            },
            {
                "key": "table",
                "description": f"Memory table name (default: {DEFAULT_TABLE})",
                "secret": False,
                "required": False,
                "default": DEFAULT_TABLE,
                "env_var": "SUPABASE_MEMORY_TABLE",
            },
        ]


def register(ctx) -> None:
    """Memory-plugin entry point — register the provider instance."""
    ctx.register_memory_provider(SupabaseMemoryProvider())
