from hermes_cli.jarvis_prime.personal_action_authority import (
    Capability,
    CapabilityGrant,
    CapabilityStatus,
    ExecutionMode,
    build_personal_action_contract,
)


def grants(*caps):
    return [CapabilityGrant(capability=cap, status=CapabilityStatus.GRANTED) for cap in caps]


def test_facebook_navigation_direct_executes_when_authorized_and_granted():
    contract = build_personal_action_contract(
        "click on Facebook",
        target_app_label="Facebook",
        target_package="com.facebook.katana",
        grants=grants(Capability.PACKAGE_VISIBILITY, Capability.OVERLAY, Capability.ACCESSIBILITY),
    )
    assert contract.execution_mode == ExecutionMode.DIRECT_EXECUTE
    assert contract.owner_authorized is True
    assert contract.missing_capabilities == ()
    assert [beat.name for beat in contract.visual_beats][:3] == ["acknowledge", "think", "move_to_target"]


def test_missing_android_grants_blocks_execution_but_not_owner_authorization():
    contract = build_personal_action_contract("click on Facebook", target_app_label="Facebook")
    assert contract.execution_mode == ExecutionMode.BLOCKED_MISSING_CAPABILITY
    assert contract.owner_authorized is True
    assert Capability.ACCESSIBILITY in contract.missing_capabilities


def test_external_post_has_pause_point_by_default():
    contract = build_personal_action_contract(
        "post this to Facebook",
        target_app_label="Facebook",
        grants=grants(Capability.PACKAGE_VISIBILITY, Capability.OVERLAY, Capability.ACCESSIBILITY),
    )
    assert contract.execution_mode == ExecutionMode.EXECUTE_WITH_PAUSE_POINT
    assert "send/post/publish" in contract.pause_reason


def test_emergency_stop_wins_over_everything():
    contract = build_personal_action_contract(
        "click on Facebook",
        target_app_label="Facebook",
        grants=grants(Capability.PACKAGE_VISIBILITY, Capability.OVERLAY, Capability.ACCESSIBILITY),
        emergency_stopped=True,
    )
    assert contract.execution_mode == ExecutionMode.EMERGENCY_STOPPED
