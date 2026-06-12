# Hermes — Plain-English Communication Principles

> **Status:** Product-level communication rules. Companion to
> [`muse-10-10-product-spec.md`](muse-10-10-product-spec.md).
> Every string the user reads or hears in Hermes — from a job card
> to a validation report to a spoken readback — follows these
> principles.

The product is mobile-first and often used while driving. The user
should be able to:

- glance at a job card and understand it in one second,
- hear a readback and act on it without re-asking,
- ask "why?" and get an answer they can repeat to a non-engineer.

If they can't, the product has failed regardless of how good the
underlying agent is.

---

## 1. The five rules

### Rule 1 — Lead with the bottom line

Every message starts with the answer, not the process.

- **Good.** *"Audit done. Top risk: an `.env` was committed in
  March 2025. Two smaller risks below."*
- **Bad.** *"I ran a comprehensive audit using the
  github-repo-audit worker on Opus 4.7. The audit took 47
  seconds. Here are the findings…"*

If the user only reads the first line, they should still know what
happened.

### Rule 2 — One paragraph per idea

A summary is one paragraph. A "why" is one paragraph. A status is
one paragraph. Lists are bullets, not numbered sub-clauses.

- **Good.** *"I sent this to Windows Claude Code on Opus 4.7
  because it had the best score on Python refactors this week and
  your profile prefers Opus for this repo. Codex CLI was the
  next-best pick."*
- **Bad.** Three paragraphs explaining radar scoring.

Power users tap "show details" for the structured data. The
default view is one paragraph.

### Rule 3 — No jargon without expansion

Every acronym is expanded on first use *on each screen*. Provider
names, model names, and tool names are written the way the user
named them, not the way the API names them.

- **Good.** *"Vercel's preview deploy failed during the
  npm-install step."*
- **Bad.** *"Vercel preview deploy lambda cold-start oom-killed
  the build runner."*

Engineering acronyms (CI, PR, API, LLM, STT) are allowed on the
power-user surface; on the primary surface they are written out:
*"continuous integration"*, *"pull request"*, *"the model"*, etc.

### Rule 4 — Name the operator's action

If the message requires the user to do something, the action is
named and reachable.

- **Good.** *"Validation failed: two unit tests broke. **Show
  failing tests** · **Re-run** · **Skip and publish** (logged)."*
- **Bad.** *"Validation failed."* (No actions.)
- **Bad.** *"An error occurred during validation. Please review
  the logs."* (Vague action.)

In voice mode, the action is named in the readback: *"Validation
failed. Do you want me to re-run, show the failing tests, or skip
and publish?"*

### Rule 5 — No raw model / system output on the primary surface

Stack traces, JSON dumps, provider error blobs, and tool outputs
live behind a **Show details** affordance. The default view is
plain English.

- **Good.** *"Supabase rejected the migration: the column
  `users.created_at` is already not-null. **Show details** for
  the SQL."*
- **Bad.** Pasting `{"code":"42704","message":"column already…"}`
  on the card.

---

## 2. Concrete patterns

### 2.1 Job-card summary

The one paragraph on every job card answers:

1. **What is the job?** ("Refactor `pkg/foo`.")
2. **What phase is it in?** ("Validating now.")
3. **What's next?** ("Will open a PR if validation passes.")
4. **Does it need me?** ("Nothing for you to do yet.")

### 2.2 Gate decision

When a gate passes:

> *"Plan looks good: under budget, in scope, matches your style.
> Approve to send to Windows Claude Code."*

When a gate fails:

> *"Plan exceeded the scope you set ('only `pkg/foo`'). I want to
> touch `pkg/bar` too. Approve to expand the scope, edit the plan,
> or reject."*

### 2.3 Validation report bottom line

> *"Promised contract met. Safe to publish."*

or

> *"Two unit tests broke and ruff has one new finding. Don't
> publish yet."*

### 2.4 Routing explanation

> *"I sent this to Windows Claude Code on Opus 4.7 because it has
> the best score on Python refactors this week and your profile
> prefers Opus for this repo. I'd have picked Codex CLI if Claude
> Code were busy."*

### 2.5 Failure surfaces

> *"Workstation `home-win-01` is unreachable — last seen 12
> minutes ago. **Retry** · **Reassign worker** · **Cancel**."*

### 2.6 Spoken readback (driving mode)

> *"Audit complete. Top risk: an environment file was committed
> last March. Two smaller risks. Want me to read the full report?"*

---

## 3. Things to never say

- *"An error occurred."* (Useless.)
- *"Please try again later."* (Useless without an ETA.)
- *"Internal server error."* (Leak; say what the user can do.)
- *"Tool call failed."* (Jargon; say *"I couldn't do X."*)
- *"LLM call returned 5xx."* (Jargon; say *"The model didn't respond. I'll retry."*)
- *"Hallucination detected."* (Jargon; say *"That answer wasn't supported by the evidence. I'm re-running."*)
- *"Token limit exceeded."* (Jargon; say *"The conversation is getting long. I'm summarizing it to keep going."*)
- *"Permission denied."* without naming what was denied and what's needed.

When in doubt: read the line out loud. If you'd be embarrassed to
say it to a non-engineer, rewrite it.

---

## 4. Voice-specific principles

Voice readbacks add three rules on top of the five above.

1. **Lead with the headline, hold the detail.** *"Audit done.
   Three risks. Want the top one?"* not a 90-second monologue.
2. **Accept a small command set.** In driving mode the user can
   only say a fixed list of phrases. The system tells them which
   ones it accepts when they go off-script.
3. **Confirm destructive actions verbally.** If the user is
   approving something destructive by voice, the system reads the
   action back and requires *"Hermes, confirm"* before acting. No
   approval is a single-utterance click.

---

## 5. Style for written copy

- **Sentence case** in headings and buttons. (*"Approve plan"*,
  not *"APPROVE PLAN"* or *"Approve Plan"*.)
- **Active voice.** (*"Hermes routed this to…"*, not *"This was
  routed by Hermes to…"*.)
- **Present tense for current state, past tense for completed
  events.** (*"Validating now"* vs. *"Validated 12 s ago"*.)
- **No exclamation points** unless reporting genuine danger.
- **No emoji** in copy except for two reserved markers:
  - 🔒 to denote private mode is on.
  - ⚠ to denote a gate or validation failure.
  Both are paired with text; neither is used decoratively.
- **No quoted code on the primary surface** unless the user has
  tapped "show details."
- **Numbers in figures**: prefer "12 s" over "12 seconds" when
  space-constrained; otherwise spell out.
- **Dates and times in the user's locale**, with a relative
  fallback ("12 s ago", "3 h ago").

---

## 6. The "show details" affordance

Every plain-English message has an optional **Show details**
affordance that reveals:

- The raw tool output (stdout / stderr / API response).
- The structured ledger entries that backed the summary.
- The model / worker / environment metadata.
- The cost and latency of the call.

The default view never shows these. Power users opt in per card.

---

## 7. The readability bar

We hold ourselves to a measurable bar:

- **Flesch–Kincaid grade ≤ 9** on every primary-surface string.
- **No primary-surface string longer than 240 characters** without
  a "show details" toggle.
- **No primary-surface string with more than two sentences**
  unless it is a validation-report body.
- **Every error message** has at least one named action.

These are enforced in CI by a copy-lint that scans
`apps/android/app/src/main/res/values/strings.xml`, the gateway's
response templates, and the validation-report template.

---

## 8. Examples — before / after

### 8.1 A bad routing explanation, rewritten

**Before.**
> *"Routing decision: anthropic/claude-opus-4-7 selected with
> confidence 0.91 over openai/gpt-5 (0.83) and codex-cli (0.78)
> per ai-improvement-radar/2026-05-week-20.yaml; budget OK
> ($0.04/$0.20); profile rule prefer_opus_for_python=true."*

**After.**
> *"I sent this to Windows Claude Code on Opus 4.7 because it has
> the best score on Python refactors this week and your profile
> prefers Opus for this repo. Codex CLI was the next-best pick."*

### 8.2 A bad failure card, rewritten

**Before.**
> *"PR creation failed: `gh: graphql error: Resource not
> accessible by integration`."*

**After.**
> *"Couldn't open the pull request. The GitHub token doesn't have
> permission to write PRs on this repo. **Re-connect GitHub** ·
> **Show details**."*

### 8.3 A bad validation report bottom line, rewritten

**Before.**
> *"Pipeline status: 7/9 passed. Some non-blocking lint warnings.
> See artifacts."*

**After.**
> *"Two unit tests broke and ruff has one new finding. Don't
> publish yet."*

---

## 9. Cross-references

- [`muse-10-10-product-spec.md`](muse-10-10-product-spec.md) — the spec these principles serve.
- [`muse-user-journeys.md`](muse-user-journeys.md) — every journey's readbacks follow these rules.
- [`muse-definition-of-done.md`](muse-definition-of-done.md) — DoD for plain-English explanations.
- [`muse-mobile-native-vision.md`](muse-mobile-native-vision.md) — voice readback rules.
