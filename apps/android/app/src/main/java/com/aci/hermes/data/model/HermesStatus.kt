package com.aci.hermes.data.model

import com.aci.hermes.util.GatewayUrl
import kotlinx.serialization.Serializable

@Serializable
data class HermesStatus(
    val ok: Boolean,
    val version: String? = null,
    val providerId: String? = null,
    val model: String? = null,
    val message: String? = null,
    // Not serialized — populated by the client when ok=false to tell the
    // UI which flavour of failure happened (so we can render "Backend
    // unreachable" vs "Wrong backend URL" instead of one generic banner).
    @kotlinx.serialization.Transient
    val failureKind: GatewayUrl.FailureKind? = null
)

sealed interface ConnectionState {
    data object Unknown : ConnectionState
    data object Connecting : ConnectionState
    data class Connected(val status: HermesStatus) : ConnectionState
    data class Failed(
        val reason: String,
        val kind: GatewayUrl.FailureKind = GatewayUrl.FailureKind.UNKNOWN
    ) : ConnectionState
}
