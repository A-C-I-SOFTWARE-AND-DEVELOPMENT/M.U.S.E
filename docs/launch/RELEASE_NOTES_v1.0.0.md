# MUSE — Runtime v1.0.0 launch notes

> Companion to the package release tracked in `pyproject.toml`
> (currently `0.14.1+aci.1`). The `1.0.0` here describes the
> **runtime** semver for MUSE itself — the local-first AI
> operating partner that ships inside `hermes_cli/jarvis_prime/`.
> A separate package version bump to `1.0.0` will happen after the
> CLI wiring + emergency-stop primitives have soaked in production.

## TL;DR

MUSE is now invocable from the interactive `hermes` CLI
via `/jarvis`, `/jp`, or `/jarvis-prime`, has a documented emergency
stop, persists memory locally with hardened secret rejection and
owner-only file perms, and gates 16 categories of risky action
behind the exact phrase **`Yes, with authorization.`**.

## What shipped

### Runtime (`hermes_cli/jarvis_prime/`, 18 modules)

- `persona.py` — six-mode persona prompts (Companion / Strategy /
  Critic / Operator / Builder / Mobile Voice).
- `modes.py` + `router.py` — mode classifier + routing hierarchy
  (Jeremiah → MUSE → AOS council → specialists → skills → workers).
- `awareness.py` — six parallel awareness streams with 2 s timeouts.
- `memory.py` — three-tier memory (working / session / durable),
  recollection, secret-pattern rejection, journal persistence at
  `~/.hermes/jarvis_prime/memory.jsonl` (file mode `0o600`).
- `reasoning.py` + `research.py` + `epistemics.py` — deductive +
  inductive reasoning, research-brief escalation, anti-hallucination
  audit.
- `gates.py` — eight verification gates (Planning, Build, Review,
  Test, Security, Release, Owner Approval, Rollback).
- `owner_auth.py` — exact-phrase enforcement for 16 owner-gated
  action categories.
- `self_update.py` — owner-gated proposal book for skill / agent /
  routing / runtime / memory-promotion / gate updates.
- `onboarding.py` — local-only, opt-in onboarding capabilities.
- `social_research.py` — public-API only (Reddit / HN / GitHub /
  Lobsters / dev.to); auth-walled platforms excluded.
- `communication_style.py` — turn-taking + cadence policy.
- `runtime.py` — orchestrator that ties everything together and
  ships a new **`stop(reason)`** primitive (see Emergency Stop).
- `tick.py` — proactive cycle (disabled by default).
- `__main__.py` — CLI subcommands: `perceive / classify / gate /
  handle / tick / stop / forget / remember / recollect`.

### CLI surface

Interactive `hermes` CLI now accepts:

```
/jarvis <intent>          # full perceive → classify → decide → route
/jp <intent>              # alias
/jarvis-prime <intent>    # canonical
/jarvis stop              # emergency stop (clears pending gates, disables tick)
```

And from any shell:

```
python -m hermes_cli.jarvis_prime stop           # emergency stop
python -m hermes_cli.jarvis_prime forget --key K
python -m hermes_cli.jarvis_prime remember --key K --value V [--durable]
python -m hermes_cli.jarvis_prime recollect "query" --limit 5
python -m hermes_cli.jarvis_prime handle "any intent"
```

### Owner Authorization Contract

MUSE defers these 16 action categories until the owner
replies with the exact phrase `Yes, with authorization.`:

`spend_money`, `post_publicly`, `create_third_party_account`,
`oauth_change`, `credential_change`, `production_deploy`,
`dns_change`, `main_branch_merge`, `force_push`, `package_publish`,
`app_store_submission`, `delete_recovered_sources`,
`modify_secrets`, `change_default_active_agents`,
`registry_mutation`, `regulated_claim` (legal / compliance /
security / health / financial).

There is no env-var or config override. Minor variants
("yes with authorization", "approved", "go ahead") do **not**
authorize.

### Emergency Stop

`JarvisPrime.stop(reason="…")` is the safety brake:

- Clears every pending owner gate.
- Sets `proactive_tick_enabled = False`.
- Journals a STOP record (`key="emergency_stop"`) to session memory.
- Returns `{"cleared": N, "tick_disabled": True, "reason": …,
  "cleared_actions": [...]}`.

Available from:

- `/jarvis stop` in the interactive CLI.
- `python -m hermes_cli.jarvis_prime stop` from any shell.
- Python: `JarvisPrime().stop(reason="…")`.

### Memory Privacy

`_FORBIDDEN_PATTERNS` rejects writes containing OpenAI / GitHub /
Slack tokens, generic `api_key=` / `password=` / `bearer …` kv,
AWS access keys (`AKIA…`), US SSNs, major-brand credit card
numbers, PEM / OpenSSH / EC / DSA / PGP / ENCRYPTED private key
headers, and JWT-shaped tokens.

The journal file is `chmod 0o600` on every write (best-effort —
no-op on platforms where the call fails).

## Android companion

Permissions remain minimal: `POST_NOTIFICATIONS`,
`FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_DATA_SYNC`. The app gains:

- A static **Owner Approve** app shortcut (long-press the launcher
  icon).
- A second notification action on the foreground service:
  **Owner Approve**, which deep-links into the approval flow inside
  `MainActivity`.

Quick-settings tile is deferred to v1.1.

## Migration

No breaking changes. MUSE is dormant until:

1. You invoke `/jarvis`, `/jp`, or `/jarvis-prime` in the CLI, or
2. You set `jarvis_prime.proactive_tick: enabled` in
   `~/.hermes/config.yaml` (off by default), or
3. You import `hermes_cli.jarvis_prime` directly.

## Rollback procedure

If anything goes sideways:

1. **Stop in place**: `python -m hermes_cli.jarvis_prime stop`.
2. **Disable proactive tick**: ensure
   `jarvis_prime.proactive_tick: disabled` in
   `~/.hermes/config.yaml` (the default).
3. **Avoid the slash commands**: nothing else activates MUSE
   Prime.
4. **Package downgrade (last resort)**:
   `pip install hermes-agent==0.14.0` — the previous release. The
   `jarvis_prime` package is additive; downgrading does not break
   any other Hermes feature.

See also the new "Disabling / Rolling Back MUSE" section
in `docs/jarvis-prime-operating-system.md`.

## Testing

- `tests/test_jarvis_prime_*.py` — 159 hermetic tests across the
  runtime modules.
- `tests/test_jarvis_prime_emergency_stop.py` — 3 new tests for the
  stop primitive.
- `tests/test_jarvis_prime_cli_wiring.py` — 3 new tests for slash
  registration.
- `tests/test_jarvis_prime_cli_memory.py` — 4 new tests for the
  `forget` / `remember` / `recollect` / `stop` subcommands.
- `tests/test_jarvis_prime_memory.py` — extended parametrized test
  for the new AWS / SSN / credit-card / PEM / JWT patterns.
- `tests/test_orchestrator_ledger.py` — 17 tests for the unified
  decision ledger at `~/.hermes/jobs/<job-id>/ledger.jsonl`.

Total local run: **381 passed, 1 skipped** (pre-existing skip).
