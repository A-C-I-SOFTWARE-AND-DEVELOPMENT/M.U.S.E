package com.aci.hermes.data.emergency

import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch
import java.util.UUID

/**
 * muse emergency stop controller. Owns the transition state
 * machine, action gating, and the audit log.
 *
 * Transition rules:
 *  - [engage] sets [EmergencyStopState.SOFT_PAUSE] (the floor for an
 *    engaged stop). Use [escalate] to climb.
 *  - [escalate] only ever raises the level; calling it with a level at
 *    or below the current one is a no-op.
 *  - Coming back down to [EmergencyStopState.INACTIVE] always goes
 *    through [requestResume] → [approveResume]. There is no direct
 *    [deescalate] to INACTIVE.
 *  - [deescalate] to [SOFT_PAUSE] from a higher level is permitted
 *    without approval but is still audited.
 *
 * The controller is process-wide and reads/writes through
 * [EmergencyStopRepository]; it must be created once and kept alive
 * for the lifetime of the app (see AppContainer).
 */
class EmergencyStopController(
    private val repository: EmergencyStopRepository,
    private val logBuffer: LogBuffer,
    private val clock: () -> Long = System::currentTimeMillis,
    private val idGenerator: () -> String = { UUID.randomUUID().toString() },
) {

    val state: StateFlow<EmergencyStopState> = repository.state
    val audit: StateFlow<List<EmergencyStopAuditEvent>> = repository.audit
    val pendingApproval: StateFlow<ResumeApproval?> = repository.pendingApproval

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    /** Convenience flow combining state + pending approval for UI banners. */
    fun bannerSignal(): kotlinx.coroutines.flow.Flow<BannerSignal> =
        combine(state, pendingApproval) { s, a -> BannerSignal(s, a) }

    fun load() {
        scope.launch { repository.load() }
    }

    /**
     * Engage the stop at [target] (defaults to SOFT_PAUSE). If the
     * current level is already higher, this is a no-op — engage never
     * downgrades.
     */
    suspend fun engage(
        source: String,
        reason: String? = null,
        target: EmergencyStopState = EmergencyStopState.SOFT_PAUSE,
    ) {
        require(target.isActive) { "engage() requires an active target" }
        val current = state.value
        if (current.severity >= target.severity) {
            logBuffer.info(TAG, "engage($target) from $source — already at $current, no-op")
            return
        }
        val event = EmergencyStopAuditEvent(
            timestamp = clock(),
            type = if (current == EmergencyStopState.INACTIVE) {
                EmergencyStopAuditEvent.EventType.ENGAGE
            } else {
                EmergencyStopAuditEvent.EventType.ESCALATE
            },
            from = current,
            to = target,
            source = source,
            reason = reason,
        )
        repository.commit(state = target, event = event)
        logBuffer.warn(TAG, "Emergency stop engaged: $current → $target ($source)")
    }

    /**
     * Escalate from the current level to [target]. Required: target
     * severity must be strictly higher than current. Returns false if
     * the request would be a downgrade or no-op.
     */
    suspend fun escalate(
        source: String,
        target: EmergencyStopState,
        reason: String? = null,
    ): Boolean {
        require(target.isActive) { "escalate() requires an active target" }
        val current = state.value
        if (target.severity <= current.severity) return false
        val event = EmergencyStopAuditEvent(
            timestamp = clock(),
            type = EmergencyStopAuditEvent.EventType.ESCALATE,
            from = current,
            to = target,
            source = source,
            reason = reason,
        )
        repository.commit(state = target, event = event)
        logBuffer.warn(TAG, "Emergency stop escalated: $current → $target ($source)")
        return true
    }

    /**
     * Step down from a higher level to a lower (but still active)
     * level. Going all the way back to [EmergencyStopState.INACTIVE]
     * is intentionally not allowed here — that path requires
     * [requestResume] + [approveResume].
     */
    suspend fun deescalate(
        source: String,
        target: EmergencyStopState,
        reason: String? = null,
    ): Boolean {
        require(target.isActive) {
            "deescalate() cannot return to INACTIVE — use requestResume()/approveResume()"
        }
        val current = state.value
        if (target.severity >= current.severity) return false
        val event = EmergencyStopAuditEvent(
            timestamp = clock(),
            type = EmergencyStopAuditEvent.EventType.DEESCALATE,
            from = current,
            to = target,
            source = source,
            reason = reason,
        )
        repository.commit(state = target, event = event)
        logBuffer.info(TAG, "Emergency stop deescalated: $current → $target ($source)")
        return true
    }

    /**
     * Open a resume request. Returns null if the stop is not currently
     * engaged. If a previous approval is still pending it's replaced —
     * only one request is tracked at a time.
     */
    suspend fun requestResume(
        requestedBy: String,
        reason: String? = null,
    ): ResumeApproval? {
        val current = state.value
        if (!current.isActive) return null
        val approval = ResumeApproval(
            id = idGenerator(),
            requestedAt = clock(),
            fromState = current,
            requestedBy = requestedBy,
            reason = reason,
        )
        val event = EmergencyStopAuditEvent(
            timestamp = approval.requestedAt,
            type = EmergencyStopAuditEvent.EventType.RESUME_REQUESTED,
            from = current,
            to = current,
            source = requestedBy,
            reason = reason,
            approval = EmergencyStopAuditEvent.ApprovalSnapshot(
                requestedAt = approval.requestedAt,
                approvedAt = null,
                approver = null,
                approved = false,
            ),
        )
        repository.commit(event = event, pendingApproval = approval)
        return approval
    }

    /**
     * Approve a previously-requested resume and return the state to
     * [EmergencyStopState.INACTIVE]. The [approvalId] must match the
     * currently-pending approval — stale approvals are rejected to
     * prevent replay.
     *
     * Returns true on success.
     */
    suspend fun approveResume(approvalId: String, approver: String): Boolean {
        val pending = pendingApproval.value ?: return false
        if (pending.id != approvalId) return false
        val now = clock()
        val current = state.value
        val event = EmergencyStopAuditEvent(
            timestamp = now,
            type = EmergencyStopAuditEvent.EventType.RESUME_APPROVED,
            from = current,
            to = EmergencyStopState.INACTIVE,
            source = approver,
            reason = pending.reason,
            approval = EmergencyStopAuditEvent.ApprovalSnapshot(
                requestedAt = pending.requestedAt,
                approvedAt = now,
                approver = approver,
                approved = true,
            ),
        )
        val resumeEvent = EmergencyStopAuditEvent(
            timestamp = now,
            type = EmergencyStopAuditEvent.EventType.RESUME,
            from = current,
            to = EmergencyStopState.INACTIVE,
            source = approver,
            reason = pending.reason,
        )
        repository.commit(
            state = EmergencyStopState.INACTIVE,
            event = event,
            clearApproval = true,
        )
        repository.appendAudit(resumeEvent)
        logBuffer.info(TAG, "Resume approved by $approver — $current → INACTIVE")
        return true
    }

    /**
     * Deny a pending resume. Audits the denial and leaves the stop
     * level untouched.
     */
    suspend fun denyResume(approvalId: String, approver: String, reason: String? = null): Boolean {
        val pending = pendingApproval.value ?: return false
        if (pending.id != approvalId) return false
        val now = clock()
        val current = state.value
        val event = EmergencyStopAuditEvent(
            timestamp = now,
            type = EmergencyStopAuditEvent.EventType.RESUME_DENIED,
            from = current,
            to = current,
            source = approver,
            reason = reason ?: pending.reason,
            approval = EmergencyStopAuditEvent.ApprovalSnapshot(
                requestedAt = pending.requestedAt,
                approvedAt = now,
                approver = approver,
                approved = false,
            ),
        )
        repository.commit(event = event, clearApproval = true)
        logBuffer.warn(TAG, "Resume denied by $approver — staying at $current")
        return true
    }

    /**
     * Check whether [action] is currently blocked. Mirrored by
     * [guard] which audits the rejection too.
     */
    fun isBlocked(action: GuardedAction): Boolean {
        val s = state.value
        return when (action) {
            // Pure inspection is never blocked, even in lockdown.
            GuardedAction.READ, GuardedAction.STATUS -> false
            GuardedAction.START_TASK -> s.isActive
            GuardedAction.SEND,
            GuardedAction.DELETE,
            GuardedAction.PUSH,
            GuardedAction.DEPLOY ->
                s.severity >= EmergencyStopState.HARD_STOP.severity
            GuardedAction.MUTATE ->
                s == EmergencyStopState.LOCKDOWN
        }
    }

    /**
     * Convenience for callers that want to refuse and audit at the
     * same time. Returns true if the action is allowed; false if it
     * was blocked (and an audit row was written).
     */
    suspend fun guard(action: GuardedAction, source: String): Boolean {
        if (!isBlocked(action)) return true
        val current = state.value
        val event = EmergencyStopAuditEvent(
            timestamp = clock(),
            type = EmergencyStopAuditEvent.EventType.BLOCKED_ACTION,
            from = current,
            to = current,
            source = source,
            reason = "blocked:${action.name}",
        )
        repository.appendAudit(event)
        logBuffer.warn(TAG, "Blocked $action from $source at level $current")
        return false
    }

    /** JSON snapshot for the export-audit action. Never blocked. */
    fun snapshotJsonForExport(): String = repository.snapshotJson()

    data class BannerSignal(
        val state: EmergencyStopState,
        val pendingApproval: ResumeApproval?,
    )

    companion object {
        const val TAG = "JarvisEmergencyStop"
    }
}
