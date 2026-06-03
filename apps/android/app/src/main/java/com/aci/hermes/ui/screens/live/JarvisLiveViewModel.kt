package com.aci.hermes.ui.screens.live

import android.app.Application
import android.graphics.BitmapFactory
import android.provider.Settings
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.avatar.AvatarRepository
import com.aci.hermes.data.avatar.AvatarSource
import com.aci.hermes.data.cockpit.CockpitJobsRepository
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.JobStatus
import com.aci.hermes.data.life.BehaviorScheduler
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TaskSection
import com.aci.hermes.data.model.section
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.service.OrchestratorServiceController
import com.aci.hermes.service.VoiceLoopService
import com.aci.hermes.ui.screens.live.JarvisLivePresenceMapper.BackendPresence
import com.aci.hermes.ui.screens.live.JarvisLivePresenceMapper.JobSignal
import com.aci.hermes.voice.VoicePhase
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
    private val jobsRepository: CockpitJobsRepository? = null,
    private val taskRepository: HermesTaskRepository? = null,
    private val settingsRepository: SettingsRepository? = null,
    private val orchestratorServiceController: OrchestratorServiceController? = null,
    private val presenceController: com.aci.hermes.voice.PresenceModeController? = null,
) : AndroidViewModel(application) {

    /** Hands-free Presence Mode on-off, surfaced to the UI (off when unwired). */
    val presenceEnabled: StateFlow<Boolean> =
        presenceController?.enabled ?: MutableStateFlow(false)

    /** Current presence phase (armed / listening / thinking / speaking). */
    val presenceState: StateFlow<com.aci.hermes.voice.PresenceState> =
        presenceController?.presenceState
            ?: MutableStateFlow(com.aci.hermes.voice.PresenceState.OFF)

    /** True if a wake-word spotter can run; else only tap-to-talk/mic fallback. */
    val wakeWordAvailable: Boolean get() = presenceController?.wakeWordAvailable ?: false

    /** Opt-in camera attention on-off (default off; off when unwired). */
    val cameraAttentionEnabled: StateFlow<Boolean> =
        presenceController?.cameraAttentionEnabled ?: MutableStateFlow(false)

    /** Toggle hands-free Presence Mode. */
    fun togglePresenceMode() {
        markInteraction()
        presenceController?.toggle()
    }

    /** Toggle opt-in camera attention. */
    fun toggleCameraAttention() {
        markInteraction()
        presenceController?.toggleCameraAttention()
    }

    /** Tap-to-talk / mic fallback: open the mic now (caller holds RECORD_AUDIO). */
    fun talkNow() {
        markInteraction()
        presenceController?.talkNow()
    }

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

    /** The id of the job to open when the user swipes to "current job"; null
     *  when there is no active job. Surfaced so the screen can route to it. */
    private val _currentJobId = MutableStateFlow<String?>(null)
    val currentJobId: StateFlow<String?> = _currentJobId.asStateFlow()

    // Optimistic "thinking" feedback while a typed command is in flight. It is
    // self-clearing (see [onSend]) so it can never get stuck the way the old
    // demo flag did; the real backend poll overrides it on the next tick.
    private val _commandInFlight = MutableStateFlow(false)

    /** Snapshot of the things only reachable by an explicit request/poll.
     *  Declared before [init] so the presence combine never reads it null. */
    private data class RuntimePoll(
        val connected: Boolean = true,
        val running: Int = 0,
        val queued: Int = 0,
        val waitingApproval: Int = 0,
        val pendingApprovals: Int = 0,
    )

    private val _runtimePoll = MutableStateFlow(RuntimePoll())

    init {
        startAmbientLife()
        observeSavedAvatar()
        loadFurniture()
        observeBackendPresence()
    }

    /**
     * The core wiring: derive the avatar's activity from REAL signals — runtime
     * queue + approvals (polled), cockpit jobs, the active task's worker phase,
     * the persisted emergency stop, and the voice-loop phase. Without the
     * cockpit deps (e.g. in isolated tests) the avatar simply stays ambient.
     */
    private fun observeBackendPresence() {
        val jobsRepo = jobsRepository ?: return
        val tasksRepo = taskRepository ?: return

        // Poll the runtime + approvals; these have no push channel.
        viewModelScope.launch {
            while (isActive) {
                refreshRuntimePoll()
                delay(RUNTIME_POLL_MS)
            }
        }

        viewModelScope.launch {
            val emergencyFlow = settingsRepository?.emergencyStopEngaged
                ?: MutableStateFlow(false)
            val presence = combine(
                _runtimePoll,
                jobsRepo.jobs,
                tasksRepo.tasks,
                emergencyFlow,
                VoiceLoopService.phaseFlow,
            ) { poll, jobs, tasks, emergency, voicePhase ->
                buildPresence(poll, jobs, tasks, emergency, voicePhase)
            }
            combine(presence, _commandInFlight) { p, inFlight -> p to inFlight }
                .collect { (snapshot, inFlight) ->
                    val flags = JarvisLivePresenceMapper.flagsFor(snapshot)
                    markInteractionIfBusy(flags)
                    _state.update {
                        it.copy(
                            listening = flags.listening,
                            // Optimistic local feedback ORs into thinking.
                            thinking = flags.thinking || inFlight,
                            researching = flags.researching,
                            coding = flags.coding,
                            reviewing = flags.reviewing,
                            working = flags.working,
                            speaking = flags.speaking,
                            approvalNeeded = flags.approvalNeeded,
                            blocked = flags.blocked,
                            warning = flags.warning,
                            disconnected = flags.disconnected,
                            emergencyStop = flags.emergencyStop,
                        )
                    }
                }
        }
    }

    private suspend fun refreshRuntimePoll() {
        val client = cockpitClient ?: return
        if (!client.isPaired()) {
            _runtimePoll.value = RuntimePoll(connected = false)
            return
        }
        val status = client.runtimeStatus()
        val approvals = client.approvalsList()
        val connected = status is CockpitResult.Success
        val queue = (status as? CockpitResult.Success)?.value?.queue
        val pending = (approvals as? CockpitResult.Success)
            ?.value?.approvals?.count { it.status.equals("PENDING", ignoreCase = true) } ?: 0
        _runtimePoll.value = RuntimePoll(
            connected = connected,
            running = queue?.running ?: 0,
            queued = queue?.queued ?: 0,
            waitingApproval = queue?.waitingApproval ?: 0,
            pendingApprovals = pending,
        )
    }

    private fun buildPresence(
        poll: RuntimePoll,
        jobs: List<com.aci.hermes.data.cockpit.CockpitJob>,
        tasks: List<HermesTask>,
        emergency: Boolean,
        voicePhase: VoicePhase,
    ): BackendPresence {
        // The active task drives the fine phase; its id (or the newest running
        // job's) is what "swipe to current job" opens.
        val activeTask = tasks.firstOrNull { it.section() == TaskSection.ACTIVE }
        _currentJobId.value = activeTask?.id
            ?: jobs.firstOrNull {
                JobStatus.fromWire(it.status) == JobStatus.RUNNING
            }?.id
        return BackendPresence(
            connected = poll.connected,
            emergencyEngaged = emergency,
            running = poll.running,
            queued = poll.queued,
            waitingApproval = poll.waitingApproval,
            pendingApprovals = poll.pendingApprovals,
            jobs = jobs.map {
                JobSignal(
                    status = JobStatus.fromWire(it.status),
                    failedGates = it.validationSummary?.fail ?: 0,
                )
            },
            activePhase = activeTask?.workerPhase,
            voicePhase = voicePhase,
        )
    }

    private fun markInteractionIfBusy(flags: JarvisLivePresenceMapper.PresenceFlags) {
        if (flags.listening || flags.speaking || flags.working || flags.coding ||
            flags.researching || flags.reviewing
        ) {
            markInteraction()
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
        if (current.command.isBlank() || current.emergencyStop) return
        // Optimistic, self-clearing feedback. Real backend state (a new job /
        // worker phase) overrides this on the next poll; the timeout guarantees
        // it can never stick the way the old demo flag did.
        _commandInFlight.value = true
        // Immediate optimistic feedback so a typed command shows "thinking"
        // even with no backend pipeline (unpaired / standalone / tests). When
        // cockpit repos are present, the presence combine ORs _commandInFlight
        // into thinking and keeps it accurate against real worker phases.
        _state.update { it.copy(thinking = true) }
        viewModelScope.launch {
            delay(COMMAND_FEEDBACK_MS)
            _commandInFlight.value = false
            // No presence pipeline to recompute it → clear the optimistic flag.
            if (jobsRepository == null || taskRepository == null) {
                _state.update { it.copy(thinking = false) }
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
        // Real global stop: halt the orchestrator service AND persist the
        // engaged flag so every surface (this avatar, the overlay, Control)
        // reflects it. The avatar's EmergencyStop state then derives from the
        // persisted flag via the presence pipeline.
        orchestratorServiceController?.emergencyStop()
        _commandInFlight.value = false
        if (settingsRepository != null) {
            viewModelScope.launch { settingsRepository.setEmergencyStopEngaged(true) }
        } else {
            // Standalone / test fallback with no persistence: local flag only.
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
    }

    fun releaseEmergencyStop() {
        if (settingsRepository != null) {
            viewModelScope.launch { settingsRepository.setEmergencyStopEngaged(false) }
        } else {
            _state.update { it.copy(emergencyStop = false) }
        }
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
        const val RUNTIME_POLL_MS = 5_000L
        const val COMMAND_FEEDBACK_MS = 8_000L
    }
}
