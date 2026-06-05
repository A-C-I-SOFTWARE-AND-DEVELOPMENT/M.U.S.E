package com.aci.hermes.ui.screens.pairing

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.DevicePairingClient
import com.aci.hermes.data.cockpit.PairingConfirm
import com.aci.hermes.data.cockpit.PairingStart
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * The pairing handshake as a small state machine:
 *
 * - [Idle] — nothing requested yet.
 * - [CodeRequested] — `pair/start` returned a code to read/enter (carries the
 *   live [PairingStart] so the UI can show the code + its TTL).
 * - [Paired] — `pair/confirm` succeeded and the per-device token was persisted;
 *   carries the [PairingConfirm] (device id + token type, never logged).
 * - [Error] — the gateway refused or was unreachable; [message] is a single
 *   human line and [retryable] notes whether re-requesting a code is sensible.
 */
sealed interface DevicePairingState {
    data object Idle : DevicePairingState
    data class CodeRequested(val start: PairingStart) : DevicePairingState
    data class Paired(val confirm: PairingConfirm) : DevicePairingState
    data class Error(val message: String, val retryable: Boolean = true) : DevicePairingState
}

/**
 * Drives device pairing: request a short-lived code, then exchange it (with
 * the exact owner authorization phrase) for the per-device token, which the
 * [DevicePairingClient] persists on success. The logic path is framework-free
 * and runs on the JVM — every branch is exercised by the unit tests against a
 * fake client.
 */
class DevicePairingViewModel(
    private val client: DevicePairingClient,
) : ViewModel() {

    private val _state = MutableStateFlow<DevicePairingState>(DevicePairingState.Idle)
    val state: StateFlow<DevicePairingState> = _state.asStateFlow()

    /** Request a pairing code; moves to [DevicePairingState.CodeRequested] on success. */
    fun startPairing(deviceName: String? = null) {
        viewModelScope.launch {
            _state.value = when (val res = client.startPairing(deviceName)) {
                is CockpitResult.Success -> DevicePairingState.CodeRequested(res.value)
                is CockpitResult.Failure -> DevicePairingState.Error(failureMessage(res))
                is CockpitResult.Unreachable -> DevicePairingState.Error(res.message)
            }
        }
    }

    /**
     * Confirm the [code] with the owner [authorization] phrase. On success the
     * token is already persisted by the client and we move to
     * [DevicePairingState.Paired]; a `403` surfaces as a non-retryable
     * authorization error (the phrase, not the code, was wrong).
     */
    fun confirmPairing(
        code: String,
        authorization: String = DevicePairingClient.OWNER_AUTHORIZATION_PHRASE,
    ) {
        viewModelScope.launch {
            _state.value = when (val res = client.confirmPairing(code, authorization)) {
                is CockpitResult.Success -> DevicePairingState.Paired(res.value)
                is CockpitResult.Failure -> DevicePairingState.Error(
                    failureMessage(res),
                    retryable = res.httpStatus != 403,
                )
                is CockpitResult.Unreachable -> DevicePairingState.Error(res.message)
            }
        }
    }

    /** Drop back to [DevicePairingState.Idle] (e.g. to restart the flow). */
    fun reset() {
        _state.value = DevicePairingState.Idle
    }

    private fun failureMessage(res: CockpitResult.Failure): String = when (res.httpStatus) {
        403 -> "Owner authorization required — reply exactly \"" +
            DevicePairingClient.OWNER_AUTHORIZATION_PHRASE + "\"."
        401 -> "Pairing code is invalid or expired — request a new one."
        429 -> "Pairing temporarily unavailable — wait a moment and try again."
        else -> "Gateway error ${res.httpStatus}: ${res.error.message}"
    }
}
