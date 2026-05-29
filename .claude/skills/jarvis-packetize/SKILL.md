---
name: jarvis-packetize
description: Turn a plain-English request into a bounded JARVIS work packet (intent, risk, owner gates, allowed files, verification, rollback) without executing anything.
---

# jarvis-packetize

Use when the owner describes work in plain English and you need a bounded,
reviewable, gate-compatible packet **before** any execution.

## Steps
1. Run the packetizer:
   ```bash
   python -m hermes_cli.jarvis_prime packetize "<request>" --markdown
   ```
2. Validate and gate-check:
   ```bash
   python -m hermes_cli.jarvis_prime packet "<request>" --validate
   python -m hermes_cli.jarvis_prime packet "<request>" --gate-check
   ```
3. If the packet is `RC4`/blocked, stop — it is plan-only. Do not execute
   owner-gated actions; surface them for the owner.
4. Hand the packet to a builder; route review to a *different* worker for
   RC2+.

## Never
- Never merge/deploy/publish or perform Android gestures from this skill.
- Never widen `allowed_files` or target `main`/`master`.
