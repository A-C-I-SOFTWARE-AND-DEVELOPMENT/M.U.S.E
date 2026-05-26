# JARVIS Prime — Audit & Proof History

The Audit & Proof History screen is the operator-facing record of
everything JARVIS Prime did, why it did it, who approved it, and what
evidence backs the result. The surface is built so a single glance
answers four questions:

1. What did JARVIS do?
2. Why was it allowed to do it?
3. Did verification pass — and if it didn't, that fact is impossible to miss.
4. Can it be undone?

## Where it lives

- Route: `Screen.Audit` (`audit`) — list of audit records.
- Route: `Screen.AuditDetail` (`audit/{auditId}`) — proof detail for one record.
- Entry point: the history icon in `OrchestratorScreen`'s top app bar.
- Source: `apps/android/app/src/main/java/com/aci/hermes/ui/screens/audit/`.
- Data: `apps/android/app/src/main/java/com/aci/hermes/data/audit/`.

## Data model

The ledger is split into two halves so the list is fast and the
detail view holds the long-form material:

| Model | Purpose |
| --- | --- |
| `AuditRecord` | One thing JARVIS did. Fields: `timestamp`, `userRequest`, `action`, `riskTier`, `route`, `approvalState`, `result`, `confidence`, link to `proofId`. Renders in the list. |
| `ProofRecord` | The full proof of work. Holds `rationale`, `evidence`, `testsRun`, `filesChanged`, `verification`, `approvals`, `rollback`, `impactReport`, `workerRuns`. |
| `EvidenceItem` | One artifact: diff, log, screenshot, metric, test report, doc link, or command output. |
| `RouteSummary` | Where the request went after classification (local worker, Codex, Claude, Hermes gateway, human only), plus reason and elapsed time. |
| `ApprovalHistoryItem` | One approval event with approver, state, comment, and timestamp. |
| `RollbackPlan` | Reversal steps, whether the plan is automatic, whether it has already executed. |
| `VerificationResult` | Aggregate verification status with the failing and passing checks. |
| `WorkerRun` | One backend worker invocation that contributed to the action. |

All models are `kotlinx.serialization` `@Serializable` data classes,
identical in shape to what the JARVIS Prime ledger emits, so the
gateway swap is a deserializer change rather than a model rewrite.

## Composables

| Composable | Role |
| --- | --- |
| `AuditScreen` | Top-level list. Empty state when there are no records. |
| `AuditCard` | One row in the list. Color-coded by result; failed results carry a visible "Failed verification" badge. |
| `AuditDetailScreen` | Container for a single record's proof. |
| `ProofDetail` | Rationale + files changed + tests run + evidence. |
| `FailedVerificationCard` | Red-tinted card that surfaces a failed `VerificationResult`. Pinned above the rest of the detail so it cannot be missed. |
| `ApprovalHistoryCard` | Approval timeline. Highlighted when risk tier is `SERIOUS` or `CRITICAL`. |
| `WorkerRunCard` / `WorkerRunsSection` | One worker run + the section heading. |
| `RollbackCard` | The rollback plan with status chip (Executed / Armed / Manual). |
| `ImpactReportCard` | Shown only for `CRITICAL`-tier records — explicit blast-radius statement. |

## Rules enforced in the UI

- **No secrets in audit UI.** Every string the UI renders is passed
  through `SecretRedactor` at the repository boundary. The redactor
  catches: API key / token / password / secret assignments,
  `Authorization` headers, common provider tokens (OpenAI, GitHub,
  AWS, Google), JWTs, and PEM private key blocks. Detection is
  intentionally over-eager — false positives are cheaper than a
  leaked credential.
- **Failed verification is obvious.** A failed `VerificationResult`
  renders as a dedicated red card with an error icon and a list of
  the failing checks, pinned directly under the summary so it is the
  first thing on screen. The list view marks the same record with a
  red badge.
- **Serious / critical approvals are visible.** `ApprovalHistoryCard`
  uses the secondary container surface and adds an "Approval
  required" chip whenever the record's risk tier is `SERIOUS` or
  `CRITICAL`.
- **Critical actions carry an impact report.** When the risk tier is
  `CRITICAL` and an `impactReport` is present, `ImpactReportCard`
  renders above `ProofDetail`.
- **Mock data is allowed.** `DefaultMockAuditSeed` provides
  representative cases (trivial success, moderate refactor failure,
  serious schema change, critical credential rotation that
  rolled back, blocked release). When the JARVIS gateway lands,
  replace the seed with a network-backed source — the rest of the
  stack does not need to change.

## Tests

JVM unit tests live in `apps/android/app/src/test/java/com/aci/hermes/`:

- `data/audit/AuditRepositoryTest`
  - audit list renders with mock data
  - every record has a resolvable proof (proof detail can open)
  - failed verification state is present in the seed
  - approval history is present for serious/critical records
  - critical records expose an impact report
  - secret-like values are scrubbed before display (both default
    seed and an injected poisoned seed)
- `data/audit/SecretRedactorTest` — covers the redaction patterns
  (assignments, auth headers, provider tokens, JWTs, PEM blocks).
- `ui/screens/audit/AuditFormattingTest` — formatting helpers used
  by the screens.

Run:

```bash
cd apps/android && ./gradlew assembleDebug
cd apps/android && ./gradlew :app:testDebugUnitTest
```

## Wiring the live gateway

To replace the mock seed, implement an `AuditSeed` (or a
streaming variant of `AuditRepository`) that reads from the JARVIS
ledger. Construction stays a single line in `AppContainer`:

```kotlin
val auditRepository: AuditRepository = AuditRepository(seed = LiveJarvisAuditSeed(api))
```

All redaction happens inside the repository, so callers never see
unredacted material regardless of source.
