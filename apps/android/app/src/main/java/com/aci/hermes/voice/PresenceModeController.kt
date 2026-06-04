package com.aci.hermes.voice

import android.content.Context
import android.speech.SpeechRecognizer
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.service.JarvisOverlayService
import com.aci.hermes.service.VoiceLoopService
import com.aci.hermes.ui.screens.live.JarvisLiveState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/**
 * The thin Android glue that runs hands-free **Presence Mode**. The
 * decisions live in the pure [PresenceModePolicy]; this controller only
 * enacts them:
 *
 *  - persists / exposes the on-off toggle (default off — owner opts in),
 *  - starts/stops [VoiceLoopService] (which arms the wake word when one is
 *    wired, e.g. [KeywordSpeechWakeWordEngine]),
 *  - offers tap-to-talk / mic-button fallback ([talkNow]) that bypasses the
 *    wake word,
 *  - mirrors the live voice phase onto the floating [JarvisOverlayService]
 *    so the avatar reacts to listening/thinking/speaking even when the app
 *    UI is in the background.
 *
 * No camera is involved *here* — this controller only mirrors the voice
 * phase onto the overlay. Camera-based attention is a separate, opt-in
 * capability: CAMERA is declared in the manifest and used only by the
 * foreground Live screen's on-device attention detector (default off,
 * presence-only, no frame storage). See CameraXFaceAttentionDetector.
 */
class PresenceModeController(
    private val appContext: Context,
    private val settings: SettingsRepository,
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate),
) {

    /** True if a keyword spotter can run on this device (mic recognition). */
    val wakeWordAvailable: Boolean
        get() = SpeechRecognizer.isRecognitionAvailable(appContext)

    /** The trigger Presence Mode will use, given current capabilities. */
    val trigger: PresenceTrigger
        get() = PresenceModePolicy.trigger(wakeWordAvailable = wakeWordAvailable)

    /** Current on-off state of Presence Mode. */
    val enabled: StateFlow<Boolean> =
        settings.presenceModeEnabled.stateIn(scope, SharingStarted.Eagerly, false)

    /** What the presence surface should show right now. */
    val presenceState: StateFlow<PresenceState> =
        combine(settings.presenceModeEnabled, VoiceLoopService.phaseFlow) { on, phase ->
            PresenceModePolicy.stateFor(on, phase)
        }.stateIn(scope, SharingStarted.Eagerly, PresenceState.OFF)

    /** Opt-in camera attention toggle (default off; arms listening on a glance). */
    val cameraAttentionEnabled: StateFlow<Boolean> =
        settings.cameraAttentionEnabled.stateIn(scope, SharingStarted.Eagerly, false)

    init {
        // Mirror the live voice phase onto the floating avatar so it reacts
        // even when the cockpit UI isn't foreground. Only the active voice
        // states are pushed, so this never fights the screen's own updates.
        VoiceLoopService.phaseFlow
            .onEach { phase -> overlayStateFor(phase)?.let { JarvisOverlayService.active?.setLiveState(it) } }
            .launchIn(scope)
    }

    /** Turn Presence Mode on/off; starts or stops the hands-free loop. */
    fun setEnabled(on: Boolean) {
        scope.launch { settings.setPresenceModeEnabled(on) }
        if (on) VoiceLoopService.start(appContext) else VoiceLoopService.stop(appContext)
    }

    fun toggle() = setEnabled(!enabled.value)

    /**
     * Tap-to-talk / mic fallback: start (if needed) and open the mic now,
     * bypassing the wake word. Caller must hold RECORD_AUDIO.
     */
    fun talkNow() = VoiceLoopService.talkNow(appContext)

    /** Opt in/out of camera attention. The camera only runs when this is on
     *  AND Presence Mode is on AND the CAMERA permission is granted. */
    fun setCameraAttention(on: Boolean) {
        scope.launch { settings.setCameraAttentionEnabled(on) }
    }

    fun toggleCameraAttention() = setCameraAttention(!cameraAttentionEnabled.value)

    private fun overlayStateFor(phase: VoicePhase): JarvisLiveState? = when (phase) {
        VoicePhase.LISTENING -> JarvisLiveState.Listening
        VoicePhase.THINKING -> JarvisLiveState.Thinking
        VoicePhase.SPEAKING -> JarvisLiveState.Speaking
        VoicePhase.DORMANT, VoicePhase.WAITING_FOR_WAKE -> null
    }
}
