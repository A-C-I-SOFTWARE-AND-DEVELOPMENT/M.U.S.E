package com.aci.hermes.data.model

import kotlinx.serialization.Serializable

@Serializable
data class HermesStatus(
    val ok: Boolean,
    val version: String? = null,
    val providerId: String? = null,
    val model: String? = null,
    val message: String? = null
)

sealed interface ConnectionState {
    data object Unknown : ConnectionState
    data object Connecting : ConnectionState
    data class Connected(val status: HermesStatus) : ConnectionState
    data class Failed(val reason: String) : ConnectionState
}
