# Canonical Repository for JARVIS Prime Runtime

## Source of truth

`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent` is the canonical source of truth
for the JARVIS Prime runtime. All runtime code, foundation modules, and
integration branches live here. CI, release tags, and any future deployment
artifacts are cut from this repository.

`echerd27-design/hermes-agent` is treated as a legacy/spec mirror. It may
hold earlier design drafts or experiments. It must not be used as the
implementation home for JARVIS Prime runtime unless an explicit, owner-approved
sync has been performed. Code that lands there without intentional sync from
the canonical repo is considered out-of-band and must not be merged into the
canonical `main` without re-review.

## Branching rules

- All future JARVIS Prime runtime work branches from `main` of the canonical
  repo (`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent`).
- No one edits multiple Hermes / JARVIS repositories in parallel without
  declaring which repo is canonical for the change. Cross-repo parallel
  edits on the same surface area are prohibited.
- Feature work uses dedicated feature branches. Wave 0 lock-down branch is
  `claude/jarvis-foundation-lock-g9i9x` (see `docs/jarvis-prime-wave-plan.md`).
- `main` is not edited directly. All merges to `main` require owner approval.

## Builder / reviewer split

- **Claude Code** is the primary implementer. It writes the code, runs local
  verification, and prepares pull requests.
- **Codex** is the primary reviewer. Codex performs bounded fixes, refactor
  passes, and second-pass engineering review on Claude-authored branches.
- Claude Code and Codex must not edit the same branch at the same time. A
  branch is owned by exactly one of them at any moment; handoffs are
  explicit.

## Owner-gated actions

The following actions are owner-gated and require the exact phrase

```text
Yes, with authorization.
```

before they may be executed:

- Merging any branch into `main`.
- Deploying any runtime, container, or service.
- Publishing packages to PyPI, npm, container registries, or any public
  package index.
- Submitting mobile or desktop apps to App Store, Play Store, or other
  distribution channels.
- Changing DNS records or any domain configuration.
- Rotating, replacing, or revoking secrets, API keys, or service
  credentials.
- Posting publicly (social media, blog, public GitHub issues on third-party
  repos, marketing channels).
- Spending money (paid APIs without an existing approved budget, cloud
  resources, paid tooling).
- Destructive operations: force-push to shared branches, hard reset of
  shared history, deletion of branches or tags, deletion of issues or PRs,
  database drops, or file deletions beyond the immediate scope of the work.

If a workflow appears to require one of these actions without explicit
authorization, the action is deferred and a request is surfaced to the owner
instead.

## Repo hygiene

- No duplicate JARVIS systems. Build on the existing JARVIS Prime files in
  `hermes_cli/jarvis_prime/` (created during Wave 0). Do not fork a parallel
  module tree.
- Runtime files for JARVIS Prime keep import-time dependencies to the Python
  standard library unless the repo already requires a heavier dependency for
  the surface in question.
- Termux compatibility is preserved. No platform-specific imports at module
  top level for JARVIS Prime runtime files.

## Pointers

- Operating system spec: `docs/jarvis-prime-operating-system.md`
- Wave plan and merge strategy: `docs/jarvis-prime-wave-plan.md`
- Verification gates: `docs/jarvis-verification-gates.md`
- Skill entry point: `skills/jarvis-prime/SKILL.md`
