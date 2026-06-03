package com.aci.hermes.ui.screens.live

import android.app.Application
import android.graphics.BitmapFactory
import android.provider.Settings
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.avatar.AvatarRepository
import com.aci.hermes.data.avatar.AvatarSource
import com.aci.hermes.data.jarvis.JarvisChatChunk
import com.aci.hermes.data.jarvis.JarvisChatGateway
import com.aci.hermes.data.life.BehaviorScheduler
import com.aci.hermes.service.VoiceLoopService
import java.util.Calendar
import kotlin.time.Duration
import kotlin.time.Duration.Companion.milliseconds
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class JarvisLiveViewModel(
    application: Application,
    private val avatarRepository: AvatarRepository? = null,
    private val cockpitClient: com.aci.hermes.data.cockpit.HermesCockpitClient? = null,
    private val gateway: JarvisChatGateway? = null,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(
        JarvisLiveUiState(reducedMotion = systemReducedMotion()),
    )
    val state: StateFlow<JarvisLiveUiState> = _state.asStateFlow()

    /** A piece of AI-generated furniture placed in the Den. */
    data class DenFurniture(
        val id: String,
        val bitmap: android.graphics.Bitmap,
        val x: Float,
        val y: Float,
    )

    private val _furniture = MutableStateFlow<List<DenFurniture>>(emptyList())
    val furniture: StateFlow<List<DenFurniture>> = _furniture.asStateFlow()

    private fun loadFurniture() {
        val client = cockpitClient ?: return
        viewModelScope.launch {
            val res = client.roomList()
            if (res is com.aci.hermes.data.cockpit.CockpitResult.Success) {
                _furniture.value = res.value.items.mapNotNull { item ->
                    val bmp = decodeRoomImage(item.imageB64) ?: return@mapNotNull null
                    DenFurniture(item.id, bmp, item.x, item.y)
                }
            }
        }
    }

    /** Persist a furniture item's new placement after a drag. */
    fun placeFurniture(id: String, x: Float, y: Float) {
        val client = cockpitClient ?: return
        viewModelScope.launch { client.roomPlace(id, x, y) }
    }

    private fun decodeRoomImage(b64: String?): android.graphics.Bitmap? {
        if (b64.isNullOrBlank()) return null
        return runCatching {
            val bytes = android.util.Base64.decode(b64, android.util.Base64.DEFAULT)
            android.graphics.BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
        }.getOrNull()
    }

    // Ambient life: when the user is away, Jarvis idles → wanders → sleeps so the
    // body reads as alive rather than frozen. Driven by the pure, tested
    // BehaviorScheduler; suppressed while the agent is busy or motion is reduced.
    private val ambientScheduler = BehaviorScheduler()

    @Volatile
    private var lastInteractionAtMs = System.currentTimeMillis()

    init {
        startAmbientLife()
        observeSavedAvatar()
        observeVoiceState()
        loadFurniture()
    }

    /**
     * Mirror the REAL hands-free voice phase onto the avatar. This is the
     * source of truth for listening/thinking/speaking — the avatar animates
     * from genuine [VoiceLoopService] state, never a faked flag. Suppressed
     * while an emergency stop is latched.
     */
    private fun observeVoiceState() {
        viewModelScope.launch {
            combine(VoiceLoopService.phase, VoiceLoopService.transcript) { phase, transcript ->
                phase to transcript
            }.collect { (phase, transcript) ->
                if (_state.value.emergencyStop) return@collect
                markInteraction()
                _state.update { it.withVoicePhase(phase, transcript) }
            }
        }
    }

    /** Render the user's saved avatar as the living body: a GENERATED photo
     *  becomes a breathing photo face; otherwise the procedural humanoid. */
    private fun observeSavedAvatar() {
        val repo = avatarRepository ?: return
        viewModelScope.launch {
            combine(repo.profileFlow, repo.spriteIdFlow) { profile, spriteId ->
                profile to spriteId
            }.collect { (profile, spriteId) ->
                val photo = if (
                    profile?.source == AvatarSource.GENERATED && profile.generatedPath != null
                ) {
                    withContext(Dispatchers.IO) {
                        runCatching { BitmapFactory.decodeFile(profile.generatedPath) }.getOrNull()
                    }
                } else {
                    null
                }
                _state.update {
                    if (photo != null) {
                        it.copy(avatarKind = AvatarKind.Photo, avatarPhoto = photo)
                    } else {
                        it.copy(
                            avatarKind = AvatarKind.Character3D,
                            avatarPhoto = null,
                            spriteId = spriteId ?: it.spriteId,
                        )
                    }
                }
            }
        }
    }

    private fun markInteraction() {
        lastInteractionAtMs = System.currentTimeMillis()
    }

    private fun startAmbientLife() {
        viewModelScope.launch {
            while (isActive) {
                val s = _state.value
                val idleFor = (System.currentTimeMillis() - lastInteractionAtMs)
                    .coerceAtLeast(0L).milliseconds
                val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
                val behavior = ambientScheduler.decide(
                    BehaviorScheduler.Tick(
                        idleFor = idleFor,
                        localHour = hour,
                        hasPendingRecommendation = false,
                        sinceLastRecommendation = Duration.ZERO,
                        agentBusy = s.thinking || s.working || s.speaking,
                        ambientMuted = s.reducedMotion || s.emergencyStop,
                    ),
                )
                if (behavior != s.avatarBehavior) {
                    _state.update { it.copy(avatarBehavior = behavior) }
                }
                delay(AMBIENT_TICK_MS)
            }
        }
    }

    private val _showStatusSheet = MutableStateFlow(false)
    val showStatusSheet: StateFlow<Boolean> = _showStatusSheet.asStateFlow()

    private val _showEmergencyConfirm = MutableStateFlow(false)
    val showEmergencyConfirm: StateFlow<Boolean> = _showEmergencyConfirm.asStateFlow()

    fun refreshReducedMotion() {
        val current = systemReducedMotion()
        _state.update { it.copy(reducedMotion = current) }
    }

    fun onCommandChange(text: String) {
        markInteraction()
        _state.update { it.copy(command = text) }
    }

    fun onSend() {
        markInteraction()
        val current = _state.value
        val prompt = current.command.trim()
        if (prompt.isBlank() || current.emergencyStop) return
        val gw = gateway
        if (gw == null) {
            // No real backend wired (preview / test) — just clear the box
            // rather than getting stuck on a fake "thinking" state.
            _state.update { it.copy(command = "") }
            return
        }
        _state.update { it.copy(command = "", thinking = true, listening = false) }
        viewModelScope.launch {
            gw.send(emptyList(), prompt).collect { chunk ->
                if (_state.value.emergencyStop) return@collect
                _state.update { s ->
                    when (chunk) {
                        is JarvisChatChunk.Thinking ->
                            s.copy(thinking = true, working = false, speaking = false)
                        is JarvisChatChunk.Working ->
                            s.copy(thinking = false, working = true)
                        is JarvisChatChunk.Body ->
                            s.copy(thinking = false, working = false, speaking = true, voiceLine = chunk.text)
                        is JarvisChatChunk.Detail ->
                            // The cockpit surfaces owner-gated actions as a detail
                            // chunk; reflect that as a real "approval needed" state
                            // rather than letting voice/typed input proceed silently.
                            if (chunk.text.contains("approval required", ignoreCase = true)) {
                                s.copy(approvalNeeded = true)
                            } else {
                                s
                            }
                        is JarvisChatChunk.Done ->
                            s.copy(thinking = false, working = false, speaking = false)
                        is JarvisChatChunk.Failure ->
                            s.copy(thinking = false, working = false, speaking = false, blocked = true)
                        else -> s
                    }
                }
            }
        }
    }

    /** Cycle to the next pixel-sprite character (robot → person → pets → …),
     *  persisting the choice so it survives restarts. */
    fun cycleSprite() {
        markInteraction()
        val next = PixelSprites.next(_state.value.spriteId).id
        _state.update { it.copy(spriteId = next, avatarPhoto = null) }
        avatarRepository?.let { repo -> viewModelScope.launch { repo.saveSpriteId(next) } }
    }

    fun openStatusSheet() { _showStatusSheet.value = true }    fun dismissStatusSheet() { _showStatusSheet.value = false }

    fun requestEmergencyConfirm() { _showEmergencyConfirm.value = true }
    fun dismissEmergencyConfirm() { _showEmergencyConfirm.value = false }

    fun confirmEmergencyStop() {
        _showEmergencyConfirm.value = false
        // A hard stop must also tear down any in-flight hands-free voice loop,
        // not just clear the flags — the mic/foreground service stops too.
        runCatching { VoiceLoopService.stop(getApplication()) }
        _state.update {
            it.copy(
                emergencyStop = true,
                thinking = false,
                working = false,
                speaking = false,
                listening = false,
            )
        }
    }

    fun releaseEmergencyStop() {
        _state.update { it.copy(emergencyStop = false) }
    }

    fun approveApproval() {
        _state.update { it.copy(approvalNeeded = false, working = true) }
    }

    private fun systemReducedMotion(): Boolean {
        val ctx = getApplication<Application>()
        val scale = Settings.Global.getFloat(
            ctx.contentResolver,
            Settings.Global.ANIMATOR_DURATION_SCALE,
            1f,
        )
        return scale == 0f
    }

    private companion object {
        const val AMBIENT_TICK_MS = 5_000L
    }
}
