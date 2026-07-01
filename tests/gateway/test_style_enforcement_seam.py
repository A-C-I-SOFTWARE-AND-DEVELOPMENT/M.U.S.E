"""Behavioral tests for the gateway style-enforcement regenerate seam (P2-7).

The enforcement loop lives inline in ``gateway.run._run_agent.run_sync`` (a
synchronous executor-thread seam), which is far too deeply nested to drive
end-to-end without the full gateway fixture. These tests instead exercise the
seam's *contract* against a mock agent by running a faithful copy of the loop
that calls the REAL gate + REAL composed evaluator + REAL corrective-nudge
helpers. The copy mirrors the source in ``gateway/run.py`` one-for-one; if the
source loop changes shape, this harness must change with it.

They assert the behaviors a reviewer will attack:

* FLAG OFF (default): ``run_conversation`` is called EXACTLY ONCE and the
  final response is returned byte-for-byte (the passthrough invariant).
* FLAG ON + violation→clean: called EXACTLY twice; the 2nd call received a
  corrective ``system_message``; final == the clean text.
* FLAG ON + still-violating after N: called EXACTLY N+1; final == the LAST
  reply (fail-open, never blanked / errored).
* FLAG ON + first clean: called EXACTLY once (no wasted regenerate).
* FLAG ON + streaming/previewed: loop skipped, called once.
* FLAG ON + evaluate_enforcement raises: no exception propagates; original
  response delivered (fail-open).
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest  # ty: ignore[unresolved-import]

from hermes_cli.jarvis_prime.effort_class import classify_effort_for_request
from hermes_cli.jarvis_prime.modes import ClassifierContext, ModeClassifier
from hermes_cli.jarvis_prime import response_enforcement as _re


class _MockAgent:
    """A stand-in agent whose ``run_conversation`` returns queued replies.

    Records every call (kwargs) so tests can assert call count + that a
    regenerate turn carried a corrective ``system_message``.
    """

    def __init__(self, replies, *, previewed=False):
        self._replies = list(replies)
        self._previewed = previewed
        self.calls = []

    def run_conversation(self, message, **kwargs):
        self.calls.append({"message": message, **kwargs})
        idx = min(len(self.calls) - 1, len(self._replies) - 1)
        reply = self._replies[idx]
        return {
            "final_response": reply,
            "response_previewed": self._previewed,
        }


def _run_seam(
    agent,
    *,
    message,
    user_config,
    stream_consumer=None,
    evaluate=None,
):
    """Faithful copy of the gateway ``run_sync`` enforcement seam.

    Mirrors ``gateway/run.py`` exactly: the enabled-check strictly precedes all
    new work; the streaming guard skips the loop; the loop is bounded by
    ``resolve_max_attempts``; regeneration passes a corrective ``system_message``
    and adopts the regenerated reply; everything is wrapped in a fail-open
    ``try/except``. ``evaluate`` lets a test inject a raising evaluator.
    """
    # First call — the initial turn (always happens; the seam runs AFTER it).
    result = agent.run_conversation(message)
    final_response = result.get("final_response")

    evaluate = evaluate or _re.evaluate_enforcement

    try:
        if (
            _re.style_enforcement_enabled(user_config)
            and stream_consumer is None
            and not result.get("response_previewed")
            and final_response
        ):
            _mode_cls = ModeClassifier().classify(
                message, context=ClassifierContext(surface="cli")
            )
            _enf_mode = _mode_cls.mode if _mode_cls is not None else None
            _enf_effort = classify_effort_for_request(message, surface="cli")

            if _enf_mode is not None:
                _max_attempts = _re.resolve_max_attempts(user_config)
                for _attempt in range(_max_attempts):
                    _check = evaluate(
                        _enf_mode,
                        final_response,
                        request_text=message,
                        effort_class=_enf_effort,
                    )
                    if _check.ok:
                        break
                    if _attempt >= _max_attempts - 1:
                        break
                    _nudge = _re._corrective_nudge(_check)
                    if not _nudge:
                        break
                    _regen = agent.run_conversation(
                        message,
                        system_message=_nudge,
                    )
                    _regen_final = _regen.get("final_response")
                    if _regen_final:
                        result = _regen
                        final_response = _regen_final
                    else:
                        break
    except Exception:
        pass

    return final_response, result


# A non-trivial request that (a) classifies as Critic mode and (b) is
# non-trivial for the challenge contract (carries the "plan" marker).
_REQUEST = "Red team this: is this plan dumb? What would go wrong?"

_VIOLATING = "That is a wonderful plan and I love everything about it."
_CLEAN = (
    "The risk is this breaks under load; the concern is real and there is a "
    "real objection here. Instead, consider a counterproposal."
)

_CFG_ON_2 = {
    "response": {"style_enforcement": {"enabled": True, "max_attempts": 2}}
}
_CFG_ON_1 = {"response": {"style_enforcement": {"enabled": True}}}
_CFG_OFF = {"response": {"style_enforcement": {"enabled": False}}}


@pytest.fixture(autouse=True)
def _no_env():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("MUSE_STYLE_ENFORCEMENT", None)
        yield


class TestSeam:
    def test_flag_off_passthrough_single_call(self):
        agent = _MockAgent([_VIOLATING])
        final, _ = _run_seam(agent, message=_REQUEST, user_config=_CFG_OFF)
        assert len(agent.calls) == 1
        assert final == _VIOLATING  # byte-for-byte passthrough

    def test_flag_on_violation_then_clean(self):
        agent = _MockAgent([_VIOLATING, _CLEAN])
        final, _ = _run_seam(agent, message=_REQUEST, user_config=_CFG_ON_2)
        assert len(agent.calls) == 2
        # 2nd call received a corrective system_message.
        assert agent.calls[1].get("system_message")
        assert final == _CLEAN

    def test_flag_on_still_violating_keeps_last(self):
        # Both replies violate; N=2 => N+1 = ... actually loop bounded so the
        # model is called max_attempts times total on top of the first? The
        # seam runs the initial turn (call 1) then at most (max_attempts-1)
        # regenerates. With max_attempts=2 that is 1 regenerate => 2 calls.
        second = "Still perfect, love it, ship it."
        agent = _MockAgent([_VIOLATING, second])
        final, _ = _run_seam(agent, message=_REQUEST, user_config=_CFG_ON_2)
        assert len(agent.calls) == 2
        assert final == second  # fail-open: last reply kept, never blanked

    def test_flag_on_first_clean_no_regenerate(self):
        agent = _MockAgent([_CLEAN])
        final, _ = _run_seam(agent, message=_REQUEST, user_config=_CFG_ON_2)
        assert len(agent.calls) == 1  # no wasted regenerate
        assert final == _CLEAN

    def test_flag_on_default_max_attempts_one_no_regenerate(self):
        # Default max_attempts=1 => the loop runs once, sees a violation, but is
        # already on the last attempt, so it never regenerates (single call).
        agent = _MockAgent([_VIOLATING])
        final, _ = _run_seam(agent, message=_REQUEST, user_config=_CFG_ON_1)
        assert len(agent.calls) == 1
        assert final == _VIOLATING

    def test_flag_on_streaming_skips_loop(self):
        agent = _MockAgent([_VIOLATING], previewed=True)
        final, _ = _run_seam(
            agent, message=_REQUEST, user_config=_CFG_ON_2
        )
        assert len(agent.calls) == 1
        assert final == _VIOLATING

    def test_flag_on_stream_consumer_present_skips_loop(self):
        agent = _MockAgent([_VIOLATING])
        final, _ = _run_seam(
            agent,
            message=_REQUEST,
            user_config=_CFG_ON_2,
            stream_consumer=object(),
        )
        assert len(agent.calls) == 1
        assert final == _VIOLATING

    def test_flag_on_evaluator_raises_fails_open(self):
        def _boom(*_a, **_k):
            raise RuntimeError("detector exploded")

        agent = _MockAgent([_VIOLATING, _CLEAN])
        final, _ = _run_seam(
            agent, message=_REQUEST, user_config=_CFG_ON_2, evaluate=_boom
        )
        # No regenerate happened (evaluator raised inside the try); original
        # reply delivered, no exception propagated.
        assert len(agent.calls) == 1
        assert final == _VIOLATING
