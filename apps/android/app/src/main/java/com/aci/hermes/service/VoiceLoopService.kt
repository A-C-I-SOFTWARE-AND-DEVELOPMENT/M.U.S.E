package com.aci.hermes.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.os.Build
import androidx.lifecycle.LifecycleService
import androidx.lifecycle.lifecycleScope
import com.aci.hermes.data.automation.AutomationIntentParser
import com.aci.hermes.voice.SttEngine
import com.aci.hermes.voice.TtsEngine
import com.aci.hermes.voice.TtsEvent
import com.aci.hermes.voice.VoiceEvent
import com.aci.hermes.voice.VoiceLoop
import com.aci.hermes.voice.VoicePhase
import com.aci.hermes.voice.WakeWordEngine
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.firstOrNull
import kotlinx.coroutines.launch

/**
 * The hands-free voice driver. A thin, Android-aware shell around the
 * pure [VoiceLoop] state machine: it routes headset audio over Bluetooth
 * SCO, runs the wake-word → STT → agent → TTS cycle, and honors
 * barge-in. Every transcript flows through the SAME pipeline the chat
 * surface uses, so any feature reachable by text is reachable by voice —
 * including the device-driving commands ([AutomationIntentParser] →
 * [JarvisOverlayService.execute]).
 *
 * The loop's *decisions* live in [VoiceLoop] (and are unit-tested); this
 * class only enacts the resulting effects.
 */
class VoiceLoopService : LifecycleService() {

    private val loop = VoiceLoop(conversational = true)

    private lateinit var audioManager: AudioManager
    private var wakeWord: WakeWordEngine? = null
    private var stt: SttEngine? = null
    private var tts: TtsEngine? = null

    /** Sends an utterance to the agent; supplied by [Wiring]. */
    private var dispatch: (suspend (String) -> String)? = null

    override fun onCreate() {
        super.onCreate()
        audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        wakeWord = Wiring.wakeWordFactory?.invoke(this)
        stt = Wiring.sttFactory?.invoke(this)
        tts = Wiring.ttsFactory?.invoke(this)
        dispatch = Wiring.dispatch
        startInForeground()
        routeToHeadset()
        active = this
        drive(VoiceEvent.Start)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)
        // Tap-to-talk / mic fallback: skip the wake word and open the mic now.
        if (intent?.getBooleanExtra(EXTRA_TALK_NOW, false) == true) {
            drive(VoiceEvent.WakeWordDetected)
        }
        return START_STICKY
    }

    override fun onDestroy() {
        tts?.stop()
        stopHeadsetRoute()
        if (active === this) active = null
        _phaseFlow.value = VoicePhase.DORMANT
        super.onDestroy()
    }

    /** Feed an event into the loop and enact the resulting effect. */
    fun drive(event: VoiceEvent) {
        val transition = loop.on(event)
        // Publish the voice phase so presence surfaces (the live avatar, the
        // floating overlay) can reflect listening / thinking / speaking.
        _phaseFlow.value = transition.phase
        when (transition.effect) {
            VoiceLoop.Effect.START_WAKE_LISTENER -> listenForWake()
            VoiceLoop.Effect.OPEN_MIC_FOR_STT -> captureUtterance()
            VoiceLoop.Effect.DISPATCH_TO_AGENT -> dispatchUtterance(loop.lastUtterance)
            VoiceLoop.Effect.SPEAK_REPLY -> speak(loop.lastReply)
            VoiceLoop.Effect.STOP_ALL_AUDIO -> { tts?.stop(); stopSelf() }
            VoiceLoop.Effect.NONE -> Unit
        }
    }

    private fun listenForWake() {
        val engine = wakeWord ?: return
        lifecycleScope.launch {
            engine.detections().first()
            drive(VoiceEvent.WakeWordDetected)
        }
    }

    private fun captureUtterance() {
        val engine = stt ?: return
        lifecycleScope.launch {
            val finalResult = engine.transcribe().firstOrNull { it.isFinal }
            val text = finalResult?.text?.trim().orEmpty()
            if (text.isEmpty()) drive(VoiceEvent.UtteranceEmpty)
            else drive(VoiceEvent.UtteranceFinal(text))
        }
    }

    private fun dispatchUtterance(text: String) {
        lifecycleScope.launch {
            // Device-driving commands are performed by the body, not spoken back.
            val automation = AutomationIntentParser.parse(text)
            if (automation != null) {
                JarvisOverlayService.active?.let { overlay ->
                    // Resolve + choreograph happens in the overlay wiring layer.
                    Wiring.performAutomation?.invoke(overlay, automation)
                }
                drive(VoiceEvent.ReplyReady("Done."))
                return@launch
            }
            // Think out loud: dispatch to the agent AND drop a brief thinking-beat
            // so the THINKING phase sounds like Jarvis is considering, not frozen.
            // The real reply (QUEUE_FLUSH) replaces the beat the moment it's ready.
            val replyDeferred = async {
                runCatching { dispatch?.invoke(text) }.getOrNull() ?: "I couldn't reach the agent."
            }
            tts?.let { engine ->
                launch {
                    engine.speak(THINKING_BEATS.random())
                        .firstOrNull { it == TtsEvent.DONE || it == TtsEvent.ERROR }
                }
            }
            drive(VoiceEvent.ReplyReady(replyDeferred.await()))
        }
    }

    private fun speak(text: String) {
        val engine = tts ?: return drive(VoiceEvent.SpeechDone)
        lifecycleScope.launch {
            engine.speak(text).firstOrNull { it == TtsEvent.DONE || it == TtsEvent.ERROR }
            drive(VoiceEvent.SpeechDone)
        }
    }

    private fun routeToHeadset() {
        runCatching {
            if (audioManager.isBluetoothScoAvailableOffCall) {
                audioManager.startBluetoothSco()
                audioManager.isBluetoothScoOn = true
            }
        }
    }

    private fun stopHeadsetRoute() {
        runCatching {
            audioManager.isBluetoothScoOn = false
            audioManager.stopBluetoothSco()
        }
    }

    private fun startInForeground() {
        val channelId = "jarvis_voice"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getSystemService(NotificationManager::class.java).createNotificationChannel(
                NotificationChannel(channelId, "Jarvis voice", NotificationManager.IMPORTANCE_LOW),
            )
        }
        val notification: Notification = Notification.Builder(this, channelId)
            .setContentTitle("Jarvis is listening")
            .setContentText("Say \"Hey Jarvis\"")
            .setSmallIcon(com.aci.hermes.R.mipmap.ic_launcher)
            .build()
        // The MICROPHONE foreground-service type is API 30+, and the typed
        // 3-arg startForeground is API 29+. Guard directly on SDK_INT so
        // lint's flow analysis is satisfied; below 30 use the 2-arg form.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            startForeground(
                VOICE_NOTIFICATION_ID,
                notification,
                android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE,
            )
        } else {
            @Suppress("DEPRECATION")
            startForeground(VOICE_NOTIFICATION_ID, notification)
        }
    }

    /**
     * Process-level wiring set by [com.aci.hermes.di.AppContainer]. Kept
     * as factories so the service stays free of construction details and
     * the engines can be swapped (on-device ↔ cloud) without touching it.
     */
    object Wiring {
        var wakeWordFactory: ((Context) -> WakeWordEngine)? = null
        var sttFactory: ((Context) -> SttEngine)? = null
        var ttsFactory: ((Context) -> TtsEngine)? = null
        var dispatch: (suspend (String) -> String)? = null
        var performAutomation: ((JarvisOverlayService, com.aci.hermes.data.automation.AutomationIntent) -> Unit)? = null
    }

    companion object {
        @Volatile
        var active: VoiceLoopService? = null
            private set

        private val _phaseFlow = MutableStateFlow(VoicePhase.DORMANT)

        /**
         * Process-wide stream of the current voice-loop phase. Presence
         * surfaces observe this to show listening / thinking / speaking; it is
         * DORMANT whenever the service is not running.
         */
        val phaseFlow: StateFlow<VoicePhase> = _phaseFlow.asStateFlow()

        // Brief, warm fillers spoken during THINKING so the pause feels like a
        // person considering, not dead air. Kept short — the real reply flushes.
        private val THINKING_BEATS = listOf("Hmm.", "One sec.", "Let me think.", "Right —")

        const val VOICE_NOTIFICATION_ID = 4243

        /** Intent extra: open the mic immediately instead of waiting for wake. */
        const val EXTRA_TALK_NOW = "talk_now"

        fun start(context: Context) = launch(context, talkNow = false)

        /**
         * Start (if needed) and immediately begin listening — the tap-to-talk /
         * mic-button fallback that bypasses the wake word.
         */
        fun talkNow(context: Context) = launch(context, talkNow = true)

        private fun launch(context: Context, talkNow: Boolean) {
            val intent = Intent(context, VoiceLoopService::class.java)
            if (talkNow) intent.putExtra(EXTRA_TALK_NOW, true)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) context.startForegroundService(intent)
            else context.startService(intent)
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, VoiceLoopService::class.java))
        }
    }
}
