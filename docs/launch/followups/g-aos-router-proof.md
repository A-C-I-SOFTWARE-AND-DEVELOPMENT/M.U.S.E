# g-aos-router-proof: routing resolves only registered AOS members (FU-21)

- **Status:** in-review
- **Risk class:** additive (test-only; no runtime behavior change)
- **Branch:** `claude/g-aos-router-proof` · **Base:** `main` @ `ba2c12dfd0ff005f8f0a36f5adbaac96edff681d`
- **PR:** draft (see PR link in ledger / report)
- **Owner-gate required to merge?** no — strictly additive test, default code paths byte-for-byte unchanged.

## Intent (one paragraph)

Realizes follow-up FU-21 with an executable proof. `CLAUDE.md` states the
binding rule "never improvise a council member that isn't in the registry,"
and `hermes_cli/jarvis_prime/router.py` hands muse work off to named council
members (e.g. `aos-council-director`, `contrarian-reviewer`,
`hazmat-command-specialist`). Before this grain there was no test pinning the
invariant that router hand-offs resolve *only* to members that actually exist
in the committed AOS Enterprise Council registry. This test enumerates the
registered member `name:` set from the committed registry frontmatter and
asserts (a) every registered name resolves, (b) an invented/near-miss name does
*not* resolve (the membership set is exactly the registry), and (c) the real
`Router`, driven across every council/specialist hand-off path, only ever names
a registered member. No runtime behavior changes — the proof is read-only over
files already on disk.

## Owned files (the ONLY files this task may write)

- `tests/test_aos_council_routing.py` (new, test only)
- `docs/launch/followups/g-aos-router-proof.md` (this snapshot)

> Disjoint from every other in-flight grain. The registry under
> `skills/aos-enterprise-council/` and all `registry/` source files are
> READ-ONLY for this task — nothing was written there. The ledger
> (`docs/launch/10_10_followups_ledger.md`) was **not** edited.

## Plan (bounded steps)

1. Reuse the stdlib `frontmatter()` parse pattern from
   `scripts/aos_registry_verify.py` (a small local copy, to avoid import-path
   coupling to the `scripts/` package).
2. Build the registered-member set by enumerating every `*.md` under
   `skills/aos-enterprise-council/agents/` and collecting its frontmatter
   `name:`.
3. Implement a tiny `_resolve_member(name, registry)` membership resolver
   (returns the name iff registered, else `None`).
4. Assert: registry non-empty + known anchors present (guards against a
   silently-empty parse); every registered name resolves; fabricated names
   (including a near-miss and a case variant) do not resolve.
5. Drive the real `Router` across the Strategy / Operator-council /
   Critic / Operator-specialist (hazmat + nourish) paths and assert each
   emitted `delegate_to` resolves to a registered member, covering both the
   council-director hand-off and a domain specialist.

## Validation

- `uv run ruff check tests/test_aos_council_routing.py` → **All checks passed!**
- `python -m pytest tests/test_aos_council_routing.py -o addopts="" -q` →
  **4 passed**
- `uv run ty check tests/test_aos_council_routing.py` → only the pre-existing
  environment diagnostic `unresolved-import: pytest` (same baseline produced by
  existing test files, e.g. `tests/test_worker_registry.py`); **no new
  code-level diagnostics**.
- Hermetic: verified the test also passes when run from a different cwd
  (`/tmp`); read-only over the committed registry; no network; deterministic.

## Residual / follow-on

- **Test-only by design.** No source/registry file was modified.
- **Observation (not fixed here):** `router._SPECIALIST_DOMAINS` includes a
  `logistics-specialist` key whose `name:` is **not** present in the registry
  frontmatter (unlike `hazmat-command-specialist` and
  `nourish-product-specialist`, which are registered). This grain does not
  trigger that path and does not encode it as pass/fail, to keep the proof
  true and non-flaky and to respect the "no source edits" constraint. A
  follow-up could either register a `logistics-specialist` member or remove
  the unrouted domain key — owner's call, out of scope here.
