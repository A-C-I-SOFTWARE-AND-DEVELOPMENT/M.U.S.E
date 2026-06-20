"""AOS council routing proof — routing resolves only registered members.

Realizes follow-up FU-21: prove that muse's council/specialist routing can
only hand off to a council member that actually exists in the committed AOS
Enterprise Council registry, and that an invented (unregistered) name does
*not* resolve. This encodes the binding rule from ``CLAUDE.md``:

    "never improvise a council member that isn't in the registry."

The test is hermetic and read-only:

* It enumerates the registered council-member ``name:`` values straight from
  the committed registry frontmatter under ``skills/aos-enterprise-council/``.
  Nothing is written; no network is touched; the set is derived purely from
  files already on disk, so the result is deterministic.
* The frontmatter parse mirrors the stdlib parser in
  ``scripts/aos_registry_verify.py`` (a small local copy is kept here rather
  than importing a script module, so the test has no import-path coupling to
  ``scripts/``).
* It then exercises the real :class:`hermes_cli.jarvis_prime.router.Router`
  for every mode/intent that hands off to a *named council member* and asserts
  each emitted ``delegate_to`` resolves to a registered member — and that a
  fabricated name resolves to nothing (the membership set is exactly the
  registry).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.modes import Mode
from hermes_cli.jarvis_prime.router import RouteTarget, Router

# Repo root: tests/ lives directly under it.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_AOS_ROOT = _REPO_ROOT / "skills" / "aos-enterprise-council"
_AGENTS_ROOT = _AOS_ROOT / "agents"


def _frontmatter(text: str) -> dict[str, str]:
    """Parse the leading ``---`` YAML-ish frontmatter block.

    A deliberately small, stdlib-only copy of the parser in
    ``scripts/aos_registry_verify.py`` so this test owns no import-path
    coupling to the ``scripts/`` package.
    """
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ": " in line and not line.startswith(" "):
            key, value = line.split(": ", 1)
            fields[key.strip()] = value.strip().strip('"')
    return fields


def _registered_member_names() -> frozenset[str]:
    """The set of council-member ``name:`` values in the committed registry.

    Read-only: enumerates every ``*.md`` under
    ``skills/aos-enterprise-council/agents/`` and collects each file's
    frontmatter ``name:``. This *is* the membership set — the registry is the
    single source of truth for who the council is.
    """
    names: set[str] = set()
    for path in sorted(_AGENTS_ROOT.rglob("*.md")):
        if not path.is_file():
            continue
        fm = _frontmatter(path.read_text(encoding="utf-8"))
        name = fm.get("name")
        if name:
            names.add(name)
    return frozenset(names)


def _resolve_member(name: str, registry: frozenset[str]) -> str | None:
    """Resolve a requested council-member name against the registry.

    Returns the canonical name when it is a registered member, otherwise
    ``None``. The membership set is *exactly* the registry — there is no
    fuzzy matching and no implicit creation.
    """
    return name if name in registry else None


# Router exercises that each hand off to a *named* council member. Each tuple
# is (mode, intent, expected RouteTarget). The router's emitted ``delegate_to``
# for these must resolve to a registered member.
_COUNCIL_MEMBER_ROUTES: tuple[tuple[Mode, str, RouteTarget], ...] = (
    # Strategy mode always convenes the council via the director.
    (Mode.STRATEGY, "should we change positioning", RouteTarget.AOS_COUNCIL),
    # Operator mode + a council trigger word convenes the council.
    (
        Mode.OPERATOR,
        "we need a security review and a release readiness check",
        RouteTarget.AOS_COUNCIL,
    ),
    # Critic mode routes to the contrarian-reviewer specialist.
    (Mode.CRITIC, "tear it apart", RouteTarget.SPECIALIST),
    # Operator mode + a domain specialist trigger.
    (
        Mode.OPERATOR,
        "review the 49 CFR placarding for the hazmat shipping papers",
        RouteTarget.SPECIALIST,
    ),
    (
        Mode.OPERATOR,
        "add a recipe and update the nutrition data and nutrient math",
        RouteTarget.SPECIALIST,
    ),
)


@pytest.fixture(scope="module")
def registry() -> frozenset[str]:
    return _registered_member_names()


def test_registry_is_non_empty_and_includes_known_anchors(
    registry: frozenset[str],
) -> None:
    """Sanity-guard: the membership set loaded and contains known anchors.

    If the registry layout ever moves and the parse silently returns an empty
    set, the resolution assertions below would vacuously pass — this guard
    fails loudly instead.
    """
    assert registry, "no registered council members parsed from the registry"
    # Anchor names the router is wired to (see router.py) must be present.
    for anchor in ("aos-council-director", "contrarian-reviewer"):
        assert anchor in registry, f"expected anchor {anchor!r} in registry"


def test_every_registered_member_resolves(registry: frozenset[str]) -> None:
    """Every registered member name resolves to itself."""
    for name in registry:
        assert _resolve_member(name, registry) == name


def test_invented_member_does_not_resolve(registry: frozenset[str]) -> None:
    """Improvised / unregistered names resolve to nothing.

    This is the negative half of the invariant: the membership set is exactly
    the registry, so a fabricated council member cannot be conjured.
    """
    fabricated = (
        "totally-invented-specialist",
        "aos-council-director-2",  # near-miss of a real name
        "",  # empty is not a member
        "Aos-Council-Director",  # case-sensitive: not the same member
    )
    for name in fabricated:
        assert name not in registry
        assert _resolve_member(name, registry) is None


def test_router_council_targets_resolve_only_to_registered_members(
    registry: frozenset[str],
) -> None:
    """FU-21 core proof: the router only hands off to registered members.

    Drive the real router across every mode/intent that delegates to a named
    council member, and assert each emitted ``delegate_to`` resolves against
    the registry. No router path may name a member that isn't registered.
    """
    router = Router()
    seen_targets: set[str] = set()
    for mode, intent, expected_target in _COUNCIL_MEMBER_ROUTES:
        decision = router.route(mode=mode, intent=intent)
        assert decision.target == expected_target, (
            f"{mode}/{intent!r} routed to {decision.target}, "
            f"expected {expected_target}"
        )
        delegate = decision.delegate_to
        assert delegate, f"{mode}/{intent!r} produced no delegate_to"
        seen_targets.add(delegate)
        assert _resolve_member(delegate, registry) == delegate, (
            f"router delegated to unregistered council member {delegate!r} "
            f"for {mode}/{intent!r}"
        )

    # The exercised paths must collectively cover both the council-director
    # hand-off and at least one domain specialist, so this is a real proof and
    # not a single-target check.
    assert "aos-council-director" in seen_targets
    assert "contrarian-reviewer" in seen_targets
    assert "hazmat-command-specialist" in seen_targets
