package com.aci.hermes.di

import android.app.Application
import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.aci.hermes.approval.event.ApprovalEventSink
import com.aci.hermes.approval.event.RecordingApprovalEventSink
import com.aci.hermes.approval.state.ApprovalStore
import com.aci.hermes.approval.state.CockpitApprovalsRepository
import com.aci.hermes.approval.state.ApprovalViewModel
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.ledger.LedgerRepository
import com.aci.hermes.data.audit.EmptyAuditSeed
import com.aci.hermes.data.avatar.AvatarImageStore
import com.aci.hermes.data.avatar.AvatarPixelator
import com.aci.hermes.data.avatar.AvatarRepository
import com.aci.hermes.data.capability.CapabilityRepository
import com.aci.hermes.data.cockpit.CockpitHomeRepository
import com.aci.hermes.data.cockpit.CockpitJobsRepository
import com.aci.hermes.data.cockpit.CockpitModelRoutesRepository
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.devicecontrol.DeviceActionLedger
import com.aci.hermes.data.devicecontrol.DeviceControlController
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.emergency.EmergencyStopRepository
import com.aci.hermes.data.emergency.EmergencyStopState
import com.aci.hermes.data.jarvis.AndroidJarvisClipboard
import com.aci.hermes.data.jarvis.HttpJarvisChatGateway
import com.aci.hermes.data.jarvis.JarvisChatGateway
import com.aci.hermes.data.jarvis.JarvisClipboard
import com.aci.hermes.data.jarvis.JarvisTaskSink
import com.aci.hermes.data.jarvis.MockJarvisChatGateway
import com.aci.hermes.data.jarvis.RepositoryTaskSink
import com.aci.hermes.data.jarvis.RoutingJarvisChatGateway
import com.aci.hermes.data.evidence.EvidenceRepository
import com.aci.hermes.data.memory.MemoryRepository
import com.aci.hermes.data.memory.MemoryTreeRepository
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.orchestrator.PromptBuilder
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.data.research.ResearchRepository
import com.aci.hermes.notify.JarvisNotifier
import com.aci.hermes.notify.WorkEvent
import com.aci.hermes.notify.WorkWatcher
import com.aci.hermes.service.WorkWatchService
import com.aci.hermes.ui.screens.avatar.AvatarPickerViewModel
import com.aci.hermes.service.OrchestratorServiceController
import com.aci.hermes.ui.screens.audit.AuditDetailViewModel
import com.aci.hermes.ui.screens.audit.AuditViewModel
import com.aci.hermes.ui.screens.ledger.LedgerEventDetailViewModel
import com.aci.hermes.ui.screens.ledger.LedgerTimelineViewModel
import com.aci.hermes.ui.screens.capability.CapabilityViewModel
import com.aci.hermes.ui.screens.chat.JarvisChatViewModel
import com.aci.hermes.ui.screens.control.ControlViewModel
import com.aci.hermes.ui.screens.devicecontrol.DeviceControlViewModel
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsViewModel
import com.aci.hermes.ui.screens.jobs.JobsViewModel
import com.aci.hermes.service.JobNotifier
import com.aci.hermes.ui.screens.home.JarvisPrimeHomeViewModel
import com.aci.hermes.ui.screens.jobs.CockpitJobsViewModel
import com.aci.hermes.ui.screens.jobs.JobDetailViewModel
import com.aci.hermes.ui.screens.live.JarvisLiveViewModel
import com.aci.hermes.ui.screens.evidence.EvidenceViewModel
import com.aci.hermes.ui.screens.memory.MemoryViewModel
import com.aci.hermes.ui.screens.modelroute.ModelRouteViewModel
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel
import com.aci.hermes.ui.screens.research.ResearchViewModel
import com.aci.hermes.ui.screens.orchestrator.TaskDetailViewModel
import com.aci.hermes.ui.screens.settings.SettingsViewModel
import com.aci.hermes.ui.screens.voice.VoiceCaptureViewModel
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.drop
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Hand-rolled DI container. Held by [com.aci.hermes.HermesApplication]
 * for the lifetime of the process. ViewModel factories pull
 * dependencies out of this container.
 *
 * Scope is intentionally tiny — Hermes is a local orchestrator and
 * does not talk to remote services from the app process.
 */
class AppContainer(private val application: Application) {

    private val context: Context = application

    val logBuffer: LogBuffer = LogBuffer()

    val settingsRepository: SettingsRepository = SettingsRepository(context)

    val taskRepository: HermesTaskRepository = HermesTaskRepository(context)

    val promptBuilder: PromptBuilder = PromptBuilder()

    val avatarImageStore: AvatarImageStore = AvatarImageStore(context)

    val avatarPixelator: AvatarPixelator = AvatarPixelator(context, avatarImageStore)

    val avatarRepository: AvatarRepository = AvatarRepository(context, avatarImageStore)

    val orchestratorServiceController: OrchestratorServiceController =
        OrchestratorServiceController(context, logBuffer)

    // Capability is a deliberately curated in-app catalog (not server-backed,
    // not mock). Memory + Audit are cut over to the cockpit client below,
    // once it's constructed.
    val capabilityRepository: CapabilityRepository = CapabilityRepository()

    // ── Cockpit connection (settings-backed) ───────────────────────────
    //
    // The container is built synchronously, but the gateway endpoint and
    // the paired token live in DataStore (async Flows). We mirror both
    // into volatile caches kept current by a long-lived collector, so the
    // synchronous `() -> ...` providers the client + gateways need always
    // see the latest value without being rebuilt on every settings change.
    private val containerScope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    @Volatile
    private var cachedEndpoint: String = SettingsRepository.DEFAULT_GATEWAY_ENDPOINT

    @Volatile
    private var cachedToken: String? = null

    init {
        settingsRepository.gatewayEndpoint
            .onEach { cachedEndpoint = it }
            .launchIn(containerScope)
        settingsRepository.cockpitToken
            .onEach { cachedToken = it }
            .launchIn(containerScope)
    }

    private fun cockpitEndpoint(): String = cachedEndpoint
    private fun cockpitToken(): String? = cachedToken
    private fun cockpitPaired(): Boolean =
        !cachedToken.isNullOrBlank() && cachedEndpoint.isNotBlank()

    /**
     * Live cockpit API client (runtime status, worker detection, health
     * negotiation, and a raw passthrough for the rest). Screens read
     * through this; an unpaired or unreachable gateway yields a typed
     * `Unreachable`, never a stub.
     */
    val cockpitClient: HermesCockpitClient = HermesCockpitClient(
        endpointProvider = ::cockpitEndpoint,
        tokenProvider = ::cockpitToken,
    )

    // Memory: live off the cockpit gateway when paired. Production wires an
    // EMPTY seed (no mock data ever reaches a paired user); the mock seed
    // default stays for @Preview / tests only. The ViewModel calls
    // refresh() to pull the real list.
    val memoryRepository: MemoryRepository = MemoryRepository(
        seed = emptyList(),
        client = cockpitClient,
        paired = ::cockpitPaired,
    )

    // Evidence Engine: live off the cockpit gateway when paired. Empty seed in
    // production (no mock reaches a paired user); the mock seed default stays
    // for @Preview / tests only. The ViewModel calls refresh() for the real list.
    val evidenceRepository: EvidenceRepository = EvidenceRepository(
        seed = emptyList(),
        client = cockpitClient,
        paired = ::cockpitPaired,
    )

    // Memory Tree (MEM-2): the proposed-inbox / contradiction / freshness
    // surface, backed by the provenance-first MemoryTreeStore over the cockpit.
    val memoryTreeRepository: MemoryTreeRepository = MemoryTreeRepository(
        client = cockpitClient,
        paired = ::cockpitPaired,
    )

    /** Jobs (contract §4) — list/dispatch/cancel over the real JobQueue. */
    /** Jobs (contract §4) — list/dispatch/cancel/controls over the real backend. */
    val cockpitJobsRepository: CockpitJobsRepository = CockpitJobsRepository(cockpitClient)

    /** GraphRAG knowledge graph — related items + query modes + rebuild. */
    val cockpitGraphRepository: com.aci.hermes.data.cockpit.CockpitGraphRepository =
        com.aci.hermes.data.cockpit.CockpitGraphRepository(cockpitClient)

    val cockpitModelRoutesRepository: CockpitModelRoutesRepository =
        CockpitModelRoutesRepository(cockpitClient)
    /**
     * Aggregated read overlay behind the home command center — fans out to
     * every cockpit read (runtime/models/workers/jobs/approvals/memory/
     * events/research) and degrades honestly when unpaired/unreachable.
     */
    val cockpitHomeRepository: CockpitHomeRepository = CockpitHomeRepository(cockpitClient)

    /**
     * Audited emergency-stop controller (state machine + decision ledger +
     * resume approval). Process-wide; loaded once so an engaged stop
     * survives restarts. Backs the home "Stop all work" action.
     */
    val emergencyStopRepository: EmergencyStopRepository =
        EmergencyStopRepository(context.filesDir)
    val emergencyStopController: EmergencyStopController =
        EmergencyStopController(emergencyStopRepository, logBuffer).also { it.load() }
    /** Keeps active owner-started jobs visible (and deep-linkable) while backgrounded. */
    val jobNotifier: JobNotifier = JobNotifier(application)
    // Research Mode: always live (no mock seed) — it needs the backend Evidence
    // Engine. Unpaired apps see an honest "pair a gateway" hint, never findings.
    val researchRepository: ResearchRepository = ResearchRepository(
        client = cockpitClient,
        paired = ::cockpitPaired,
    )

    // Audit: live off the cockpit decision-ledger when paired (empty seed in
    // production — no mock reaches a paired user; mock seed stays for tests).
    val auditRepository: AuditRepository = AuditRepository(
        seed = EmptyAuditSeed,
        client = cockpitClient,
        paired = ::cockpitPaired,
    )

    // Activity timeline: the redacted orchestrator event ledger
    // (GET /v1/cockpit/ledger). Empty until paired — no fabricated events.
    val ledgerRepository: LedgerRepository = LedgerRepository(
        client = cockpitClient,
        paired = ::cockpitPaired,
    )

    // Jarvis Prime chat.
    //
    // [liveJarvisChatGateway] streams the real agent from the cockpit
    // gateway, attaching the paired bearer token. [MockJarvisChatGateway]
    // stays the offline-safe path so previews / first-run / tests work
    // with no daemon. [RoutingJarvisChatGateway] selects between them at
    // send-time on whether the cockpit is paired — so pairing a token
    // flips chat live with no rebuild.
    val liveJarvisChatGateway: JarvisChatGateway = HttpJarvisChatGateway(
        endpointProvider = ::cockpitEndpoint,
        logBuffer = logBuffer,
        tokenProvider = ::cockpitToken,
    )
    private val mockJarvisChatGateway: JarvisChatGateway = MockJarvisChatGateway()
    val jarvisChatGateway: JarvisChatGateway = RoutingJarvisChatGateway(
        live = liveJarvisChatGateway,
        mock = mockJarvisChatGateway,
        useLive = ::cockpitPaired,
    )
    val jarvisClipboard: JarvisClipboard = AndroidJarvisClipboard(context)
    val jarvisTaskSink: JarvisTaskSink = RepositoryTaskSink(taskRepository)

    // ── Mobile-native device control ───────────────────────────────────
    //
    // The broker chokepoint + append-only action ledger that let Jarvis
    // operate the phone safely. Constructing the controller also wires the
    // accessibility service's gesture guard (so the emergency halt drops
    // gestures) — see DeviceControlController.init.
    val deviceActionLedger: DeviceActionLedger = DeviceActionLedger(context.filesDir)
    val deviceControlController: DeviceControlController = DeviceControlController(
        context = context,
        settings = settingsRepository,
        ledger = deviceActionLedger,
        logBuffer = logBuffer,
    )

    // Voice loop wiring: bind the on-device STT/TTS engines and the agent
    // dispatch so VoiceLoopService (barge-in conversation) can run once started.
    // The loop is started explicitly from the UI behind RECORD_AUDIO consent —
    // this only makes the engines available, it does not open the mic.
    init {
        com.aci.hermes.service.VoiceLoopService.Wiring.apply {
            // Keyless on-device wake word ("jarvis") so hands-free Presence Mode
            // works without a cloud key; a dedicated spotter (Picovoice) is a
            // drop-in upgrade that would need an access key (not in source).
            wakeWordFactory = { ctx -> com.aci.hermes.voice.KeywordSpeechWakeWordEngine(ctx) }
            sttFactory = { ctx -> com.aci.hermes.voice.AndroidSpeechRecognizerStt(ctx) }
            ttsFactory = { ctx -> com.aci.hermes.voice.AndroidTtsEngine(ctx) }
            dispatch = { utterance -> voiceDispatchToAgent(utterance) }
            // Device-driving commands flow through the broker, not straight
            // to the gesture layer — so consent, confirmation, the emergency
            // halt, and the action ledger all apply.
            performAutomation = { overlay, intent ->
                deviceControlController.dispatchFromVoice(overlay, intent)
            }
        }
    }

    /** Hands-free Presence Mode orchestrator (wake word / tap-to-talk + overlay). */
    val presenceModeController: com.aci.hermes.voice.PresenceModeController =
        com.aci.hermes.voice.PresenceModeController(context, settingsRepository)

    /** Send a spoken utterance to the real agent and return its reply text. */
    private suspend fun voiceDispatchToAgent(utterance: String): String {
        val reply = StringBuilder()
        jarvisChatGateway.send(emptyList(), utterance).collect { chunk ->
            if (chunk is com.aci.hermes.data.jarvis.JarvisChatChunk.Body) {
                reply.append(chunk.text)
            }
        }
        return reply.toString().trim()
    }

    /**
     * Approval-event sink. The cockpit doesn't ship a real gateway transport
     * yet; this in-memory recorder lets the UI run end-to-end and lets the
     * runtime swap in a real sink later via a setter or a Hilt-style binding.
     */
    val approvalEventSink: ApprovalEventSink = RecordingApprovalEventSink()

    /**
     * Process-wide approval store. Cards are seeded by the gateway/runtime
     * in production; for now, start empty.
     */
    val approvalStore: ApprovalStore = ApprovalStore(sink = approvalEventSink)

    /** Gateway-backed owner-approval queue (loads real pending cards). */
    val cockpitApprovalsRepository: CockpitApprovalsRepository =
        CockpitApprovalsRepository(cockpitClient)

    /** Gateway-backed learning-dataset candidate queue (owner review). */
    val learningRepository: com.aci.hermes.learning.state.LearningRepository =
        com.aci.hermes.learning.state.LearningRepository(cockpitClient)

    // ── Long-running-work notifications ────────────────────────────────
    //
    // A local-only watcher polls the cockpit repositories and posts Android
    // notifications on state transitions. No FCM, no SSE — see
    // docs/mobile/mobile-app-guide.md ("How notifications work"). Polling is
    // never permanently on: the in-app foreground poller below runs only
    // while the app is visible, and escalates to WorkWatchService (which
    // self-stops when idle) so active work keeps notifying after the app is
    // backgrounded.
    val jarvisNotifier: JarvisNotifier = JarvisNotifier(context)

    val workWatcher: WorkWatcher = WorkWatcher(
        jobsRepo = cockpitJobsRepository,
        approvalsRepo = cockpitApprovalsRepository,
        client = cockpitClient,
        notifier = jarvisNotifier,
        emergencyActive = { emergencyStopController.state.value.isActive },
        notificationsEnabled = { settingsRepository.notificationsEnabled.first() },
    )

    /**
     * Route a notification tap wants opened. MainActivity publishes here from
     * the launch intent; HermesNavHost consumes it and navigates, then calls
     * [consumeDeepLink].
     */
    private val _pendingDeepLink = MutableStateFlow<String?>(null)
    val pendingDeepLink: StateFlow<String?> = _pendingDeepLink.asStateFlow()

    fun requestDeepLink(route: String?) {
        if (!route.isNullOrBlank()) _pendingDeepLink.value = route
    }

    fun consumeDeepLink() {
        _pendingDeepLink.value = null
    }

    private var foregroundPollJob: Job? = null

    init {
        // Restore any engaged stop (survives process death) and surface an
        // emergency-stop notification the instant the gate engages — fast,
        // independent of whether the watch service happens to be running.
        emergencyStopController.load()
        emergencyStopController.state
            .map { it.isActive }
            .distinctUntilChanged()
            .drop(1) // skip the restored/initial value; only fire on a transition
            .onEach { active ->
                if (active && settingsRepository.notificationsEnabled.first()) {
                    jarvisNotifier.post(WorkEvent.EmergencyStopTriggered(label = ""))
                }
            }
            .launchIn(containerScope)
    }

    /**
     * Engage the emergency stop (records + audits state) and stop the
     * orchestrator service. The single entry point every Emergency Stop
     * surface routes through.
     */
    fun emergencyStop(source: String = "ui_emergency_stop") {
        containerScope.launch {
            emergencyStopController.engage(source = source, target = EmergencyStopState.HARD_STOP)
            // Keep the settings-backed flag in sync: the Control screen + Home
            // dashboard read `emergencyStopEngaged` to show the stop and to gate
            // `startJarvis()`. Without this, a global stop would engage the
            // controller but leave those surfaces showing "inactive" and still
            // able to restart HermesService.
            settingsRepository.setEmergencyStopEngaged(true)
        }
        orchestratorServiceController.emergencyStop()
    }

    /**
     * Begin the lightweight foreground poll loop while the app is visible.
     * On the first tick that sees active work it hands off to
     * [WorkWatchService] so notifications keep flowing after the app leaves
     * the foreground. Idempotent.
     */
    fun onAppForeground() {
        if (foregroundPollJob?.isActive == true) return
        foregroundPollJob = containerScope.launch {
            while (isActive) {
                val result = runCatching { workWatcher.tick() }.getOrNull()
                if (result?.hasActiveWork == true) {
                    WorkWatchService.start(context)
                }
                val intervalSec = settingsRepository.notificationPollIntervalSeconds.first()
                delay(intervalSec.coerceIn(10L, 600L) * 1000L)
            }
        }
    }

    /** Stop the foreground poll loop (the watch service, if active, continues). */
    fun onAppBackground() {
        foregroundPollJob?.cancel()
        foregroundPollJob = null
    }

    fun orchestratorVmFactory(): ViewModelProvider.Factory = factory {
        OrchestratorViewModel(
            application = application,
            settings = settingsRepository,
            tasksRepo = taskRepository,
            promptBuilder = promptBuilder,
            logBuffer = logBuffer,
            cockpitClient = cockpitClient,
            endpointConfigured = { cockpitEndpoint().isNotBlank() },
        )
    }

    fun taskDetailVmFactory(taskId: String?, initialTarget: TargetTool?): ViewModelProvider.Factory = factory {
        TaskDetailViewModel(
            application = application,
            tasksRepo = taskRepository,
            promptBuilder = promptBuilder,
            settings = settingsRepository,
            logBuffer = logBuffer,
            initialTaskId = taskId,
            initialTarget = initialTarget,
        )
    }

    fun settingsVmFactory(): ViewModelProvider.Factory = factory {
        SettingsViewModel(settingsRepository, taskRepository, logBuffer)
    }

    fun diagnosticsVmFactory(): ViewModelProvider.Factory = factory {
        DiagnosticsViewModel(logBuffer, cockpitClient)
    }

    fun modelRouteVmFactory(): ViewModelProvider.Factory = factory {
        ModelRouteViewModel(cockpitModelRoutesRepository)
    }

    fun avatarPickerVmFactory(): ViewModelProvider.Factory = factory {
        AvatarPickerViewModel(
            application = application,
            pixelator = avatarPixelator,
            imageStore = avatarImageStore,
            repo = avatarRepository,
            logBuffer = logBuffer,
            cockpitClient = cockpitClient,
        )
    }

    fun approvalsVmFactory(): ViewModelProvider.Factory = factory {
        ApprovalViewModel(approvalStore, cockpitApprovalsRepository)
    }

    fun learningVmFactory(): ViewModelProvider.Factory = factory {
        com.aci.hermes.learning.state.LearningViewModel(learningRepository)
    }

    fun memoryVmFactory(): ViewModelProvider.Factory = factory {
        MemoryViewModel(memoryRepository, logBuffer, memoryTreeRepository)
    }

    fun evidenceVmFactory(): ViewModelProvider.Factory = factory {
        EvidenceViewModel(evidenceRepository, logBuffer)
    }

    fun auditVmFactory(): ViewModelProvider.Factory = factory {
        AuditViewModel(auditRepository)
    }

    fun knowledgeGraphVmFactory(): ViewModelProvider.Factory = factory {
        com.aci.hermes.ui.screens.knowledge.KnowledgeGraphViewModel(cockpitGraphRepository)
    }

    fun auditDetailVmFactory(auditId: String): ViewModelProvider.Factory = factory {
        AuditDetailViewModel(auditRepository, auditId)
    }

    fun ledgerTimelineVmFactory(): ViewModelProvider.Factory = factory {
        LedgerTimelineViewModel(ledgerRepository)
    }

    fun ledgerEventVmFactory(eventId: String): ViewModelProvider.Factory = factory {
        LedgerEventDetailViewModel(ledgerRepository, eventId)
    }

    fun capabilityVmFactory(): ViewModelProvider.Factory = factory {
        CapabilityViewModel(application, capabilityRepository, logBuffer)
    }

    fun controlVmFactory(): ViewModelProvider.Factory = factory {
        ControlViewModel(application, settingsRepository, logBuffer, cockpitClient)
    }

    fun cockpitJobsVmFactory(): ViewModelProvider.Factory = factory {
        CockpitJobsViewModel(cockpitJobsRepository, logBuffer)
    }

    fun deviceControlVmFactory(): ViewModelProvider.Factory = factory {
        DeviceControlViewModel(
            application = application,
            settings = settingsRepository,
            controller = deviceControlController,
            logBuffer = logBuffer,
        )
    }

    fun jobsVmFactory(): ViewModelProvider.Factory = factory {
        JobsViewModel(cockpitJobsRepository, jobNotifier)
    }

    fun jobDetailVmFactory(jobId: String): ViewModelProvider.Factory = factory {
        JobDetailViewModel(cockpitJobsRepository, jobId)
    }

    fun jarvisPrimeHomeVmFactory(): ViewModelProvider.Factory = factory {
        JarvisPrimeHomeViewModel(
            application = application,
            settings = settingsRepository,
            tasksRepo = taskRepository,
            logBuffer = logBuffer,
            homeRepo = cockpitHomeRepository,
            jobsRepo = cockpitJobsRepository,
            emergencyController = emergencyStopController,
        )
    }

    fun jarvisLiveVmFactory(): ViewModelProvider.Factory = factory {
        JarvisLiveViewModel(
            application,
            avatarRepository,
            cockpitClient,
            jobsRepository = cockpitJobsRepository,
            taskRepository = taskRepository,
            settingsRepository = settingsRepository,
            orchestratorServiceController = orchestratorServiceController,
            presenceController = presenceModeController,
        )
    }

    // Cockpit-backed chat ports: job dispatch, owner approval, and evidence/
    // ledger inspection. Each is "available" only while a gateway is paired,
    // so the chat view model falls back to its offline path automatically.
    private val jarvisJobDispatcher = com.aci.hermes.data.cockpit.CockpitJobDispatcher(
        jobs = cockpitJobsRepository,
        paired = ::cockpitPaired,
    )
    private val jarvisApprovalGateway = com.aci.hermes.data.cockpit.CockpitApprovalGateway(
        approvals = cockpitApprovalsRepository,
        paired = ::cockpitPaired,
    )
    private val jarvisRecordInspector = com.aci.hermes.data.cockpit.CockpitRecordInspector(
        client = cockpitClient,
        paired = ::cockpitPaired,
    )

    fun jarvisChatVmFactory(): ViewModelProvider.Factory = factory {
        JarvisChatViewModel(
            gateway = jarvisChatGateway,
            taskSink = jarvisTaskSink,
            logBuffer = logBuffer,
            clipboard = jarvisClipboard,
            jobDispatcher = jarvisJobDispatcher,
            approvalGateway = jarvisApprovalGateway,
            recordInspector = jarvisRecordInspector,
        )
    }

    fun voiceCaptureVmFactory(): ViewModelProvider.Factory = factory {
        VoiceCaptureViewModel(
            taskSink = jarvisTaskSink,
            logBuffer = logBuffer,
        )
    }

    fun researchVmFactory(): ViewModelProvider.Factory = factory {
        ResearchViewModel(researchRepository, logBuffer)
    }

    private inline fun <reified VM : ViewModel> factory(crossinline build: () -> VM): ViewModelProvider.Factory =
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T = build() as T
        }
}
