# JARVIS Companion, Memory Tree, and Avatar Implementation Packets

## Packet 1 — Memory Tree clean-room core

**Risk:** RC1  
**Allowed files:**

- `hermes_cli/jarvis_prime/memory_tree.py`
- `tests/test_jarvis_prime_memory_tree.py`
- `docs/jarvis_research/OPENHUMAN_MEMORY_TREE_CLEAN_ROOM_RESEARCH.md`

**Done in this ZIP:** yes.

**Acceptance:** chunks reject secrets, persist to JSONL, build outline, search,
and compile context packs.

## Packet 2 — Natural-language coder packetizer

**Risk:** RC1/RC2 depending on task.  
**Allowed files:**

- `hermes_cli/jarvis_prime/natural_language_coder.py`
- `tests/test_jarvis_prime_natural_language_coder.py`
- `docs/jarvis_research/SELF_EFFICIENT_LLM_CODER_RESEARCH_DOSSIER.md`

**Done in this ZIP:** yes.

**Acceptance:** plain English requests become bounded work packets with branch,
allowed files, forbidden files, verification, reviewer, rollback, and owner
approval when needed.

## Packet 3 — Companion presence policy

**Risk:** RC2.  
**Allowed files:**

- `hermes_cli/jarvis_prime/companion_presence.py`
- `tests/test_jarvis_prime_companion_presence.py`
- `docs/jarvis_architecture/LIVING_COMPANION_AVATAR_ARCHITECTURE.md`

**Done in this ZIP:** yes.

**Acceptance:** avatar states are deterministic; attention requires opt-in;
real device actions are separated from animation and owner-gated.

## Packet 4 — Android in-app mini avatar

**Risk:** RC2.  
**Allowed files:**

- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/live/**`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/avatar/**`
- `apps/android/app/src/test/**`
- `apps/android/docs/**`

**Not done in this ZIP:** implementation plan only.

**Acceptance:** mini companion mode exists in-app with no new permissions.

## Packet 5 — Android overlay companion

**Risk:** RC3.  
**Allowed files:**

- `apps/android/app/src/main/AndroidManifest.xml`
- `apps/android/app/src/main/java/com/aci/hermes/service/**`
- `apps/android/app/src/main/java/com/aci/hermes/ui/settings/**`
- `apps/android/docs/**`

**Not done in this ZIP:** owner-gated future lane.

**Acceptance:** overlay is opt-in, has education screen, timeout, emergency stop,
and does not obscure permission/payment/security dialogs.

## Packet 6 — Accessibility action broker

**Risk:** RC3.  
**Allowed files:**

- `apps/android/app/src/main/java/com/aci/hermes/accessibility/**`
- `apps/android/app/src/main/res/xml/**`
- `apps/android/docs/**`

**Not done in this ZIP:** owner-gated future lane.

**Acceptance:** every gesture/action is previewed, approved, executed, audited,
and reversible where possible.

## Packet 7 — Attention sensing

**Risk:** RC3 privacy.  
**Allowed files:**

- `apps/android/app/src/main/java/com/aci/hermes/vision/**`
- `apps/android/app/src/main/java/com/aci/hermes/ui/settings/**`
- `apps/android/docs/**`

**Not done in this ZIP:** owner-gated future lane.

**Acceptance:** camera is opt-in, no raw frames saved, no cloud upload, no durable
emotion inference, visible camera indicator.
