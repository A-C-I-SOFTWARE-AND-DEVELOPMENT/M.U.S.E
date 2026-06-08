package com.aci.hermes.data.audit

import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.model.audit.ActionResult
import com.aci.hermes.data.model.audit.ApprovalHistoryItem
import com.aci.hermes.data.model.audit.ApprovalState
import com.aci.hermes.data.model.audit.AuditRecord
import com.aci.hermes.data.model.audit.EvidenceItem
import com.aci.hermes.data.model.audit.EvidenceKind
import com.aci.hermes.data.model.audit.ProofRecord
import com.aci.hermes.data.model.audit.RiskTier
import com.aci.hermes.data.model.audit.RollbackPlan
import com.aci.hermes.data.model.audit.RouteDestination
import com.aci.hermes.data.model.audit.RouteSummary
import com.aci.hermes.data.model.audit.VerificationResult
import com.aci.hermes.data.model.audit.VerificationStatus
import com.aci.hermes.data.model.audit.WorkerRun
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map

/** Sync state of the audit ledger against the cockpit gateway. */
sealed interface AuditSync {
    data object Idle : AuditSync
    data object Loading : AuditSync
    /** No gateway paired — records are the local/preview seed, not live. */
    data object MockOnly : AuditSync
    data class Loaded(val count: Int) : AuditSync
    data class Error(val message: String) : AuditSync
}

/**
 * Read access to the MUSE audit + proof ledger.
 *
 * - **Paired** (a [client] + [paired]==true): [refresh] pulls the real
 *   decision-ledger audit list (`GET /v1/cockpit/audit`); proofs are fetched
 *   on demand via [fetchProof] (`GET /v1/cockpit/audit/{id}/proof`) and
 *   cached. No mock data is shown.
 * - **Unpaired / preview / tests**: falls back to the [seed]. Production
 *   wires [EmptyAuditSeed] + a client, so nothing fake reaches a paired user.
 *
 * All reads pass through [SecretRedactor] before display.
 */
class AuditRepository(
    seed: AuditSeed = DefaultMockAuditSeed,
    private val client: HermesCockpitClient? = null,
    private val paired: () -> Boolean = { false },
) {

    private val recordsState: MutableStateFlow<List<AuditRecord>> =
        MutableStateFlow(seed.records().redactedForDisplay())

    private val proofsState: MutableStateFlow<Map<String, ProofRecord>> =
        MutableStateFlow(
            seed.proofs().map { it.redactedForDisplay() }.associateBy(ProofRecord::auditId)
        )

    val records: StateFlow<List<AuditRecord>> = recordsState.asStateFlow()

    private val _sync: MutableStateFlow<AuditSync> = MutableStateFlow(AuditSync.Idle)
    val sync: StateFlow<AuditSync> = _sync.asStateFlow()

    val isLive: Boolean get() = client != null && paired()

    /** Pull the live audit list from the gateway when paired. */
    suspend fun refresh() {
        val c = client
        if (c == null || !paired()) {
            _sync.value = AuditSync.MockOnly
            return
        }
        _sync.value = AuditSync.Loading
        when (val res = c.auditList()) {
            is CockpitResult.Success -> {
                recordsState.value = res.value.records.map { it.toDomain() }.redactedForDisplay()
                _sync.value = AuditSync.Loaded(recordsState.value.size)
            }
            is CockpitResult.Failure ->
                _sync.value = AuditSync.Error("Gateway error ${res.httpStatus}: ${res.error.message}")
            is CockpitResult.Unreachable ->
                _sync.value = AuditSync.Error(res.message)
        }
    }

    /**
     * The proof bundle for [auditId] — served from cache, else fetched from
     * the gateway on demand (when paired) and cached. Drives [proofFor].
     */
    suspend fun fetchProof(auditId: String): ProofRecord? {
        proofsState.value[auditId]?.let { return it }
        val c = client
        if (c != null && paired()) {
            val res = c.auditProof(auditId)
            if (res is CockpitResult.Success) {
                val proof = res.value.toDomain().redactedForDisplay()
                proofsState.value = proofsState.value + (proof.auditId to proof)
                return proof
            }
        }
        return null
    }

    fun proofFor(auditId: String): Flow<ProofRecord?> =
        proofsState.map { it[auditId] }

    fun proofSnapshot(auditId: String): ProofRecord? = proofsState.value[auditId]
}

/** Empty seed for production: nothing fake before the gateway responds. */
object EmptyAuditSeed : AuditSeed {
    override fun records(): List<AuditRecord> = emptyList()
    override fun proofs(): List<ProofRecord> = emptyList()
}

interface AuditSeed {
    fun records(): List<AuditRecord>
    fun proofs(): List<ProofRecord>
}

private object DefaultMockAuditSeed : AuditSeed {

    private const val DAY_MS = 24L * 60 * 60 * 1000
    private val now: Long = System.currentTimeMillis()

    override fun records(): List<AuditRecord> = listOf(
        AuditRecord(
            id = "aud_001",
            timestamp = now - 12 * 60 * 1000,
            userRequest = "Rename the onboarding banner copy",
            action = "Edited apps/web/src/components/Banner.tsx",
            riskTier = RiskTier.TRIVIAL,
            route = RouteSummary(
                destination = RouteDestination.LOCAL_WORKER,
                model = "jarvis-local-edit",
                reason = "Single file copy change with no schema impact.",
                durationMs = 1_840,
            ),
            approvalState = ApprovalState.UNNECESSARY,
            result = ActionResult.SUCCESS,
            confidence = 0.97f,
            proofId = "prf_001",
        ),
        AuditRecord(
            id = "aud_002",
            timestamp = now - 2 * 60 * 60 * 1000,
            userRequest = "Add server-side rate limit to /api/login",
            action = "Implemented middleware + tests across 3 files",
            riskTier = RiskTier.MODERATE,
            route = RouteSummary(
                destination = RouteDestination.CODEX,
                model = "codex-mid",
                reason = "Touches auth surface; routed to Codex for diff quality.",
                durationMs = 42_300,
            ),
            approvalState = ApprovalState.APPROVED,
            result = ActionResult.SUCCESS,
            confidence = 0.88f,
            proofId = "prf_002",
        ),
        AuditRecord(
            id = "aud_003",
            timestamp = now - 6 * 60 * 60 * 1000,
            userRequest = "Migrate users table to add stripe_customer_id",
            action = "Generated migration 0042_user_stripe_id.sql",
            riskTier = RiskTier.SERIOUS,
            route = RouteSummary(
                destination = RouteDestination.CLAUDE,
                model = "claude-sonnet",
                reason = "Schema change on production table — serious tier requires explicit approval.",
                durationMs = 18_400,
            ),
            approvalState = ApprovalState.APPROVED,
            result = ActionResult.SUCCESS,
            confidence = 0.81f,
            proofId = "prf_003",
        ),
        AuditRecord(
            id = "aud_004",
            timestamp = now - 1 * DAY_MS,
            userRequest = "Refactor the notification dispatcher",
            action = "Rewrote NotificationDispatcher.kt and updated callers",
            riskTier = RiskTier.MODERATE,
            route = RouteSummary(
                destination = RouteDestination.CODEX,
                model = "codex-mid",
                reason = "Cross-file refactor with regression risk.",
                durationMs = 64_120,
            ),
            approvalState = ApprovalState.APPROVED,
            result = ActionResult.FAILED,
            confidence = 0.42f,
            proofId = "prf_004",
        ),
        AuditRecord(
            id = "aud_005",
            timestamp = now - 2 * DAY_MS,
            userRequest = "Roll keys for the staging postgres user",
            action = "Rotated DATABASE_URL secret and re-deployed worker",
            riskTier = RiskTier.CRITICAL,
            route = RouteSummary(
                destination = RouteDestination.HERMES_GATEWAY,
                model = "hermes-policy-runner",
                reason = "Touches credentials + live infra. Critical tier — impact report required.",
                durationMs = 7_900,
            ),
            approvalState = ApprovalState.APPROVED,
            result = ActionResult.ROLLED_BACK,
            confidence = 0.55f,
            proofId = "prf_005",
        ),
        AuditRecord(
            id = "aud_006",
            timestamp = now - 3 * DAY_MS,
            userRequest = "Push the marketing changes to production",
            action = "Blocked — awaiting human approval (serious tier)",
            riskTier = RiskTier.SERIOUS,
            route = RouteSummary(
                destination = RouteDestination.HUMAN_ONLY,
                model = null,
                reason = "Production deploy outside the standard release window.",
                durationMs = 0,
            ),
            approvalState = ApprovalState.PENDING,
            result = ActionResult.BLOCKED,
            confidence = 0.0f,
            proofId = "prf_006",
        ),
    )

    override fun proofs(): List<ProofRecord> = listOf(
        ProofRecord(
            id = "prf_001",
            auditId = "aud_001",
            rationale = "Copy-only change; one file, no behavior delta. JARVIS handled locally.",
            evidence = listOf(
                EvidenceItem(
                    id = "ev_001a",
                    kind = EvidenceKind.DIFF,
                    title = "Banner.tsx",
                    body = "- Welcome aboard!\n+ Welcome to Hermes",
                    sourcePath = "apps/web/src/components/Banner.tsx",
                ),
            ),
            testsRun = listOf("vitest apps/web/src/components/Banner.test.tsx"),
            filesChanged = listOf("apps/web/src/components/Banner.tsx"),
            verification = VerificationResult(
                status = VerificationStatus.PASSED,
                summary = "1/1 checks passed",
                failingChecks = emptyList(),
                passedChecks = listOf("vitest"),
            ),
            approvals = emptyList(),
            rollback = null,
            impactReport = null,
            workerRuns = listOf(
                WorkerRun(
                    id = "wr_001",
                    worker = "local-edit-worker",
                    startedAt = now - 13 * 60 * 1000,
                    finishedAt = now - 12 * 60 * 1000 - 10_000,
                    status = ActionResult.SUCCESS,
                    notes = "Edit applied in 1.8s",
                ),
            ),
        ),
        ProofRecord(
            id = "prf_002",
            auditId = "aud_002",
            rationale = "Auth-surface change; routed to Codex. Tests added before merge.",
            evidence = listOf(
                EvidenceItem(
                    id = "ev_002a",
                    kind = EvidenceKind.DIFF,
                    title = "rateLimit.ts (new)",
                    body = "export const loginLimiter = rateLimit({ windowMs: 60000, max: 10 })",
                    sourcePath = "apps/api/src/middleware/rateLimit.ts",
                ),
                EvidenceItem(
                    id = "ev_002b",
                    kind = EvidenceKind.TEST_REPORT,
                    title = "vitest run",
                    body = "PASS apps/api/src/middleware/rateLimit.test.ts (8 tests)",
                ),
            ),
            testsRun = listOf(
                "vitest apps/api/src/middleware/rateLimit.test.ts",
                "vitest apps/api/src/routes/login.test.ts",
            ),
            filesChanged = listOf(
                "apps/api/src/middleware/rateLimit.ts",
                "apps/api/src/middleware/rateLimit.test.ts",
                "apps/api/src/routes/login.ts",
            ),
            verification = VerificationResult(
                status = VerificationStatus.PASSED,
                summary = "All 12 checks passed",
                failingChecks = emptyList(),
                passedChecks = listOf("vitest", "eslint", "tsc"),
            ),
            approvals = listOf(
                ApprovalHistoryItem(
                    id = "ap_002a",
                    timestamp = now - 2 * 60 * 60 * 1000 - 4 * 60 * 1000,
                    approver = "jeremiah",
                    state = ApprovalState.APPROVED,
                    comment = "Looks good. Ship it.",
                ),
            ),
            rollback = RollbackPlan(
                id = "rb_002",
                summary = "Revert merge commit to remove middleware wiring.",
                steps = listOf(
                    "git revert <merge-sha>",
                    "Redeploy api service",
                ),
                automatic = false,
                executed = false,
            ),
            impactReport = null,
            workerRuns = listOf(
                WorkerRun(
                    id = "wr_002a",
                    worker = "codex-mid",
                    startedAt = now - 2 * 60 * 60 * 1000 - 60 * 1000,
                    finishedAt = now - 2 * 60 * 60 * 1000 - 18_000,
                    status = ActionResult.SUCCESS,
                    notes = "Generated patch with 2 follow-up tests.",
                ),
            ),
        ),
        ProofRecord(
            id = "prf_003",
            auditId = "aud_003",
            rationale = "Schema change against the users table. Serious tier — requires named approver.",
            evidence = listOf(
                EvidenceItem(
                    id = "ev_003a",
                    kind = EvidenceKind.DIFF,
                    title = "0042_user_stripe_id.sql",
                    body = "ALTER TABLE users ADD COLUMN stripe_customer_id text NULL;",
                    sourcePath = "db/migrations/0042_user_stripe_id.sql",
                ),
                EvidenceItem(
                    id = "ev_003b",
                    kind = EvidenceKind.METRIC,
                    title = "Row count check",
                    body = "users: 47,212 rows — NULLABLE column, zero-downtime.",
                ),
            ),
            testsRun = listOf("psql --dry-run db/migrations/0042_user_stripe_id.sql"),
            filesChanged = listOf("db/migrations/0042_user_stripe_id.sql"),
            verification = VerificationResult(
                status = VerificationStatus.PASSED,
                summary = "Migration linter + dry-run OK",
                failingChecks = emptyList(),
                passedChecks = listOf("migration-lint", "psql-dry-run"),
            ),
            approvals = listOf(
                ApprovalHistoryItem(
                    id = "ap_003a",
                    timestamp = now - 6 * 60 * 60 * 1000 - 30 * 60 * 1000,
                    approver = "jeremiah",
                    state = ApprovalState.PENDING,
                    comment = "Need eyes on this before it lands.",
                ),
                ApprovalHistoryItem(
                    id = "ap_003b",
                    timestamp = now - 6 * 60 * 60 * 1000 - 10 * 60 * 1000,
                    approver = "jeremiah",
                    state = ApprovalState.APPROVED,
                    comment = "Approved. NULLABLE keeps it reversible.",
                ),
            ),
            rollback = RollbackPlan(
                id = "rb_003",
                summary = "Drop the new nullable column.",
                steps = listOf("ALTER TABLE users DROP COLUMN stripe_customer_id;"),
                automatic = true,
                executed = false,
            ),
            impactReport = null,
            workerRuns = listOf(
                WorkerRun(
                    id = "wr_003",
                    worker = "claude-sonnet",
                    startedAt = now - 6 * 60 * 60 * 1000 - 40_000,
                    finishedAt = now - 6 * 60 * 60 * 1000 - 22_000,
                    status = ActionResult.SUCCESS,
                    notes = "Drafted migration + dry-run script.",
                ),
            ),
        ),
        ProofRecord(
            id = "prf_004",
            auditId = "aud_004",
            rationale = "Refactor produced compiling code but downstream tests fail. Verification gate held the change.",
            evidence = listOf(
                EvidenceItem(
                    id = "ev_004a",
                    kind = EvidenceKind.DIFF,
                    title = "NotificationDispatcher.kt",
                    body = "- fun dispatch(n: Notification) = legacyBus.send(n)\n+ fun dispatch(n: Notification) = newRouter.route(n)",
                    sourcePath = "apps/android/app/src/main/java/.../NotificationDispatcher.kt",
                ),
                EvidenceItem(
                    id = "ev_004b",
                    kind = EvidenceKind.TEST_REPORT,
                    title = "Gradle test report",
                    body = "FAILED NotificationDispatcherTest.legacyConsumersStillReceive (4 tests failing)",
                ),
                EvidenceItem(
                    id = "ev_004c",
                    kind = EvidenceKind.LOG,
                    title = "Logcat excerpt",
                    body = "E/Dispatcher: no consumer registered for channel=legacy.email",
                ),
            ),
            testsRun = listOf(
                "./gradlew :app:testDebugUnitTest",
                "./gradlew :app:lintDebug",
            ),
            filesChanged = listOf(
                "apps/android/app/src/main/java/com/aci/hermes/notify/NotificationDispatcher.kt",
                "apps/android/app/src/main/java/com/aci/hermes/notify/Router.kt",
                "apps/android/app/src/main/java/com/aci/hermes/ui/screens/orchestrator/OrchestratorViewModel.kt",
            ),
            verification = VerificationResult(
                status = VerificationStatus.FAILED,
                summary = "4 test failures in NotificationDispatcherTest; verification blocked the change.",
                failingChecks = listOf(
                    "NotificationDispatcherTest.legacyConsumersStillReceive",
                    "NotificationDispatcherTest.priorityOrderPreserved",
                    "NotificationDispatcherTest.deadLetterFallback",
                    "NotificationDispatcherTest.cancellationPropagates",
                ),
                passedChecks = listOf("lintDebug"),
            ),
            approvals = listOf(
                ApprovalHistoryItem(
                    id = "ap_004a",
                    timestamp = now - 1 * DAY_MS - 30 * 60 * 1000,
                    approver = "jeremiah",
                    state = ApprovalState.APPROVED,
                    comment = "Go ahead with the refactor.",
                ),
            ),
            rollback = RollbackPlan(
                id = "rb_004",
                summary = "Revert the refactor commit; legacy bus path is still in place.",
                steps = listOf(
                    "git revert <refactor-sha>",
                    "./gradlew :app:assembleDebug",
                ),
                automatic = true,
                executed = false,
            ),
            impactReport = null,
            workerRuns = listOf(
                WorkerRun(
                    id = "wr_004",
                    worker = "codex-mid",
                    startedAt = now - 1 * DAY_MS - 90_000,
                    finishedAt = now - 1 * DAY_MS - 25_000,
                    status = ActionResult.FAILED,
                    notes = "Patch applied but verification gate failed. No merge.",
                ),
            ),
        ),
        ProofRecord(
            id = "prf_005",
            auditId = "aud_005",
            rationale = "Credential rotation against live infra. Critical tier — full impact report + auto rollback armed.",
            evidence = listOf(
                EvidenceItem(
                    id = "ev_005a",
                    kind = EvidenceKind.COMMAND_OUTPUT,
                    title = "rotate-secret output",
                    body = "Rotated DATABASE_URL — old credential disabled at 2026-05-24T10:02:11Z.\n" +
                        "DATABASE_URL=postgres://hermes:s3cretP@ss@db.internal/hermes",
                    sourcePath = "scripts/rotate-secret.sh",
                ),
                EvidenceItem(
                    id = "ev_005b",
                    kind = EvidenceKind.LOG,
                    title = "Deploy log",
                    body = "worker-7f3c restarted; healthcheck failing for 90s; rollback triggered.",
                ),
            ),
            testsRun = listOf("scripts/healthcheck.sh worker-staging"),
            filesChanged = listOf(".env.staging"),
            verification = VerificationResult(
                status = VerificationStatus.FAILED,
                summary = "Staging worker failed healthcheck after rotation; automatic rollback executed.",
                failingChecks = listOf("worker-staging healthcheck"),
                passedChecks = listOf("secret-rotation"),
            ),
            approvals = listOf(
                ApprovalHistoryItem(
                    id = "ap_005a",
                    timestamp = now - 2 * DAY_MS - 5 * 60 * 1000,
                    approver = "jeremiah",
                    state = ApprovalState.APPROVED,
                    comment = "Approved rotation; rollback must be armed.",
                ),
            ),
            rollback = RollbackPlan(
                id = "rb_005",
                summary = "Restored prior DATABASE_URL and redeployed worker.",
                steps = listOf(
                    "Re-enable previous credential in secret store",
                    "Redeploy worker-staging",
                    "Verify healthcheck passes",
                ),
                automatic = true,
                executed = true,
            ),
            impactReport = "Affected: worker-staging (1 service). User-visible downtime: 90s. " +
                "Blast radius: staging only — production untouched. Action: rollback restored prior state.",
            workerRuns = listOf(
                WorkerRun(
                    id = "wr_005a",
                    worker = "hermes-policy-runner",
                    startedAt = now - 2 * DAY_MS - 60_000,
                    finishedAt = now - 2 * DAY_MS - 50_000,
                    status = ActionResult.SUCCESS,
                    notes = "Rotated credential.",
                ),
                WorkerRun(
                    id = "wr_005b",
                    worker = "deploy-runner",
                    startedAt = now - 2 * DAY_MS - 45_000,
                    finishedAt = now - 2 * DAY_MS - 5_000,
                    status = ActionResult.ROLLED_BACK,
                    notes = "Healthcheck failed; auto-rollback executed.",
                ),
            ),
        ),
        ProofRecord(
            id = "prf_006",
            auditId = "aud_006",
            rationale = "Production push outside release window. JARVIS held the change pending human approval.",
            evidence = listOf(
                EvidenceItem(
                    id = "ev_006a",
                    kind = EvidenceKind.DOC_LINK,
                    title = "Release window policy",
                    body = "docs/governance/release-windows.md — production deploys allowed Mon-Thu 09:00-16:00 PT.",
                ),
            ),
            testsRun = emptyList(),
            filesChanged = emptyList(),
            verification = VerificationResult(
                status = VerificationStatus.SKIPPED,
                summary = "No verification run — change blocked before execution.",
                failingChecks = emptyList(),
                passedChecks = emptyList(),
            ),
            approvals = listOf(
                ApprovalHistoryItem(
                    id = "ap_006a",
                    timestamp = now - 3 * DAY_MS,
                    approver = "jeremiah",
                    state = ApprovalState.PENDING,
                    comment = "Awaiting approver decision.",
                ),
            ),
            rollback = null,
            impactReport = "Would deploy marketing site to production outside the standard release window. " +
                "Estimated user reach: ~12k DAU. Reversible via standard redeploy.",
            workerRuns = emptyList(),
        ),
    )
}

private fun List<AuditRecord>.redactedForDisplay(): List<AuditRecord> = map { it.redactedForDisplay() }

private fun AuditRecord.redactedForDisplay(): AuditRecord = copy(
    userRequest = SecretRedactor.redact(userRequest),
    action = SecretRedactor.redact(action),
    route = route.copy(reason = SecretRedactor.redact(route.reason)),
)

private fun ProofRecord.redactedForDisplay(): ProofRecord = copy(
    rationale = SecretRedactor.redact(rationale),
    evidence = evidence.map { it.copy(body = SecretRedactor.redact(it.body)) },
    approvals = approvals.map { it.copy(comment = it.comment?.let(SecretRedactor::redact)) },
    rollback = rollback?.copy(
        summary = SecretRedactor.redact(rollback.summary),
        steps = rollback.steps.map(SecretRedactor::redact),
    ),
    impactReport = impactReport?.let(SecretRedactor::redact),
    workerRuns = workerRuns.map { it.copy(notes = SecretRedactor.redact(it.notes)) },
    verification = verification.copy(
        summary = SecretRedactor.redact(verification.summary),
        failingChecks = verification.failingChecks.map(SecretRedactor::redact),
        passedChecks = verification.passedChecks.map(SecretRedactor::redact),
    ),
)
