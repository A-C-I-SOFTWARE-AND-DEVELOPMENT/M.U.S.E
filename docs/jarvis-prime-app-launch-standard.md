# Jarvis Prime — Android App Launch Standard

> **Status:** product spec, v1. Companion to
> [`jarvis-prime-app-product-spec.md`](jarvis-prime-app-product-spec.md),
> [`jarvis-prime-app-user-flows.md`](jarvis-prime-app-user-flows.md),
> [`jarvis-prime-app-screen-map.md`](jarvis-prime-app-screen-map.md),
> [`jarvis-prime-app-onboarding-spec.md`](jarvis-prime-app-onboarding-spec.md).
>
> The launch readiness bar — what *"Jarvis Prime is ready to ship"*
> means. Every section here is a gate. A build that fails any one
> is not a launch candidate, regardless of how close the others
> are.

---

## 1. The four launch tracks

Launch is gated on four independent tracks. All four must pass.

| Track | Gate | Owner |
|---|---|---|
| **Product** | The eight verbs (talk · command · approve · monitor · remember · verify · stop · resume) all work end-to-end. | Product spec §1. |
| **Quality** | Twenty user flows pass on a physical Android device. | User flows doc. |
| **Safety** | Approvals, emergency stop, memory corrections, and audit are visibly trustworthy. | Product spec §6 + §8. |
| **Distribution** | Build is signed, store metadata is complete, support paths exist. | This doc, §6. |

---

## 2. Product gate

The build passes the product gate when **every cell of the verb
matrix is green**.

| Verb | What proves it works |
|---|---|
| **Talk** | Open app, single-tap icon → Chat opens, voice or text reply streams from a real gateway within 2 s of first byte. |
| **Command** | Voice capture → *Convert to task* → Tasks screen shows the new task within 2 s. |
| **Approve** | Risky, Serious, and Critical approvals each complete with the correct number of confirms; ledger entry appears in Audit within 2 s. |
| **Monitor** | Home tile shows current active task within 1 s of cold start; Tasks screen reflects SSE updates within 2 s of gateway emit. |
| **Remember** | Memory screen shows at least one durable fact; *Correct* and *Delete* both work and write audit entries. |
| **Verify** | Audit / Proof screen is reachable in one tap from Home and shows the last 24 h of consequential actions. |
| **Stop** | Double-tap icon → confirm → all approvals disabled in ≤ 1 s; emergency-stop banner visible app-wide. |
| **Resume** | From Stopped, Resume runs the gateway self-check and re-enables approvals only after the confirm phrase. |

If any cell fails on a physical device against a real gateway,
the build is not launch-ready.

---

## 3. Quality gate — user-flow acceptance

Every flow in
[`jarvis-prime-app-user-flows.md`](jarvis-prime-app-user-flows.md)
passes its **happy path**, its **named fallback paths**, and its
**offline behavior** on a physical mid-range Android device
running the minimum supported SDK (Android 8.0 / SDK 26) and the
latest supported SDK.

| # | Flow | Required to pass |
|---|---|---|
| 1 | Open app and see Jarvis status | happy path · cached state · emergency stop sticky |
| 2 | Ask Jarvis a casual question | happy path · stream interruption · out-of-scope (gated proposal) · offline outbox |
| 3 | Use voice capture | happy path · STT failure · mic denied · offline capture queue |
| 4 | Convert rough voice idea into a task | happy path · gateway 5xx draft retention · mobile-voice format · explicit defer |
| 5 | View active tasks | happy path · SSE drop · empty · failed task `View why` |
| 6 | Approve a risky action once | happy path · stale state · revoked · write 5xx · offline blocked |
| 7 | Approve a serious action — step one | happy path · screen-exit re-acknowledgement · evidence card missing |
| 8 | Approve a serious action — step two | happy path · step-one expired · stale state · wrong confirm phrase |
| 9 | Review a critical impact report | happy path · missing section · impact report unreachable |
| 10 | Reject an action | happy path · stale state · write 5xx · offline blocked |
| 11 | Trigger emergency stop | happy path · already stopped · cancelled · gateway never acknowledges · offline immediate |
| 12 | Correct memory | happy path · conflict · secret-shaped rejection · offline outbox |
| 13 | Delete memory | happy path · undo · bulk delete · offline outbox |
| 14 | View audit / proof history | happy path · ledger 5xx (cache) · export offline |
| 15 | Use the interactive icon | each of five gestures · state changes mid-gesture · reduce motion |
| 16 | Handle gateway disconnected state | happy path · wrong URL · TLS · 401 · reconnect flow |
| 17 | Use mock mode | happy path · mock banner persistence · switch-to-live confirm |
| 18 | Use Termux gateway mode | happy path · Termux not installed · Intent rejected · Doze kill recovery |
| 19 | Decline optional permissions and continue | happy path · don't-ask-again · revisit shortcut |
| 20 | Resume after emergency stop | happy path · self-check fail · degraded · cancel · offline blocked |

Each row in this table is a discrete test plan item. Sign-off
requires the device-based walkthrough to be performed once for the
launch build and recorded — the launch ledger entry references the
walkthrough run.

---

## 4. Safety gate

Safety is the third gate because launch failure on safety is
worse than launch failure on quality.

### 4.1 Approval safety

- No path in the app completes an approval without:
  - the correct number of confirm steps for its class
    (Risky=1, Serious=2, Critical=2 + Impact Report),
  - a server-side `Idempotency-Key`,
  - a final ledger entry,
  - and a green visual state on the card.
- Approvals are **never completable while offline.**
- Approvals are **never completable while emergency stop is
  engaged.**
- The phrase *"Yes, with authorization."* is the canonical voice
  phrase for two-step approvals and is preserved verbatim across
  locales.

### 4.2 Emergency stop safety

- Reachable from every screen via the icon's double-tap.
- Reachable via the voice phrase *"Jarvis, stop everything."*
- Reachable via long-press on the lock-screen widget.
- Local effect ≤ 200 ms.
- Resume is **never automatic** — no timer, no fallback, no
  "auto-resume on reconnect."
- Stop reconciles with the gateway when offline; local sticky
  state is never rolled back during retry.

### 4.3 Memory safety

- Every durable fact is visible, editable, and deletable.
- Secret-shaped content is refused at the gateway and surfaced as
  a rejection.
- Delete is one-step with a 5 s undo and a preserved ledger entry.
- *Should I remember this?* candidates are surfaced explicitly —
  never silently written.

### 4.4 Audit safety

- The ledger is read-only from the app.
- Owner annotations are new linked entries, never edits.
- Export is scrubbed of secrets and tokens (it does not include
  EncryptedSharedPreferences contents).
- Audit reaches one tap from Home.

### 4.5 Permissions safety

- Every permission is requested with a *Why* rationale **before**
  the system dialog.
- Declining never silently breaks a feature.
- *Don't ask again* (permanent denial) is detected and the *revisit*
  shortcut opens system settings.

### 4.6 Mode-swap safety

- Mock ↔ Live is a confirmed transition with a persistent banner.
- Mock mode cannot reach a real gateway.
- Termux gateway lifecycle is owner-initiated and logged.

### 4.7 Naming safety

- No user-visible string says *"Hermes"*. (Compatibility names
  like `com.aci.hermes`, `HermesService`, and `/v1/*` remain
  internal-only and never surface on screen.)
- The app label, all notification titles, voice readbacks,
  widget text, and store metadata say **Jarvis Prime**.

### 4.8 Distribution safety

- The release build is signed with the production keystore (not
  the debug keystore).
- `usesCleartextTraffic` is **off** in release manifest before the
  Google Play release. If LAN HTTP gateways are required for some
  users, a build flavor gates the cleartext flag with a clear
  *Cleartext-allowed* badge in Diagnostics; the Play Store release
  channel does not ship the cleartext-allowed flavor.
- No build secrets, tokens, or test API keys are present in any
  shipped resource (`strings.xml`, `BuildConfig`, embedded assets).

---

## 5. Performance and reliability bar

The following must be measured on a mid-range device
(approximately Pixel 6a or equivalent, 4 GB RAM, mid-tier
networking) before launch:

| Metric | Bar | Source |
|---|---|---|
| Cold start to Home (cached settings) | ≤ 1.5 s | Macrobench |
| Home first paint | ≤ 1.0 s | Macrobench |
| Chat stream first byte (healthy gateway) | ≤ 2.0 s | Manual on physical device |
| Approval write latency (healthy gateway) | ≤ 2.0 s | Manual on physical device |
| Voice capture transcript-to-screen | ≤ 1.0 s | Manual on physical device |
| Emergency stop local effect | ≤ 200 ms | Manual + automated UI test |
| Crash-free sessions (rolling 7 d in beta) | ≥ 99.5% | Crashlytics / equivalent |
| ANR rate (rolling 7 d in beta) | ≤ 0.1% | Crashlytics / equivalent |
| SSE reconnect after a forced kill | ≤ 30 s with backoff | Manual on physical device |

---

## 6. Distribution gate

### 6.1 App identity (user-visible)

| Field | Value |
|---|---|
| App name | **Jarvis Prime** |
| Tagline | *Talk. Command. Approve. Stop.* |
| Short description (80 chars) | *Your mobile-first AI operating partner. You stay in control.* |
| Long description | Pulled from §6.2 below. |
| Category | Productivity |
| Content rating | Everyone |
| Pricing | Free (no in-app purchases at launch) |

### 6.2 Long description copy (Play Store)

```
Jarvis Prime is a mobile-first AI operating partner.

From your phone, you can:

· Talk to Jarvis — voice or text, anywhere.
· Command — turn a rough idea into a runnable task.
· Approve — sign off risky, serious, and critical actions with
  the right level of friction. No silent autopilot.
· Monitor — see active tasks, pending approvals, and the last
  thing Jarvis did, at a glance.
· Remember — inspect, correct, and delete the durable memory
  Jarvis is using.
· Verify — audit every consequential action in plain English.
· Stop — emergency stop is one gesture, any screen.
· Resume — only when you say so.

Jarvis Prime connects to a Jarvis Prime gateway you run — on a
server, a VPS, or Termux on the same phone. It never silently
swaps modes, never auto-approves, never writes memory without
asking.
```

### 6.3 App identity (internal — preserved for compatibility)

| Field | Value | Reason |
|---|---|---|
| Package id | `com.aci.hermes` | Existing installs / signed releases. |
| Foreground service class | `com.aci.hermes.service.HermesService` | Manifest stability. |
| Gateway client class | `HermesGatewayClient` | Wire-format stability. |
| Gateway path | `/v1/*` | Backend contract. |

The user never sees any of these.

### 6.4 Assets required

- High-resolution app icon (512×512, foreground / background
  layered).
- Feature graphic (1024×500).
- Phone screenshots (minimum 4):
  1. Jarvis Home with status, icon, and tiles.
  2. Chat mid-stream.
  3. Approval detail with a Critical Impact Report.
  4. Audit / Proof timeline.
- Optional: 7-inch and 10-inch tablet screenshots.
- Optional: a 30-second preview video (Home → Chat → Approval →
  Audit).

### 6.5 Privacy and store compliance

- **Data Safety form.** Declare:
  - Audio (microphone): collected only when voice mode is active,
    processed on-device by default, optional cloud STT with
    per-session opt-in.
  - Personal info: only what the owner enters into Chat, Memory,
    or Tasks. Stored on the owner's gateway, not on a Jarvis Prime
    server.
  - App activity: log buffer kept in-memory and surfaced in
    Diagnostics only.
  - Device id: not collected.
  - Encrypted storage on device for tokens and provider keys.
- **Privacy policy.** Hosted at a stable URL and linked from
  Settings → About → Privacy policy.
- **Account deletion.** Not applicable (no Jarvis Prime cloud
  account). Settings → Reset → *Clear everything* removes all
  local data.

### 6.6 Support paths

- **In-app.** Settings → About → *Help* and *Report an issue* link
  to the docs and the GitHub issue tracker.
- **Diagnostics bundle.** Owner can attach the scrubbed bundle to
  any support request from Diagnostics → *Export diagnostics
  bundle*.
- **Versioned docs.** The product spec, user flows, screen map,
  onboarding spec, and this launch standard are all linked from
  the in-app *About* section.

---

## 7. Beta program

Before public launch, a **closed beta** runs for at least 14 days
with the following gates:

- At least 3 distinct testers on at least 3 distinct device models
  including one Android 8 / SDK 26 device.
- At least one tester runs the Termux gateway mode end-to-end.
- At least one tester runs Mock mode end-to-end.
- At least one full pass of the twenty user flows on a real
  gateway is recorded and the recording is attached to the launch
  ledger entry.
- Crash-free sessions ≥ 99.5% over the rolling 7 days before
  promotion.

The beta surfaces are:

- Google Play **Internal testing** → **Closed testing** → **Open
  testing** (optional) → **Production**.
- The debug APK distributed via GitHub Releases for testers who
  prefer sideloading.

---

## 8. Release procedure

Owner-gated (Critical class). Requires the confirm phrase *"Yes,
with authorization."*

1. **Cut the release branch.** `release/v<X.Y.Z>` off `main` after
   the merge-train is green.
2. **Bump version.** `versionName` + `versionCode` in
   `app/build.gradle.kts`.
3. **Build.** `./gradlew bundleRelease` with the production
   keystore from `apps/android/keystore.properties` (gitignored).
4. **Smoke test.** Install the release AAB on at least one
   physical device against the production gateway. Walk through
   the verb matrix in §2.
5. **Upload to Play.** Internal testing track first.
6. **Smoke test on Play.** Update from the internal track on a
   second device; confirm signature, install, cold start to Home,
   one Chat round-trip, one approval round-trip.
7. **Promote to closed testing.** 24 h soak with the closed
   group.
8. **Promote to production.** Owner approval — Critical class.
   Impact Report includes:
   - what changes (new app version),
   - who sees it (all current installs + Play Store visitors),
   - what can break (regression in approvals, gateway
     compatibility, signing chain),
   - rollback (downgrade via Play Internal track + halt rollout),
   - why now (release notes).
9. **Write the launch ledger entry.** Classification *publish*,
   actor *owner*, action *"Released Jarvis Prime <version> to
   Google Play."*

The release rollout uses **staged rollout** (5% → 25% → 50% →
100%) with at least 24 h between bumps unless a regression
demands a halt.

---

## 9. Post-launch monitoring

For the first 14 days after the production promotion:

- Daily check on crash-free sessions and ANR rate.
- Daily check on Play Store reviews ≤ 3 stars; triage on the same
  day.
- Weekly check on Diagnostics-bundle reports.
- The audit ledger records each release-related action (publish,
  rollback, hotfix) on the gateway side.

If any of:

- crash-free sessions < 99.0%,
- ANR rate > 0.5%,
- a critical security report (CVE-class),
- an approval-bypass bug,
- a memory-write-without-consent bug,
- an emergency-stop-failure bug,

is detected, the rollout is halted within 1 hour and a hotfix
branch is opened. Halt is itself an Owner Gate (Critical).

---

## 10. Acceptance checklist (the one-page version)

Pin this in the release ledger. Every box must be checked before
the launch ledger entry is written.

### Product

- [ ] Talk: Chat opens in one tap and replies stream within 2 s.
- [ ] Command: Voice → Convert to task → task visible in Tasks.
- [ ] Approve: Risky / Serious / Critical all complete with the
      correct gates.
- [ ] Monitor: Home tile updates within 1 s of cold start.
- [ ] Remember: Memory list visible, *Correct* and *Delete* both
      work.
- [ ] Verify: Audit reachable in one tap from Home; last 24 h
      visible.
- [ ] Stop: Double-tap icon → emergency stop in ≤ 1 s, app-wide
      sticky.
- [ ] Resume: Confirm phrase required; self-check runs first.

### Quality

- [ ] All 20 flows pass on a physical device.
- [ ] All 20 flows' offline behaviors pass.
- [ ] Crash-free sessions ≥ 99.5% in beta.
- [ ] ANR rate ≤ 0.1% in beta.

### Safety

- [ ] No path completes an approval without correct confirms +
      ledger entry.
- [ ] Approvals blocked offline and blocked while stopped.
- [ ] Emergency stop reachable from every screen.
- [ ] Resume is never automatic.
- [ ] No user-visible string says *Hermes*.
- [ ] `usesCleartextTraffic` is off in the Play Store release
      variant.
- [ ] Diagnostics export is scrubbed of secrets.

### Distribution

- [ ] Signed release AAB with production keystore.
- [ ] Play Store metadata complete (icon, screenshots, long
      description, privacy policy).
- [ ] Data Safety form complete and accurate.
- [ ] Beta program ran ≥ 14 days with ≥ 3 testers on ≥ 3 device
      models.
- [ ] Staged rollout plan (5% → 25% → 50% → 100%) prepared.
- [ ] Support paths (in-app Help, Report an issue, Diagnostics
      bundle) functional.
- [ ] Companion docs (`jarvis-prime-app-product-spec.md`,
      `jarvis-prime-app-user-flows.md`,
      `jarvis-prime-app-screen-map.md`,
      `jarvis-prime-app-onboarding-spec.md`, and this file)
      cross-link and exist in `docs/`.

---

## 11. Cross-references

- [`jarvis-prime-app-product-spec.md`](jarvis-prime-app-product-spec.md)
  — the product promise this launch certifies.
- [`jarvis-prime-app-user-flows.md`](jarvis-prime-app-user-flows.md)
  — the twenty flows the quality gate exercises.
- [`jarvis-prime-app-screen-map.md`](jarvis-prime-app-screen-map.md)
  — the surfaces the safety gate inspects.
- [`jarvis-prime-app-onboarding-spec.md`](jarvis-prime-app-onboarding-spec.md)
  — the first-run path that distribution must preserve.
- [`jarvis-prime-operating-system.md`](jarvis-prime-operating-system.md)
  — the runtime identity Jarvis Prime presents on launch.
- [`jarvis-verification-gates.md`](jarvis-verification-gates.md)
  — the verification gates the gateway enforces; this doc covers
  app-side verification for the launch itself.
- [`apps/android/README.md`](../apps/android/README.md)
  — technical compatibility surface; release procedure in §8
  references its build instructions.
