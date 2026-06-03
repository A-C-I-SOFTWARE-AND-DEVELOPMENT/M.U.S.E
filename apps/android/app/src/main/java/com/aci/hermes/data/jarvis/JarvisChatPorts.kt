package com.aci.hermes.data.jarvis

import com.aci.hermes.data.model.TargetTool

/**
 * Narrow ports the [com.aci.hermes.ui.screens.chat.JarvisChatViewModel]
 * uses to reach the live cockpit (job dispatch, owner approval, evidence/
 * ledger inspection) without depending on a Context, the network stack, or
 * the cockpit data classes directly.
 *
 * Mirrors the existing [JarvisTaskSink] / [JarvisClipboard] pattern: each
 * port has a no-op default so the view model still constructs and unit-
 * tests offline (mock mode), and the container swaps in a cockpit-backed
 * implementation when wiring the real app.
 */

/** Dispatches a chat-derived job to the cockpit job queue. */
interface JarvisJobDispatcher {
    /** True when a real backend is paired and can accept a dispatch. */
    val available: Boolean

    suspend fun dispatch(
        title: String,
        prompt: String,
        targetTool: TargetTool,
    ): JarvisDispatchResult

    companion object {
        /** Offline default: never available, so the VM falls back to the local task sink. */
        val Unavailable: JarvisJobDispatcher = object : JarvisJobDispatcher {
            override val available: Boolean = false
            override suspend fun dispatch(
                title: String,
                prompt: String,
                targetTool: TargetTool,
            ): JarvisDispatchResult = JarvisDispatchResult.Unavailable
        }
    }
}

sealed interface JarvisDispatchResult {
    data class Ok(val jobId: String) : JarvisDispatchResult
    data class Failed(val message: String) : JarvisDispatchResult
    data object Unavailable : JarvisDispatchResult
}

/**
 * Decides an owner-approval card on the live cockpit. The implementation
 * submits the owner phrase only after the on-device confirmation; the
 * gateway still enforces it server-side (this is the ceremony token, not a
 * bypass).
 */
interface JarvisApprovalGateway {
    val available: Boolean

    /** Approve the pending cockpit approval [approvalId]; returns true if accepted. */
    suspend fun approve(approvalId: String): JarvisApprovalResult

    companion object {
        val Unavailable: JarvisApprovalGateway = object : JarvisApprovalGateway {
            override val available: Boolean = false
            override suspend fun approve(approvalId: String): JarvisApprovalResult =
                JarvisApprovalResult.Unavailable
        }
    }
}

sealed interface JarvisApprovalResult {
    data object Accepted : JarvisApprovalResult
    data class Rejected(val message: String) : JarvisApprovalResult
    data object Unavailable : JarvisApprovalResult
}

/** Resolves an evidence/ledger [JarvisRecordRef] into a readable view. */
interface JarvisRecordInspector {
    val available: Boolean

    suspend fun load(ref: JarvisRecordRef): JarvisRecordView?

    companion object {
        val Unavailable: JarvisRecordInspector = object : JarvisRecordInspector {
            override val available: Boolean = false
            override suspend fun load(ref: JarvisRecordRef): JarvisRecordView? = null
        }
    }
}

/** A resolved evidence/ledger record, ready to show in a bottom sheet. */
data class JarvisRecordView(
    val title: String,
    val subtitle: String? = null,
    val lines: List<String> = emptyList(),
)

// ─── Test doubles (kept beside the ports, matching FakeJarvisTaskSink) ────

/** Records dispatches; configurable availability + result. */
class FakeJarvisJobDispatcher(
    override var available: Boolean = true,
    var result: JarvisDispatchResult = JarvisDispatchResult.Ok("job_fake"),
) : JarvisJobDispatcher {
    data class Call(val title: String, val prompt: String, val targetTool: TargetTool)

    val calls: MutableList<Call> = mutableListOf()

    override suspend fun dispatch(
        title: String,
        prompt: String,
        targetTool: TargetTool,
    ): JarvisDispatchResult {
        calls += Call(title, prompt, targetTool)
        return if (available) result else JarvisDispatchResult.Unavailable
    }
}

/** Records approvals; configurable availability + result. */
class FakeJarvisApprovalGateway(
    override var available: Boolean = true,
    var result: JarvisApprovalResult = JarvisApprovalResult.Accepted,
) : JarvisApprovalGateway {
    val approvedIds: MutableList<String> = mutableListOf()

    override suspend fun approve(approvalId: String): JarvisApprovalResult {
        approvedIds += approvalId
        return if (available) result else JarvisApprovalResult.Unavailable
    }
}

/** Returns a canned view for any ref; records lookups. */
class FakeJarvisRecordInspector(
    override var available: Boolean = true,
    var view: JarvisRecordView? = JarvisRecordView("Record", lines = listOf("line")),
) : JarvisRecordInspector {
    val loaded: MutableList<JarvisRecordRef> = mutableListOf()

    override suspend fun load(ref: JarvisRecordRef): JarvisRecordView? {
        loaded += ref
        return if (available) view else null
    }
}
