# muse Social Intelligence — UI

This document describes the Memory screen and Social Speech Pattern
data model that the Android companion app uses to surface, audit, and
delete muse's learned speech patterns.

## What this is

muse learns **abstract communication patterns** — how a class
of people typically writes (e.g. "engineers reply short on mobile") —
to make its own replies sound human. The Social Intelligence UI is
the user's review surface for that learning.

## What this is not

- It is not scraping.
- It is not identity profiling.
- It does not copy any specific person's voice.

The model is intentionally narrow:

| Allowed                              | Blocked                            |
|--------------------------------------|------------------------------------|
| Abstract communication patterns      | Usernames                          |
| Mobile reply patterns                | Real names                         |
| Disagreement patterns                | Private profile data               |
| Trust-building patterns              | Raw comment hoarding               |
| Support patterns                     | Impersonation                      |
| Technical triage patterns            | Manipulation tactics               |
| Public-source citations / provenance | Auth-walled / private scraping     |

The redactor and the UI both treat the blocked column as a hard
boundary. Patterns that contain identity tokens are flagged HIGH risk
and their summary is hidden until the user deletes or corrects them.

## Architecture — one memory store, a rich social view

There is **one** memory store: `com.aci.hermes.data.memory.MemoryRepository`,
holding generic `MemoryItem`s. Social speech patterns are ordinary
`MemoryItem`s with `MemoryCategory.SOCIAL_SPEECH_PATTERN`. The runtime
redactor `com.aci.hermes.data.memory.MemoryRedactor` strips identity
(usernames, handles, emails, phones) from every item before it reaches
the UI, replacing it with placeholder markers (`[identity]`,
`[handle]`, `[email]`, `[phone]`).

The Social Intelligence UI does not add a second store. Instead it
**projects** social-category `MemoryItem`s into a richer view model
for display:

- `ui/screens/memory/SocialPatternProjection.from(item)` →
  `com.aci.hermes.data.model.SocialPattern`.
- The projection infers the `SocialPatternKind` (from tags, else from
  text), derives **safe usage** (kind-specific) and **unsafe usage**
  (the universal muse boundary), maps the item's single
  provenance source into the public-source provenance list, and reads
  the runtime's redaction markers to flag identity.

### `SocialPattern` view model

`com.aci.hermes.data.model.SocialPattern` carries `id`, `title`,
`kind`, `summary`, `safeUsage`, `unsafeUsage`, `provenance`,
`privacyRisk` (`LOW`/`MEDIUM`/`HIGH`), and `identityFlags`. It is a
display projection, not a persisted record.

### The privacy redactor (defense in depth)

`com.aci.hermes.data.social.PrivacyRedactor` re-sanitizes the
projected `SocialPattern` at render time, independently of the
runtime redactor. It:

- detects handles (`@alice`, `u/alice`), platform profile URLs,
  emails, phones, and `Firstname Lastname`-shaped tokens, replacing
  them with `[redacted]`;
- recognizes the runtime's placeholder markers (`[identity]`, …) as
  evidence that identity was present and stripped upstream, so the
  card still shows "private identity flagged";
- classifies privacy risk (any identity evidence → `HIGH`, a lone
  real-name → `MEDIUM`, otherwise `LOW`);
- drops provenance entries whose URL is auth-walled or points at a
  personal profile (`sanitizeProvenance`).

`HIGH` risk hides the summary behind a "delete or correct" prompt.

## Screens

### Memory screen (`MemoryScreen`)

- Search + category filter chips over all `MemoryItem`s.
- For `SOCIAL_SPEECH_PATTERN` items it renders the rich
  `SocialPatternCard` (title, kind chip, privacy-risk chip, summary or
  hidden notice, "private identity flagged"); all other categories use
  the generic `MemoryCard`.
- Tap → `MemoryDetail` bottom sheet.

### Social pattern card (`SocialPatternCard`)

- Title, kind chip, privacy-risk chip.
- Summary truncated to ~180 chars; `HIGH`-risk patterns hide the
  summary with a delete/correct prompt.
- `Private identity flagged: ...` when markers/tokens are detected.

### Memory detail (`MemoryDetail`)

For social patterns the detail sheet renders a dedicated section
(`SocialPatternDetailSection`):

- privacy-risk chip + inferred kind chip;
- `Private identity flagged: ...` when applicable;
- **Pattern summary** — abstract description (hidden when `HIGH`);
- **Safe usage** — when and how to apply the pattern;
- **Unsafe usage — never do this** — the universal boundary;
- **Provenance (public sources)** — source title + kind + note.

Actions (shared with all memory items, via `MemoryViewModel`):

- **Correct** — `CorrectMemoryDialog`; persists a corrected,
  re-sanitized `MemoryItem` and emits a `MemoryAction.Correct`.
- **Delete** — `DeleteMemoryDialog`; removes the item and emits a
  `MemoryAction.Delete`.

## Tests

JVM tests:

- `data/social/PrivacyRedactorTest` — username/email/phone/real-name
  redaction, flag classification (incl. upstream markers),
  HIGH/MEDIUM/LOW risk mapping, provenance filtering, idempotence.
- `ui/screens/memory/SocialPatternProjectionTest` — clean pattern
  renders without identity (LOW), username-like strings redacted +
  private identity flagged (HIGH), handle markers flagged, kind
  inference (tag + text), universal unsafe usage, provenance mapping,
  safe usage present for every kind.
- `memory/MemoryRedactorTest`, `memory/MemoryRepositoryTest`,
  `memory/MemoryViewModelTest` — the shared store's correct/delete and
  identity-stripping behavior.

Run via:

```bash
cd apps/android
./gradlew testDebugUnitTest
```

The full debug APK is built with:

```bash
cd apps/android
./gradlew assembleDebug
```

## Threat model

| Threat                                       | Mitigation                                                       |
|----------------------------------------------|-----------------------------------------------------------------|
| Identity token slips into a learned pattern  | `MemoryRedactor` strips it upstream; `PrivacyRedactor` re-checks at render |
| Identity was stripped but should be surfaced | Redaction markers re-flag the pattern as `HIGH` / "private identity flagged" |
| Auth-walled or private URL is cited          | `PrivacyRedactor.sanitizeProvenance` drops the entry            |
| Two diverging stores                         | Single source of truth — `MemoryRepository`; the social view is a projection |
| User wants the pattern gone                  | One-tap delete in the detail sheet                              |
| User wants the pattern adjusted              | "Correct" action via `MemoryViewModel`, re-sanitized on save    |
| Anything dangerous to do with the pattern    | Explicit "Unsafe usage — never do this" section                |
