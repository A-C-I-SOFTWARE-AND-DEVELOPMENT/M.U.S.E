"""Tests for YuanbaoAdapter.get_chat_info group metadata enrichment (T06).

The method is exercised with a fake ``self`` carrying a stub ``_group_query`` so
no WS connection / credentials are needed: one case where the live query returns
real group info, and one where it returns ``None`` (no connection) and the
prefix-derived fallback must be used.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from gateway.platforms.yuanbao import YuanbaoAdapter  # noqa: E402


@pytest.mark.asyncio
async def test_get_chat_info_group_enriched_from_api():
    raw = {
        "group_name": "Launch War Room",
        "member_count": 42,
        "owner_id": "u-123",
    }
    fake_self = SimpleNamespace(
        _group_query=SimpleNamespace(query_group_info_raw=AsyncMock(return_value=raw))
    )
    info = await YuanbaoAdapter.get_chat_info(fake_self, "group:abc123")
    assert info["type"] == "group"
    assert info["name"] == "Launch War Room"
    assert info["member_count"] == 42
    assert info["owner_id"] == "u-123"
    assert info["group_code"] == "abc123"
    fake_self._group_query.query_group_info_raw.assert_awaited_once_with("abc123")


@pytest.mark.asyncio
async def test_get_chat_info_group_falls_back_when_no_connection():
    # query_group_info_raw returns None when the WS isn't connected.
    fake_self = SimpleNamespace(
        _group_query=SimpleNamespace(query_group_info_raw=AsyncMock(return_value=None))
    )
    info = await YuanbaoAdapter.get_chat_info(fake_self, "group:abc123")
    assert info == {"name": "group:abc123", "type": "group", "group_code": "abc123"}


@pytest.mark.asyncio
async def test_get_chat_info_dm_unchanged():
    fake_self = SimpleNamespace(_group_query=SimpleNamespace(query_group_info_raw=AsyncMock()))
    info = await YuanbaoAdapter.get_chat_info(fake_self, "direct:someone")
    assert info == {"name": "direct:someone", "type": "dm"}
    fake_self._group_query.query_group_info_raw.assert_not_awaited()
