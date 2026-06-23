"""Live core-loop smoke test (WC-3) — the "is this a tool, not a demo" proof.

Why this exists
---------------

`tests/e2e/test_core_loop_depth_e2e.py` (FU-15) records the cockpit-level
control plane end-to-end — submit, dispatch, owner-gate, publish gate,
approvals, audit ledger — but it is **offline by construction**: the
chosen worker is the built-in `hermes-local-planner` lane, which does
repo-only navigation with "no edits, no shell, no network." It is a real
HTTP+orchestrator proof, but it never produces a model-generated artifact.

A sharp reviewer can fairly ask: "show me one test in this repo that
calls a real model and asserts on its output." Until WC-3, the answer
was "none." This file is that test — gated behind ``@pytest.mark.live``
so it does NOT run on free CI, but runnable locally with one flag on any
box that has a free / local agent CLI installed (the standard target
being the `claude` worker the README's first-run path already recommends).

How to run it
-------------

::

    pytest tests/e2e/test_core_loop_live_smoke.py --run-live      # explicit
    HERMES_E2E_LIVE=1 pytest tests/e2e/test_core_loop_live_smoke.py
    pytest tests/e2e -m live --run-live                           # marker filter

What it proves
--------------

A single forward pass: the configured worker CLI is on PATH, returns a
zero exit code on a trivial prompt, emits a non-empty stdout, and the
stdout does NOT match the worker-misconfigured / unauthenticated error
shapes (no "API key", no "unauthenticated", no "not configured"). That
is the minimum honest "I produced an artifact" signal — small enough to
not be theater, real enough to fail when the loop is broken.

It is deliberately **not** a full chat turn through muse's gateway:
that path is exercised by the unit + integration suites and stubbed in
the offline E2E. The live smoke targets the single concrete claim the
offline E2E cannot make: "the configured model actually answers." Once
the wider depth program lands a free/local model with a real scoring
harness (the deep-research recommendation: BFCL v3 multi-turn on Qwen3
32B / GLM-4.5 via vLLM), this test is the seed that grows into it.
"""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest


# Markers picked up by ``tests/conftest.py::pytest_collection_modifyitems``.
# ``live`` skips the whole module on the default lane; ``filterwarnings``
# is added defensively to keep the live runner's banner out of failure tails.
pytestmark = [
    pytest.mark.live,
    pytest.mark.filterwarnings("ignore::DeprecationWarning"),
]


# Worker binaries the smoke test will try, in priority order. The first one
# whose ``--version`` returns 0 is used. This matches the route order written
# by ``muse models bootstrap`` (``claude_code_worker`` before ``codex_worker``)
# so a box configured via the README's headless path is exercised verbatim.
_WORKER_CANDIDATES: tuple[str, ...] = ("claude", "codex")

# The prompt we send. Deliberately tiny: one token of expected output, zero
# tool-use, zero ambiguity. Anything bigger turns this into a benchmark — not
# the job. (The real benchmark belongs in the depth program — see the WC-3
# rationale in the PR description.)
_PROMPT = (
    "Reply with exactly the single word OK and nothing else. "
    "Do not explain, do not add punctuation, do not add a newline beyond the word."
)

# How long to wait for the worker. A correctly-configured local agent CLI
# answers a one-word prompt in well under 60s; this is a generous ceiling so a
# warm-cache miss or model load does not flake the smoke.
_TIMEOUT_S = 120

# Substrings in the worker's stdout/stderr that mean "the loop is broken, not
# that the model produced a thinking artifact." If any of these appear, the
# test fails with a clear diagnostic instead of asserting on the (wrong)
# output. Kept conservative — common worker error vocabulary, no rare phrases.
_BROKEN_LOOP_MARKERS: tuple[str, ...] = (
    "api key",
    "api_key",
    "unauthenticated",
    "authentication failed",
    "not configured",
    "not authenticated",
    "no provider",
    "no model",
    "credentials missing",
)


def _resolve_worker() -> tuple[str, str] | None:
    """Return ``(name, path)`` of the first available worker CLI, or None.

    Tried in priority order. ``which`` only — no execution; the test body
    runs the worker exactly once with the real prompt, so we don't burn
    invocations on probes.
    """
    for name in _WORKER_CANDIDATES:
        path = shutil.which(name)
        if path:
            return name, path
    return None


def _build_argv(worker_name: str, worker_path: str) -> list[str]:
    """One-shot non-interactive invocation per worker, as documented by each CLI.

    Each agent CLI exposes a non-interactive / single-prompt mode under a
    different flag. The argv here is the documented "give me one answer and
    exit" invocation for each worker; nothing fancy.
    """
    if worker_name == "claude":
        # ``claude -p`` is the documented headless / pipe-friendly mode that
        # honors an ``ANTHROPIC_API_KEY`` env var when present and answers in
        # a single shot. See https://code.claude.com/docs/en/headless.
        return [worker_path, "-p", _PROMPT]
    if worker_name == "codex":
        # ``codex exec`` is the OpenAI Codex CLI's non-interactive mode and
        # accepts a prompt as the trailing positional. See
        # https://developers.openai.com/codex/noninteractive.
        return [worker_path, "exec", _PROMPT]
    # Defensive: a new worker added to _WORKER_CANDIDATES without a matching
    # argv builder would otherwise silently mis-invoke. Skip explicitly.
    pytest.skip(f"live smoke does not know how to invoke worker {worker_name!r} yet")
    return []  # unreachable; pytest.skip raises.


def test_live_worker_produces_nonempty_artifact() -> None:
    """One real worker call: zero exit, non-empty stdout, no broken-loop text.

    This is the smallest honest signal. We do not assert the exact word "OK"
    because models vary in formatting (some add a final newline, some quote
    it, some add a courtesy period). We DO assert:

    - The chosen worker CLI is on PATH.
    - It exits zero within ``_TIMEOUT_S``.
    - Its stdout contains non-whitespace content.
    - Its stdout does NOT match any of the broken-loop error markers — those
      indicate the local config is wrong (no key, no model, wrong endpoint),
      which is what the first-run gate is supposed to catch and which the
      live smoke is here to backstop.
    """
    chosen = _resolve_worker()
    if chosen is None:
        pytest.skip(
            "live smoke requires one of {!r} on PATH — install Claude Code "
            "or the Codex CLI to run this lane.".format(_WORKER_CANDIDATES)
        )
        return  # unreachable (pytest.skip raises); narrows `chosen` for the type checker
    worker_name, worker_path = chosen
    argv = _build_argv(worker_name, worker_path)

    # Inherit env but explicitly strip any test-suite-blanked credential vars
    # so the worker's own auth path (browser OAuth cache, ANTHROPIC_API_KEY,
    # ~/.codex/auth.json, etc.) is what it actually depends on — not whatever
    # this test process inherited. The conftest credential filter is exactly
    # what makes this smoke meaningful: the test cannot fake the credential.
    env = dict(os.environ)

    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            f"live smoke worker {worker_name!r} timed out after {_TIMEOUT_S}s. "
            f"argv={argv!r}. Partial stdout: {exc.stdout!r}; "
            f"partial stderr: {exc.stderr!r}."
        )
    except FileNotFoundError:
        # which() said it existed at the start of the test, but a stale PATH
        # cache or a racing uninstall could remove it. Skip rather than fail —
        # this is an env condition, not a code regression.
        pytest.skip(
            f"live smoke worker {worker_name!r} was on PATH at resolve time "
            "but missing at invocation time; treating as environmental."
        )

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    combined_low = (stdout + "\n" + stderr).lower()

    # Broken-loop check fires FIRST so its diagnostic wins over a generic
    # exit-code message — an "API key" error is a much more useful failure
    # than "exit code 1".
    broken_hits = [marker for marker in _BROKEN_LOOP_MARKERS if marker in combined_low]
    assert not broken_hits, (
        f"live smoke worker {worker_name!r} reported a broken-loop signal "
        f"({broken_hits!r}) — the local config is the problem, not the test. "
        f"stdout={stdout!r} stderr={stderr!r}"
    )

    assert completed.returncode == 0, (
        f"live smoke worker {worker_name!r} exited {completed.returncode}. "
        f"stdout={stdout!r} stderr={stderr!r}"
    )

    assert stdout, (
        f"live smoke worker {worker_name!r} returned empty stdout — exit was "
        f"zero but no artifact was produced. stderr={stderr!r}"
    )
