# FU-23: Machine-tag unverified model slugs as `candidate`

- **Status:** in-review
- **Risk class:** additive
- **Branch:** `claude/fu-23-candidate-tagging` · **Base:** `main` @ `b74f9889`
- **PR:** (draft — see ledger)
- **Owner-gate required to merge?** no — strictly additive; verified routing is
  byte-for-byte unchanged, no default behavior change, no paid resolution change.

## Intent (one paragraph)

The founding "no fake certainty" rule was only half-enforced.
`config/model-catalog.yaml` already tags unverified rows with
`tags: [..., candidate]`, but `docs/ai-intelligence/oss-model-catalog.yaml`
— the layer that actually drives `task_router` routing — carried only a *prose*
disclaimer (the "PROVIDER MODEL IDS for just-released variants are CANDIDATES
pending verification" note). Just-released variant slugs (glm-5.1,
deepseek-v4-pro, minimax-m3, kimi-k2.6-thinking, qwen3-coder-next, qwen3-235b,
qwen3-vl) shipped with hard benchmark numbers presented as fact, and
`task_router._hosted_candidates` expanded them into live `provider/model` routing
candidates with no machine-readable way to down-weight the unverified ones. This
follow-up adds a per-entry `candidate: true` flag (mirroring the config catalog's
honesty), surfaces it through the OSS model brain as `OssModel.candidate`, and
makes `_hosted_candidates` order **verified families before candidate-tagged
ones** via a *stable partition* — so a verified slug is never dropped and a lane
whose hits are all-verified or all-candidate is byte-for-byte unchanged; only a
*mixed* lane (e.g. `reasoning`) re-orders (verified `deepseek-r1` / `gpt-oss-120b`
ahead of candidate `qwen3-235b` / `glm-5`). The `set_paid_enabled` docstring was
also corrected (DOC ONLY) — the override is a double-gate (owner override OR, when
unset, the env-written policy flag), not a "floor on top of the env."

## Owned files (the ONLY files this task may write)

- `docs/ai-intelligence/oss-model-catalog.yaml`
- `hermes_cli/oss_model_brain.py`
- `hermes_cli/jarvis_prime/task_router.py`
- `tests/test_oss_model_brain.py` (extended)
- `docs/launch/followups/fu-23-candidate-tagging.md` (this snapshot)

## What changed

1. **YAML (`oss-model-catalog.yaml`)** — added `candidate: true` to the 7
   unverified just-released frontier/strong families (`deepseek-v4`, `glm-5`,
   `kimi-k2`, `minimax-m2`, `qwen3-coder`, `qwen3-235b`, `qwen3-vl`) — the exact
   set tagged `candidate` in `config/model-catalog.yaml`. Documented the field in
   the schema comment. Stable/locally-grounded families (deepseek-r1, gpt-oss-*,
   gemma4, qwen-omni, retrieval stack, qwen3-27b, devstral-small) stay unflagged.
2. **`oss_model_brain.py`** — added `OssModel.candidate: bool = False` (defaults
   verified), parsed it in `_model_from_yaml` (`bool(raw.get("candidate", False))`),
   added it to `OssModel.to_dict`, and mirrored `candidate=True` on the same 7
   families in `_BUILTIN_FAMILIES`. `load_oss_catalog` still never raises.
3. **`task_router._hosted_candidates`** — replaced the single ordered list with a
   stable verified-first / candidate-last partition (relative order preserved in
   each group). Verified routing unchanged; candidates sunk, never dropped. The
   disable env switch and the never-shrink bare-provider tail are untouched.
4. **`task_router.set_paid_enabled`** — softened the docstring to describe the
   real double-gate. No code/behavior change to paid resolution (no lockout).

## Four sync points kept consistent

YAML routing+families ↔ `_BUILTIN_ROUTING`/`_BUILTIN_FAMILIES` ↔ `model_brain`
`KNOWN_TASKS` ↔ parity tests. The candidate set is now guarded by a new parity
test (`test_yaml_and_builtin_agree_on_candidate_set`) alongside the existing
tasks/routing parity tests, so a candidate added in one mirror must be added in
the other.

## Validation

- `uv run ruff check hermes_cli/oss_model_brain.py hermes_cli/jarvis_prime/task_router.py tests/test_oss_model_brain.py` → **All checks passed!**
  (Ruff lints Python only; the YAML is validated by `yaml.safe_load` + the test
  suite that loads it.)
- `uv run ty check hermes_cli/oss_model_brain.py hermes_cli/jarvis_prime/task_router.py tests/test_oss_model_brain.py` → **All checks passed!** (zero diagnostics ⇒ no new diagnostics vs base)
- `python -m pytest tests/test_oss_model_brain.py tests/test_jarvis_prime_task_router.py tests/test_gemma4_catalog.py -o addopts="" -q` → **46 passed**
- Wider sweep (consumers): `test_ai_radar`, `test_jarvis_model_bootstrap`,
  `test_model_bootstrap`, `test_gemma4_model_bootstrap`, `test_jarvis_launch_doctor`,
  `test_jarvis_prime_model_rerank`, `test_gemma4_task_router`,
  `test_jarvis_prime_router`, `tests/hermes_cli/test_open_data_sources` →
  **all green** (no downstream break from the additive `to_dict` key / new field).

New tests added to `tests/test_oss_model_brain.py`:
`test_candidate_defaults_false`, `test_unverified_slugs_carry_candidate_after_yaml_load`,
`test_candidate_flag_survives_to_dict_roundtrip`,
`test_yaml_and_builtin_agree_on_candidate_set`,
`test_hosted_candidates_orders_verified_before_candidate`,
`test_hosted_candidates_all_candidate_lane_unchanged`,
`test_hosted_candidates_disabled_flag_is_byte_for_byte_bare`.

## Residual / follow-on

- The flag is metadata + an intra-tier tiebreaker only; it deliberately does NOT
  gate or block a candidate (scorecards/owner overrides still win, and a candidate
  remains routable). A future follow-up could surface `candidate` in the CLI
  `models` output / cockpit and in scorecard provenance.
- No model facts/benchmarks were invented or changed; the numbers stay as the
  vendor/aggregator snapshot they already were — now correctly marked unverified.
