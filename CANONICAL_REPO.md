# Canonical Repo Declaration — JARVIS Prime Runtime

This document declares the canonical source of truth for the **JARVIS
Prime** runtime that lives inside Hermes, and the working rules every
contributor (human or agent) is expected to follow before touching it.

It is intentionally short. If anything in this file conflicts with a
verbal request, a chat instruction, or another doc, this file wins until
the owner updates it.

---

## 1. Canonical repository

The canonical source of truth for the JARVIS Prime runtime is:

```text
A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent
```

All runtime code, runtime tests, runtime docs, and runtime
configuration for JARVIS Prime should live here and be developed here
first.

The sister repository:

```text
echerd27-design/hermes-agent
```

is treated as a **legacy / spec mirror**. It may carry historical
specs, exploration branches, design notes, or earlier prototypes, but
it is **not** the source of truth for runtime behavior. Code in the
echerd27-design mirror may be older, divergent, or experimental and
must not be assumed to match ACI behavior.

Do not develop JARVIS Prime runtime work in both repositories in
parallel without first declaring, in writing, which repository is
canonical for that change. Parallel uncoordinated edits across both
repos are the failure mode this document exists to prevent.

## 2. Branching rules

- All future JARVIS Prime runtime work branches from `main` of the
  canonical ACI repo.
- Nobody (human or agent) edits `main` directly.
- Each feature lane gets its own branch — see
  `docs/jarvis-prime-wave-plan.md`.
- Claude Code and Codex must **not** be pointed at the same branch at
  the same time. Pick one editor per branch per window.

## 3. Roles

- **Claude Code** is the primary builder. It implements features,
  writes code, writes tests, and produces verification evidence.
- **Codex** is the reviewer, bounded fix worker, refactorer, and
  second-pass engineer. It should not be the primary author on a
  feature branch that Claude is actively building.
- **AOS Council** is invoked when a decision needs multi-perspective
  reasoning (architecture, risk, contrarian review, product, etc.).
- **Owner (Jeremiah Echerd)** owns final judgment, all `main` merges,
  and all owner-gated actions.

## 4. Owner-gated actions

The following actions require the exact authorization phrase:

```text
Yes, with authorization.
```

before any agent (Claude Code, Codex, or otherwise) may execute them:

- merging anything to `main`
- deploying or publishing to any environment
- publishing or uploading a package (PyPI, npm, app store, etc.)
- changing DNS records or domain configuration
- rotating, creating, or changing secrets or credentials
- spending money or invoking paid APIs the owner did not pre-approve
- posting publicly on the owner's behalf (social, blog, public PR
  comments on third-party repos, etc.)
- destructive git operations (force-push, history rewrite, branch
  deletion of shared branches)
- bulk file deletion or schema-destroying migrations

Owner gating means the action is **described and prepared**, but not
executed, until the owner replies with the exact phrase above.

## 5. Done-claim discipline

Nothing is "done" without verification evidence. At minimum, a done
claim includes:

- the exact commands run
- the actual output (pass/fail, counts, any errors)
- which files changed
- a one-line rollback note

If verification could not run (missing dep, missing secret, sandbox),
say so explicitly — do not pretend it passed.

## 6. Scope hygiene

Wave 0 (this branch) is foundation only. It does **not** ship the
immune layer, runtime enforcement, CLI expansion, proposal
persistence, mobile live mode, real Claude/Codex dispatch, GitHub
publishing automation, or deployment automation. Those land in later
waves on their own branches. See `docs/jarvis-prime-wave-plan.md`.
