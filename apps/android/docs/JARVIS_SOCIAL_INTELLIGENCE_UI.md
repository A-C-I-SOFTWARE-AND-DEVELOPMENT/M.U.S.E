# Jarvis Prime Social Intelligence — UI

This document describes the Memory screen and Social Speech Pattern
data model that the Android companion app uses to surface, audit, and
delete Jarvis Prime's learned speech patterns.

## What this is

Jarvis Prime learns **abstract communication patterns** — how a class
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

## Data model

`com.aci.hermes.data.model.SocialPattern` carries:

- `id`, `title`, `kind` (`SocialPatternKind`) — what kind of speech
  pattern this is, picked from the allowed list above.
- `summary` — an abstract description of the pattern. No identity.
- `safeUsage` — when and how Jarvis Prime may apply the pattern.
- `unsafeUsage` — what Jarvis Prime must never do with the pattern.
- `provenance` — public, citable sources (`PatternProvenance`).
- `privacyRisk` — `LOW`, `MEDIUM`, `HIGH`. Set by the redactor.
- `identityFlags` — list of token kinds the redactor detected.
- `correctedFrom` — id of the previous version if the user corrected
  the pattern.

`MemoryCategory.SOCIAL_SPEECH_PATTERN` is the Memory-screen category
this data lives under.

## The privacy redactor

`com.aci.hermes.data.social.PrivacyRedactor` is the privacy boundary.

It detects and replaces with `[redacted]`:

- handles like `@alice`, `u/alice`
- platform URLs like `twitter.com/alice`, `github.com/alice`
- emails, phone numbers
- `Firstname Lastname`-shaped tokens (with a small whitelist for place
  names)

It rejects provenance entries whose URL is auth-walled or points at a
specific profile (DMs, inbox, account, login-bound paths, common
platform profile URLs).

`PrivacyRedactor.sanitize` runs at write time **and** at render time
so older stored data benefits from any tightening of the rules.

## Screens

### Memory screen (`MemoryScreen`)

- Shows the selected `MemoryCategory` (currently always Social Speech
  Pattern).
- Shows a privacy legend card so the user knows what is and isn't
  stored.
- Renders a `SocialPatternCard` for each stored pattern.
- Empty-state copy invites the user to teach Jarvis Prime over time.
- Entry point: the Orchestrator screen's overflow menu, "Memory".

### Social pattern card (`SocialPatternCard`)

- Shows title, kind chip, privacy-risk chip.
- Truncates the summary to ~180 chars; HIGH-risk patterns show the
  summary as hidden with a prompt to delete or correct.
- Shows `Private identity flagged: ...` when any identity tokens were
  detected.
- Tap → detail screen.

### Social pattern detail (`SocialPatternDetail`)

- Header card with title, kind, privacy-risk chip, identity flags.
- High-risk banner when `privacyRisk == HIGH`. Summary stays hidden.
- Sections:
  - **Pattern summary** — the abstract description.
  - **Safe usage** — when and how to apply the pattern.
  - **Unsafe usage — never do this** — explicit do-not-do block.
  - **Provenance (public sources)** — list of `PatternProvenance`
    entries with kind, optional URL, optional note.
- Actions:
  - **Correct** — opens an inline edit card; "Save correction" persists
    a sanitized replacement and records `correctedFrom`.
  - **Delete** — confirms, then removes the pattern.

## Tests

JVM tests live under `apps/android/app/src/test/java/com/aci/hermes/data/social/`:

- `PrivacyRedactorTest` — username/email/phone/real-name redaction,
  flag classification, HIGH/MEDIUM/LOW risk mapping, provenance
  filtering, idempotence.
- `SocialPatternRepositoryTest` — upsert sanitizes on write, delete
  removes, correct replaces and re-sanitizes, deleteAll empties.

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

## Integration with Settings reset

`SettingsScreen` "Reset all settings and tasks" clears social pattern
storage too, via `SocialPatternRepository.deleteAll()` injected into
`SettingsViewModel`. Reset is the user's nuclear option.

## Threat model

| Threat                                       | Mitigation                                                |
|----------------------------------------------|-----------------------------------------------------------|
| Identity token slips into a learned pattern  | `PrivacyRedactor.sanitize` at write + render time         |
| Auth-walled or private URL is cited          | `sanitizeProvenance` drops the entry                      |
| Stale rules let old data leak                | Re-sanitize on read in `SocialPatternRepository.loadFromDisk` |
| User wants the pattern gone                  | One-tap delete in detail screen                           |
| User wants the pattern adjusted              | "Correct" action keeps the id, records `correctedFrom`    |
| Anything dangerous to do with the pattern    | Explicit "Unsafe usage — never do this" section           |
