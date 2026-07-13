# JARVIS Self-Efficient LLM Coder Research Dossier

## Goal

Build JARVIS Prime into a local-first coding partner that can take natural
language requests, inspect the repo, localize the correct files, prepare a
bounded work packet, route work to the right builder/reviewer, verify results,
learn from outcomes, and improve its own process without losing owner control.

## Research synthesis

### What strong coding agents have in common

1. **Agent-computer interface matters.** SWE-agent's research argues agents
   perform better when given purpose-built interfaces for repository navigation,
   file editing, and test execution instead of a generic chat surface.
2. **Execution-grounded verification matters.** Recent agent frameworks focus on
   mandatory sandbox execution because plausible code is not enough.
3. **Human-in-the-loop remains mandatory.** Modern sandboxes and coding agents
   still need human supervision for exception handling, credentials, destructive
   actions, and production changes.
4. **Memory should be operational, not decorative.** Useful memory preserves
   repo lessons, repeated failures, successful prompts, test commands, source
   hierarchy, worker routing decisions, and rollback patterns.
5. **Natural-language coding must become packets.** The system should convert
   speech like “fix the login bug” into mission, repo root, allowed files,
   forbidden files, branch, tests, reviewer, owner gates, rollback.

## JARVIS coding law

No serious code edit without localization first.

Every coding task should pass through:

```text
Understand → Localize → Plan → Build → Verify → Review → Package → Learn
```

## Implemented in this local ZIP

- `hermes_cli/jarvis_prime/natural_language_coder.py`
- `tests/test_jarvis_prime_natural_language_coder.py`

It adds a small router that converts natural language requests into bounded
coding work packets using the canonical worker posture:

- Primary builder: `claude-code-windows`
- Reviewer / bounded fix worker: `codex`
- Local/runtime worker: `hermes-local`

## JARVIS-native worker roles

| Worker | Best use | Must not do |
|---|---|---|
| `hermes-local` | inspect, classify, run safe local checks, compile context | make high-risk changes without packet |
| `claude-code-windows` | primary implementation | approve its own work |
| `codex` | review, bounded fixes, second-pass engineering | edit same branch at same time as builder |
| `aider` / `goose` / `chatgpt-handoff` | optional fallback lanes | bypass Hermes gates |

## Evaluation metrics

Track each coding session with:

- localization accuracy
- files touched vs allowed files
- tests selected vs tests needed
- first-pass test success
- reviewer findings count
- security findings count
- rollback completeness
- owner-gate compliance
- time to useful answer
- memory usefulness on next similar task

## Next build lane

Wire `natural_language_coder.build_work_packet()` into JARVIS Prime CLI:

```text
python -m hermes_cli.jarvis_prime packet draft "fix the memory bug"
python -m hermes_cli.jarvis_prime packet validate packet.json
python -m hermes_cli.jarvis_prime handoff --intent "fix..." --packet packet.json
```

## Hard no-go lines

- No unbounded agent swarm.
- No edits without branch/scope.
- No merge/deploy/publish/account/credential actions without owner approval.
- No fake “done” without verification evidence or a stated skip reason.
