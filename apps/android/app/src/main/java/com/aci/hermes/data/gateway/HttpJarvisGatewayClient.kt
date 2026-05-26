package com.aci.hermes.data.gateway

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Placeholder for the real network transport that will eventually
 * attach to a Jarvis Prime gateway over WebSocket / SSE.
 *
 * Its purpose today is alignment: it implements [GatewayClient] so the
 * UI, reducer, and tests cannot accidentally depend on
 * [MockGatewayClient]-only behaviour. When [GatewayMode.REAL] is
 * selected from settings, [com.aci.hermes.di.AppContainer] hands this
 * client out; it immediately reports
 * [GatewayConnectionState.Failed] so the UI surfaces the "real
 * transport not implemented" banner instead of silently doing
 * nothing.
 *
 * Implementation notes for whoever wires the real transport:
 *
 *  - Do **not** add bearer tokens, refresh tokens, OAuth secrets, or
 *    provider API keys to any [GatewayEvent] field. Authentication
 *    headers go on the underlying HTTP request, never inside an event
 *    payload, and never inside [LogBuffer][com.aci.hermes.util.LogBuffer]
 *    output.
 *  - Drive [events] from the deserialized stream using [GatewayJson].
 *    Unknown event types should be logged at WARN with the type name
 *    only — never log the raw body, since some future event may
 *    carry user content that should stay off Logcat.
 *  - Outbound calls (`sendUserMessage`, `requestApproval`,
 *    `confirmSerious`, `confirmCritical`, `triggerEmergencyStop`) must
 *    emit the corresponding event on [events] *before* returning, to
 *    match the mock client's behaviour and keep the reducer's
 *    invariants honest.
 *  - Honour the type-system invariant on critical actions: there is
 *    no way to call [confirmCritical] without an [ImpactReport]. Do
 *    not add a back-door overload.
 */
class HttpJarvisGatewayClient(
    private val baseUrl: String,
) : GatewayClient {

    private val _events = MutableSharedFlow<GatewayEvent>(replay = 0, extraBufferCapacity = 64)
    override val events: Flow<GatewayEvent> = _events.asSharedFlow()

    private val _connectionState = MutableStateFlow<GatewayConnectionState>(
        GatewayConnectionState.Idle,
    )
    override val connectionState: StateFlow<GatewayConnectionState> =
        _connectionState.asStateFlow()

    override suspend fun connect() {
        _connectionState.value = GatewayConnectionState.Connecting(GatewayMode.REAL)
        // Until a transport is wired up, never claim Connected.
        _connectionState.value = GatewayConnectionState.Failed(
            reason = "real_transport_not_implemented",
        )
    }

    override suspend fun disconnect() {
        _connectionState.value = GatewayConnectionState.Disconnected("user_disconnect")
    }

    override suspend fun sendUserMessage(text: String, correlationId: String?): UserMessageEvent =
        notImplemented("sendUserMessage")

    override suspend fun requestApproval(
        actionId: String,
        summary: String,
        riskClass: ApprovalRiskClass,
    ): ApprovalRequestedEvent = notImplemented("requestApproval")

    override suspend fun grantApproval(approvalId: String, note: String?): ApprovalGrantedEvent =
        notImplemented("grantApproval")

    override suspend fun rejectApproval(approvalId: String, reason: String?): ApprovalRejectedEvent =
        notImplemented("rejectApproval")

    override suspend fun confirmSerious(
        approvalId: String,
        confirmationToken: String,
    ): ApprovalGrantedEvent = notImplemented("confirmSerious")

    override suspend fun confirmCritical(
        approvalId: String,
        impactReport: ImpactReport,
    ): ApprovalGrantedEvent = notImplemented("confirmCritical")

    override suspend fun triggerEmergencyStop(reason: String): EmergencyStopTriggeredEvent =
        notImplemented("triggerEmergencyStop")

    @Suppress("UNUSED_PARAMETER")
    private fun notImplemented(method: String): Nothing =
        throw UnsupportedOperationException(
            "HttpJarvisGatewayClient.$method is not implemented yet; " +
                "switch the app to MOCK gateway mode or wire the real transport. " +
                "baseUrl=$baseUrl",
        )
}
