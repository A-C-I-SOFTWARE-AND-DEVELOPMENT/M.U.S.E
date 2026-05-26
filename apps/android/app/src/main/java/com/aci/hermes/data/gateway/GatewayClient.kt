package com.aci.hermes.data.gateway

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow

/**
 * Boundary between the Android app and a Jarvis Prime gateway.
 *
 * Implementations are responsible for transporting [GatewayEvent]s in
 * both directions — typically over a WebSocket or SSE channel — and for
 * surfacing connection state. The interface is intentionally narrow so
 * that mock and real transports stay swappable from
 * [com.aci.hermes.di.AppContainer].
 *
 * Invariants every implementation must uphold:
 *
 * 1. **App emits approvals, not destructive actions.** The mutators
 *    here all produce events on the spine. Implementations never
 *    perform a destructive side effect locally — the gateway side is
 *    where execution happens.
 * 2. **Serious actions require two separate confirmations.** A single
 *    [confirmSerious] call must not be enough to satisfy a
 *    [SeriousConfirmationRequiredEvent]; the caller has to invoke it
 *    twice with two distinct confirmation tokens.
 * 3. **Critical actions require an [ImpactReport].** The type system
 *    enforces this — [confirmCritical] takes the report as a required
 *    parameter, so a screen cannot "just confirm" a
 *    [CriticalConfirmationRequiredEvent] without first reading and
 *    forwarding the impact report.
 * 4. **Emergency stop overrides everything in flight.**
 *    [triggerEmergencyStop] must cause an
 *    [EmergencyStopTriggeredEvent] to be observable on [events] before
 *    the function returns.
 * 5. **No secrets in events.** Implementations must not place gateway
 *    tokens, provider API keys, or session cookies in any event field.
 *    Validate via [GatewayEvent] type system: there is nowhere to put
 *    them.
 */
interface GatewayClient {

    /**
     * Hot stream of every event that has crossed the spine in either
     * direction since [connect] succeeded. Outbound events (the ones
     * this client produces from `send*`/`confirm*` calls) appear here
     * before the suspending call returns, so a UI subscriber sees the
     * intent before it sees the response.
     */
    val events: Flow<GatewayEvent>

    /** Live connection state. Drives status indicators and the icon. */
    val connectionState: StateFlow<GatewayConnectionState>

    /**
     * Attach to the gateway. Emits a [GatewayConnectedEvent] on success
     * and moves [connectionState] to
     * [GatewayConnectionState.Connected]. Calling twice is safe — the
     * second call is a no-op if already connected.
     */
    suspend fun connect()

    /**
     * Detach from the gateway. Emits a [GatewayDisconnectedEvent] and
     * moves [connectionState] to [GatewayConnectionState.Disconnected].
     */
    suspend fun disconnect()

    // ── Conversation ─────────────────────────────────────────────────

    /** Send a user utterance onto the spine. */
    suspend fun sendUserMessage(text: String, correlationId: String? = null): UserMessageEvent

    // ── Approvals ────────────────────────────────────────────────────

    /**
     * Ask the gateway to perform a side-effecting action on the user's
     * behalf. The action is identified by [actionId] and described in
     * [summary]. The risk class controls how many confirmations the
     * gateway will require before executing.
     *
     * Returns the [ApprovalRequestedEvent] emitted on the spine so the
     * caller has the approval id without scraping [events].
     */
    suspend fun requestApproval(
        actionId: String,
        summary: String,
        riskClass: ApprovalRiskClass,
    ): ApprovalRequestedEvent

    /**
     * Grant a standard approval. Emits [ApprovalGrantedEvent] with
     * `confirmation_index = 1`.
     */
    suspend fun grantApproval(approvalId: String, note: String? = null): ApprovalGrantedEvent

    /** Reject any pending approval. Emits [ApprovalRejectedEvent]. */
    suspend fun rejectApproval(approvalId: String, reason: String? = null): ApprovalRejectedEvent

    /**
     * Provide *one* of the two confirmations required for a
     * [SeriousConfirmationRequiredEvent]. Each call must use a
     * different [confirmationToken] — repeating the same token raises
     * [IllegalStateException].
     *
     * The gateway is the one that counts confirmations and executes;
     * the app only emits them.
     */
    suspend fun confirmSerious(
        approvalId: String,
        confirmationToken: String,
    ): ApprovalGrantedEvent

    /**
     * Provide the confirmation for a
     * [CriticalConfirmationRequiredEvent]. The [impactReport] is
     * required by the type system — there is no overload that omits
     * it. Implementations must reject any attempt to forge an empty
     * report (e.g. blank summary) with [IllegalArgumentException].
     */
    suspend fun confirmCritical(
        approvalId: String,
        impactReport: ImpactReport,
    ): ApprovalGrantedEvent

    // ── Emergency stop ───────────────────────────────────────────────

    /**
     * Halt all in-flight work on the gateway side. Implementations
     * must emit an [EmergencyStopTriggeredEvent] synchronously (before
     * this call returns) so downstream reducers can clear pending
     * approvals and workers.
     */
    suspend fun triggerEmergencyStop(reason: String): EmergencyStopTriggeredEvent
}
