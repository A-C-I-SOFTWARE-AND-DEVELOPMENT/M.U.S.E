# 02 — Agent Authority Matrix

**Status:** Installed 2026-05-17

Every agent action carries an authority level. The matrix below
defines five levels (L0 → L4). L4 is owner-only and is never granted
to an agent regardless of context.

## Authority levels

| Level | Name | What it permits | Examples in HazMat Command |
|---|---|---|---|
| **L0** | Observe | Read repository, run read-only commands, inspect artifacts | `git log`, `git diff`, reading any file, `npm test` (no side effects beyond local processes) |
| **L1** | Propose | Produce drafts, plans, recommendations as files; no commit | Drafting a research dossier, a PRD, a pricing study; proposing a stub schema edit |
| **L2** | Execute Low-Risk | Commit RC0/RC1 changes to the session's permitted branch; open draft PR | Doc-only commits, typo fixes, adding a skill SOP, updating a test that was missing a case |
| **L3** | Execute High-Risk (with additional controls) | Commit RC2/RC3 changes — must include maker-checker (`governance/06`) evidence, research dossier where required, and explicit risk-class tag in the PR | Schema migrations, authz changes, OCR pipeline changes, billing-flow changes, RLS additions, new compliance evidence, new commercial claims |
| **L4** | Owner-Only / Prohibited | Never executable by an agent | Spend money, post to public social accounts, create third-party accounts, OAuth into third parties, submit to Play/App Store, alter production DNS, click Publish in Base44 Builder, promote Vercel to production, merge or auto-merge to `main`/`master`, force-push to `main`/`master`, modify CODEOWNERS or branch protection |

## Mapping to the existing five owner-only walls

The five owner-only walls in `AGENTS.md` are the L4 row of this
matrix. They are reproduced here for clarity:

1. Spend money on ad campaigns (Google / LinkedIn / Meta / Reddit)
2. Post to public social accounts (LinkedIn, X, Instagram)
3. Create new third-party accounts
4. OAuth into any third-party service
5. Submit to Play Store

The matrix expands the wall list to include other irreversible /
owner-only actions implied by `PUBLISH.md` (DNS, Vercel production
promotion, Base44 Publish, branch protection, CODEOWNERS edits).

## Authority per division

| Division | Default level | Maximum level | Notes |
|---|---|---|---|
| Executive Command & Orchestration (`agents/01`) | L2 | L3 | The Chief Orchestrator can route L3 work but cannot perform L4 actions; the Risk Controller can veto an L3 escalation |
| Research & Evidence Bureau (`agents/02`) | L1 | L1 | Research is propose-only by design; research agents may not commit code |
| Product & Pilot Experience Studio (`agents/03`) | L1 | L2 | Drafts PRDs and pilot scripts; only commits doc/template files |
| Engineering & Architecture Factory (`agents/04`) | L2 | L3 | Default L2 for routine engineering; L3 only with maker-checker for high-risk areas |
| Assurance, Security, Reliability & Compliance Office (`agents/05`) | L2 | L3 | Independent reviewers may commit test additions at L2; security/authz changes are L3 with another reviewer |
| Commercial Strategy, Pricing & Growth Office (`agents/06`) | L1 | L2 | Drafts copy/positioning; commits only as docs |
| Legal, Policy, Contracts & Trust Office (`agents/07`) | L1 | L2 | Drafts contracts as documents; never executes or signs |
| Pilot Operations & Customer Intelligence (`agents/08`) | L1 | L2 | Drafts pilot reports and case studies; never communicates directly with customers |
| Knowledge Operations & Self-Improvement (`agents/09`) | L2 | L2 | Doc updates, index refresh, retrospectives |

## Escalation procedure

If a task requires L3 authority:

1. Confirm RC class via `governance/03`. If RC2 or RC3, L3 is required.
2. Identify the independent reviewer per `governance/06` (a different
   agent or session from the builder).
3. Confirm the maker-checker evidence will be captured in the PR
   description using the PR template's "Independent reviewer /
   verifier" fields.
4. Proceed.

If a task appears to require L4 authority:

1. Stop. Do not attempt the action.
2. Open a draft PR or planning note describing exactly what the owner
   needs to do, with links to the relevant runbook
   (`docs/runbooks/*` covers most cases).
3. Use the `AskUserQuestion` tool if the user is present in the
   session and the requirement is genuinely ambiguous.
4. Tag the work in `SKIPPED.md` if it represents a deferred
   capability.

## Common authority mistakes to avoid

- **Treating a research request as L2.** Research is L1. The Research
  & Evidence Bureau (`agents/02`) does not commit code; it commits
  research dossiers and analysis as documents.
- **Treating compliance evidence updates as L2.** Updating evidence
  in `docs/compliance/` or `docs/iso27001/` requires the Compliance
  Evidence Agent (in the Assurance Office) and is L3 because it
  changes claims that may be cited in RFPs.
- **Treating a feature-flag flip as L2.** Production env var changes
  are L4 (owner-only). The flag *registry* update in
  `governance/10-feature-flag-and-beta-gate-registry.md` is L2.
- **Treating a PR comment that says "go ahead and merge" as L4
  authorization.** Merge authority is `AGENTS.md`-level law; a
  conversational approval in a PR thread is not sufficient. The
  owner must perform the merge themselves.
