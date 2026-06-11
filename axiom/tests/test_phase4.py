"""Phase 4 — the agent surface: every MCP tool exercised through an
in-process fastmcp client. The exit-gate test is a scripted agent
session that composes a NEW unit calling an existing registered unit,
verifies it, runs it, and audits the chain — through MCP tools only.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from fastmcp import Client  # ty: ignore[unresolved-import]

from axiom.core.ledger import Ledger
from axiom.core.registry import Registry
from axiom.interface import mcp_server
from axiom.memory.beliefs import ENTRENCH_OWNER


def _data(result):
    """Extract structured data from a fastmcp CallToolResult."""
    if getattr(result, "data", None) is not None:
        return result.data
    return json.loads(result.content[0].text)


@pytest.fixture
def host(tmp_path):
    registry = Registry(str(tmp_path / "registry.db"))
    ledger = Ledger(str(tmp_path / "ledger.db"))
    mcp_server.configure(registry, ledger, data_dir=str(tmp_path / "data"))
    return mcp_server


def _call(tool: str, args: dict):
    async def go():
        async with Client(mcp_server.mcp) as client:
            return _data(await client.call_tool(tool, args))
    return asyncio.run(go())


DOUBLE_FORM = {
    "name": "double", "doc": "Double a number.",
    "params": {"x": "float"},
    "intent": "THE unit SHALL return two times x.",
    "contracts": ["result == x * 2.0"],
    "effects": [], "refs": {},
    "body": [
        {"op": "mul", "in": ["x", 2.0], "into": "y"},
        {"op": "return", "in": ["y"]},
    ],
}


# ----------------------------------------------------------- 4.2 tool surface

def test_all_tools_visible_with_schemas(host):
    async def go():
        async with Client(mcp_server.mcp) as client:
            return await client.list_tools()
    tools = {t.name: t for t in asyncio.run(go())}
    expected = {"registry_search", "verify_and_register", "run",
                "ledger_verify", "memory_observe", "memory_query",
                "forge_run", "ledger_history", "unit_compose"}
    assert expected <= set(tools)
    for name in expected:
        assert tools[name].inputSchema, f"{name} must publish an input schema"


def test_verify_and_register_and_search(host):
    out = _call("verify_and_register", {"unit_form": DOUBLE_FORM})
    assert out["ok"] is True and out["unit_hash"]
    hits = _call("registry_search", {"name": "double"})
    assert any(h["unit_hash"] == out["unit_hash"] for h in hits)


def test_run_returns_machine_readable_errors(host):
    out = _call("verify_and_register", {"unit_form": DOUBLE_FORM})
    ok = _call("run", {"unit_hash": out["unit_hash"], "args": {"x": 4.0}})
    assert ok == {"ok": True, "result": 8.0}
    missing = _call("run", {"unit_hash": "00" * 32, "args": {}})
    assert missing["ok"] is False and missing["error"] == "unresolved"


def test_memory_tools(host):
    obs = _call("memory_observe",
                {"content": "gateway port is 8088", "source_grade": "verified"})
    assert obs["ok"] is True and obs["memory_id"] >= 1
    hits = _call("memory_query", {"query": "what is the gateway port?", "k": 3})
    assert hits and "gateway" in hits[0]["content"]


def test_memory_observe_owner_required_is_machine_readable(host):
    bid = mcp_server._mind.believe("never deploy fridays",
                                   entrenchment=ENTRENCH_OWNER)
    out = _call("memory_observe",
                {"content": "deploy fridays freely", "source_grade": "hearsay",
                 "contradicts": bid})
    assert out["ok"] is False
    assert out["error"] == "owner_required"
    assert out["belief_id"] == bid


def test_forge_run_tool(host):
    cheat = dict(DOUBLE_FORM, name="cheat",
                 body=[{"op": "add", "in": ["x", 2.0], "into": "y"},
                       {"op": "return", "in": ["y"]}])
    out = _call("forge_run", {
        "units": {"honest": DOUBLE_FORM, "cheat": cheat},
        "probes": [{"x": 3.0}],
    })
    assert out["champion"] == "honest"
    assert out["gate_failed"] == ["cheat"]


def test_unit_compose_verifies_refs_as_you_go(host):
    reg = _call("verify_and_register", {"unit_form": DOUBLE_FORM})
    good = _call("unit_compose", {
        "name": "quad", "doc": "", "params": {"x": "float"},
        "intent": "THE unit SHALL return four times x.",
        "contracts": ["result == x * 4.0"],
        "refs": {"d": reg["unit_hash"]},
        "body": [
            {"op": "call", "ref": "d", "in": ["x"], "into": "t"},
            {"op": "call", "ref": "d", "in": ["t"], "into": "u"},
            {"op": "return", "in": ["u"]},
        ],
    })
    assert good["ok"] is True and good["unit_form"]["refs"]["d"]

    bad = _call("unit_compose", {
        "name": "ghostly", "doc": "", "params": {"x": "float"},
        "intent": "THE unit SHALL call a ghost.",
        "contracts": ["result == x"],
        "refs": {"g": "ff" * 32},
        "body": [{"op": "call", "ref": "g", "in": ["x"], "into": "t"},
                 {"op": "return", "in": ["t"]}],
    })
    assert bad["ok"] is False
    assert any(e.get("unresolved") for e in bad["errors"])


# ------------------------------------------------------------- 4.4 EXIT GATE

def test_scripted_agent_session_end_to_end(host):
    """An agent session through MCP tools ONLY: search → compose →
    verify → run → audit."""
    async def session():
        async with Client(mcp_server.mcp) as client:
            async def call(tool, args):
                return _data(await client.call_tool(tool, args))

            # 1. Search before invent: nothing there yet.
            assert await call("registry_search", {"name": "double"}) == []

            # 2. Register the base unit.
            base = await call("verify_and_register", {"unit_form": DOUBLE_FORM})
            assert base["ok"], base

            # 3. Compose a NEW unit that calls the registered one.
            composed = await call("unit_compose", {
                "name": "quadruple", "doc": "Four times x via double twice.",
                "params": {"x": "float"},
                "intent": "THE unit SHALL return four times x.",
                "contracts": ["result == x * 4.0"],
                "refs": {"d": base["unit_hash"]},
                "body": [
                    {"op": "call", "ref": "d", "in": ["x"], "into": "t"},
                    {"op": "call", "ref": "d", "in": ["t"], "into": "u"},
                    {"op": "return", "in": ["u"]},
                ],
            })
            assert composed["ok"], composed

            # 4. Verify + register the composition.
            quad = await call("verify_and_register",
                              {"unit_form": composed["unit_form"]})
            assert quad["ok"], quad

            # 5. Run it; the postcondition is enforced on the result.
            run = await call("run", {"unit_hash": quad["unit_hash"],
                                     "args": {"x": 3.0}})
            assert run == {"ok": True, "result": 12.0}

            # 6. Audit: this unit's full history from the ledger,
            #    and the chain must verify.
            history = await call("ledger_history",
                                 {"unit_hash": quad["unit_hash"]})
            kinds = [e["kind"] for e in history]
            assert "artifact_attestation" in kinds
            assert "process_event" in kinds
            audit = await call("ledger_verify", {})
            assert audit["chain_valid"] is True
            return True

    assert asyncio.run(session()) is True
