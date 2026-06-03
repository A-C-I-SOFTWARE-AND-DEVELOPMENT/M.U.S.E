"""Tests for INT-1 integration registry (capability + approval governance)."""

import pytest

from hermes_cli.integrations import (
    ActionRequest,
    IntegrationRegistry,
    IntegrationSpec,
    default_registry,
)


def test_register_and_lookup():
    reg = IntegrationRegistry()
    reg.register(IntegrationSpec(name="email", capabilities=frozenset({"read", "send"}),
                                 requires_approval=frozenset({"send"})))
    assert reg.get("email") is not None
    assert [s.name for s in reg.list()] == ["email"]


def test_requires_approval_must_be_subset_of_capabilities():
    with pytest.raises(ValueError):
        IntegrationSpec(name="bad", capabilities=frozenset({"read"}),
                        requires_approval=frozenset({"send"}))


def test_unknown_integration_rejected():
    reg = IntegrationRegistry()
    res = reg.execute(ActionRequest("nope", "read"))
    assert res.status == "rejected"


def test_unknown_capability_rejected():
    reg = default_registry()
    res = reg.execute(ActionRequest("email", "delete_everything"))
    assert res.status == "rejected"


def test_send_blocked_without_approval_and_transport_not_called():
    reg = IntegrationRegistry()
    calls = []
    reg.register(
        IntegrationSpec(name="email", capabilities=frozenset({"read", "send"}),
                        requires_approval=frozenset({"send"})),
        transport=lambda req: calls.append(req) or "SENT",
    )
    res = reg.execute(ActionRequest("email", "send", {"to": "x@y.z"}))
    assert res.status == "needs_approval"
    assert calls == []  # nothing sent


def test_send_allowed_with_approval_calls_transport():
    reg = IntegrationRegistry()
    calls = []
    reg.register(
        IntegrationSpec(name="email", capabilities=frozenset({"read", "send"}),
                        requires_approval=frozenset({"send"})),
        transport=lambda req: calls.append(req) or "SENT",
    )
    res = reg.execute(ActionRequest("email", "send", {"to": "x@y.z"}), approved=True)
    assert res.status == "ok"
    assert res.data == "SENT"
    assert len(calls) == 1


def test_read_capability_allowed_without_approval():
    reg = IntegrationRegistry()
    reg.register(
        IntegrationSpec(name="email", capabilities=frozenset({"read", "send"}),
                        requires_approval=frozenset({"send"})),
        transport=lambda req: ["msg1", "msg2"],
    )
    res = reg.execute(ActionRequest("email", "read"))
    assert res.status == "ok"
    assert res.data == ["msg1", "msg2"]


def test_declared_only_integration_has_no_side_effect():
    # default_registry wires NO transports → sends are gated, reads are no-op ok.
    reg = default_registry()
    assert reg.execute(ActionRequest("email", "send"), approved=True).status == "ok"
    assert reg.execute(ActionRequest("email", "send"), approved=True).data is None
    assert reg.execute(ActionRequest("calendar", "create_event")).status == "needs_approval"


def test_default_registry_seeds_comms_integrations():
    names = {s.name for s in default_registry().list()}
    assert {"email", "sms", "calendar"} <= names
