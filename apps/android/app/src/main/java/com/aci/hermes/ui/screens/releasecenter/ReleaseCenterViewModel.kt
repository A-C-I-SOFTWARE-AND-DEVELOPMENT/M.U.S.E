package com.aci.hermes.ui.screens.releasecenter

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.cockpit.ServerCapabilities
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * Release / Download Center — the honest, single place for "how do I get and
 * trust this build". It mixes **on-device facts** (this APK's version + build
 * type) with the **documented** download/signing model and an optional
 * **backend** capability read. It never fabricates CI/PR/release state: live CI
 * needs a configured GitHub token (not wired), so the screen says so rather
 * than inventing a status.
 */
class ReleaseCenterViewModel(
    private val client: HermesCockpitClient,
    /** This APK's build facts (from BuildConfig), passed in so the VM is JVM-testable. */
    val appVersion: String,
    val buildType: String,
    val applicationId: String,
) : ViewModel() {

    data class UiState(
        val loading: Boolean = true,
        val capabilities: ServerCapabilities? = null,
        /** Honest hint when the backend is unreachable/unpaired (no data). */
        val backendUnavailable: String? = null,
    )

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()

    /** Stable, documented rolling-download URL (see RELEASE_DOWNLOAD.md). */
    val downloadUrl: String =
        "https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/releases/download/" +
            "android-latest/jarvis-prime-android.apk"

    /** The four CI secret *names* (never values) that switch on release signing. */
    val signingSecretNames: List<String> = listOf(
        "ANDROID_KEYSTORE_BASE64",
        "ANDROID_KEYSTORE_PASSWORD",
        "ANDROID_KEY_ALIAS",
        "ANDROID_KEY_PASSWORD",
    )

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true) }
            when (val r = client.capabilities()) {
                is CockpitResult.Success ->
                    _state.update { it.copy(loading = false, capabilities = r.value, backendUnavailable = null) }
                is CockpitResult.Unreachable ->
                    _state.update { it.copy(loading = false, capabilities = null, backendUnavailable = r.message) }
                is CockpitResult.Failure ->
                    _state.update { it.copy(loading = false, capabilities = null, backendUnavailable = r.error.message) }
            }
        }
    }
}
