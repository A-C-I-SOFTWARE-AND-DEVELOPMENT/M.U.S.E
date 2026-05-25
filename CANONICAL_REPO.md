# Canonical Repo Declaration — JARVIS Prime

This file declares the canonical source of truth for JARVIS Prime runtime
work across the two Hermes mirrors. It is intentionally short, durable,
and load-bearing: branching, review, and merge discipline depend on it.

## Source of Truth

`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent` is the canonical source of
truth for the JARVIS Prime runtime. All future JARVIS Prime runtime work
must branch from this repo's `main` and merge back through it.

`echerd27-design/hermes-agent` is treated as a legacy / specification
mirror. It may carry historical JARVIS Prime context (operating-system
doc, skill spec, design notes) and is allowed to diverge for reference
purposes, but it is **not** the canonical runtime. Code there should be
considered out-of-date unless someone has intentionally synced it from
ACI.

## No Parallel-Repo Editing

No contributor (human or agent) should edit JARVIS Prime files in both
repos in parallel. Before starting any JARVIS Prime work, the operator
declares which repo is canonical for that change. Default: ACI.

If a sync from ACI → echerd27-design is intentional, it is one-way,
explicit, and documented in the sync commit message.

## Role Assignment

- **Claude Code** is the primary implementer. It writes the foundation,
  the runtime modules, the schemas, the tests, and the docs.
- **Codex** is the reviewer / bounded-fix worker / second-pass engineer.
  It does not implement Wave 0 foundation work. It reviews after Claude
  Code lands a feature branch, and may take narrowly-scoped fix tickets.
- Claude Code and Codex **must not** edit the same branch at the same
  time. The operator (Jeremiah) chooses which agent owns a branch at any
  given moment.

## Owner-Gated Actions

The following actions require explicit owner authorization with the
phrase **`Yes, with authorization.`** before they may be performed by
any agent operating in this repo:

- merging any branch into `main`;
- deploying to any environment;
- publishing a package to PyPI, npm, or any other registry;
- submitting to an app store or marketplace;
- changing DNS records;
- rotating or changing secrets, API keys, or credentials;
- public posting (blog, social, mailing list, release notes);
- spending money on third-party services;
- destructive operations (`git push --force`, `git reset --hard` on
  shared branches, dropping data stores, deleting branches that hold
  unmerged work).

## Branching Rules

- Do not edit `main` directly.
- Feature work goes on its own branch named for the wave/lane.
- Wave 0 foundation work uses a single branch and lands before any
  Wave 1 feature lane is opened.
- Wave 1 feature lanes are parallel and each gets its own branch.
- Wave 2 lands all feature lanes into a single integration branch:
  `integration/jarvis-prime-runtime`.
- Wave 3 is Codex independent review.
- Wave 4 is the owner-approved merge of the integration branch into
  `main`.

## Done Definition

No agent calls work "done" without verification evidence. Verification
evidence means commands actually run, output captured, and either a
green result or a clearly-named failure mode with cause.

See `docs/jarvis-prime-wave-plan.md` for the full wave plan.
