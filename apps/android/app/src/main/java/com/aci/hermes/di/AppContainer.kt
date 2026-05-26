package com.aci.hermes.di

import android.app.Application
import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.aci.hermes.data.approval.ApprovalRepository
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.conversation.ConversationRepository
import com.aci.hermes.data.conversation.JarvisConversationEngine
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.gateway.GatewayEventBus
import com.aci.hermes.data.memory.MemoryRepository
import com.aci.hermes.data.mock.MockDataSeeder
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.notifications.JarvisNotificationRepository
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.orchestrator.PromptBuilder
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.data.skills.SkillsRepository
import com.aci.hermes.data.social.SocialPatternRepository
import com.aci.hermes.data.termux.TermuxIntentBridge
import com.aci.hermes.ui.screens.approval.ApprovalsViewModel
import com.aci.hermes.ui.screens.audit.AuditViewModel
import com.aci.hermes.ui.screens.chat.ChatViewModel
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsViewModel
import com.aci.hermes.ui.screens.emergency.EmergencyStopViewModel
import com.aci.hermes.ui.screens.gateway.GatewayViewModel
import com.aci.hermes.ui.screens.home.HomeViewModel
import com.aci.hermes.ui.screens.memory.MemoryViewModel
import com.aci.hermes.ui.screens.notifications.NotificationsViewModel
import com.aci.hermes.ui.screens.onboarding.OnboardingViewModel
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel
import com.aci.hermes.ui.screens.orchestrator.TaskDetailViewModel
import com.aci.hermes.ui.screens.settings.SettingsViewModel
import com.aci.hermes.ui.screens.skills.SkillsViewModel
import com.aci.hermes.ui.screens.social.SocialViewModel
import com.aci.hermes.ui.screens.voice.VoiceCaptureViewModel
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * Hand-rolled DI container. Held by [com.aci.hermes.HermesApplication]
 * for the lifetime of the process. ViewModel factories pull
 * dependencies out of this container.
 *
 * Scope is intentionally small — Jarvis Prime is a local-first agent
 * and the app itself does not talk to remote services from the app
 * process. Real model dispatch happens through the Termux gateway or
 * a wired remote gateway.
 */
class AppContainer(private val application: Application) {

    private val context: Context = application
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    val logBuffer: LogBuffer = LogBuffer()

    val settingsRepository: SettingsRepository = SettingsRepository(context)

    val taskRepository: HermesTaskRepository = HermesTaskRepository(context)

    val promptBuilder: PromptBuilder = PromptBuilder()

    // New Jarvis Prime modules
    val conversationRepository: ConversationRepository = ConversationRepository(context)
    val approvalRepository: ApprovalRepository = ApprovalRepository(context)
    val memoryRepository: MemoryRepository = MemoryRepository(context)
    val auditRepository: AuditRepository = AuditRepository(context)
    val gatewayEventBus: GatewayEventBus = GatewayEventBus(context)
    val notificationRepository: JarvisNotificationRepository = JarvisNotificationRepository(context)
    val socialRepository: SocialPatternRepository = SocialPatternRepository(context)
    val skillsRepository: SkillsRepository = SkillsRepository(context)
    val termuxBridge: TermuxIntentBridge = TermuxIntentBridge(context)
    val conversationEngine: JarvisConversationEngine = JarvisConversationEngine()
    val emergencyStop: EmergencyStopController = EmergencyStopController(
        approvalRepository = approvalRepository,
        gateway = gatewayEventBus,
        audit = auditRepository,
        notifications = notificationRepository,
    )

    init {
        scope.launch {
            // Boot every store and seed mock data if appropriate.
            conversationRepository.load()
            approvalRepository.load()
            memoryRepository.load()
            auditRepository.load()
            gatewayEventBus.load()
            notificationRepository.load()
            socialRepository.load()
            skillsRepository.load()

            // Seeding is gated on mock mode being enabled. We read once;
            // subsequent toggles do not retroactively wipe / seed.
            val seeder = MockDataSeeder(
                conversations = conversationRepository,
                approvals = approvalRepository,
                memory = memoryRepository,
                audit = auditRepository,
                gateway = gatewayEventBus,
                notifications = notificationRepository,
                social = socialRepository,
            )
            val isMock = runCatching { settingsRepository.snapshot().mockMode }.getOrDefault(true)
            if (isMock) seeder.seedAll()
        }
    }

    // ── ViewModel factories ────────────────────────────────────────────

    fun homeVmFactory(): ViewModelProvider.Factory = factory {
        HomeViewModel(
            application = application,
            settings = settingsRepository,
            approvals = approvalRepository,
            tasks = taskRepository,
            audit = auditRepository,
            notifications = notificationRepository,
            social = socialRepository,
            memory = memoryRepository,
            gateway = gatewayEventBus,
            emergencyStop = emergencyStop,
        )
    }

    fun chatVmFactory(): ViewModelProvider.Factory = factory {
        ChatViewModel(
            application = application,
            settings = settingsRepository,
            conversations = conversationRepository,
            engine = conversationEngine,
            audit = auditRepository,
            emergencyStop = emergencyStop,
        )
    }

    fun approvalsVmFactory(): ViewModelProvider.Factory = factory {
        ApprovalsViewModel(
            application = application,
            approvals = approvalRepository,
            settings = settingsRepository,
            audit = auditRepository,
            notifications = notificationRepository,
            emergencyStop = emergencyStop,
        )
    }

    fun memoryVmFactory(): ViewModelProvider.Factory = factory {
        MemoryViewModel(
            application = application,
            memory = memoryRepository,
            audit = auditRepository,
        )
    }

    fun socialVmFactory(): ViewModelProvider.Factory = factory {
        SocialViewModel(application, socialRepository)
    }

    fun auditVmFactory(): ViewModelProvider.Factory = factory {
        AuditViewModel(application, audit = auditRepository)
    }

    fun gatewayVmFactory(): ViewModelProvider.Factory = factory {
        GatewayViewModel(
            application = application,
            gateway = gatewayEventBus,
            termux = termuxBridge,
            settings = settingsRepository,
        )
    }

    fun notificationsVmFactory(): ViewModelProvider.Factory = factory {
        NotificationsViewModel(application, notifications = notificationRepository)
    }

    fun emergencyVmFactory(): ViewModelProvider.Factory = factory {
        EmergencyStopViewModel(application, emergencyStop = emergencyStop, audit = auditRepository)
    }

    fun skillsVmFactory(): ViewModelProvider.Factory = factory {
        SkillsViewModel(application, skills = skillsRepository)
    }

    fun voiceVmFactory(): ViewModelProvider.Factory = factory {
        VoiceCaptureViewModel(application, conversations = conversationRepository, audit = auditRepository)
    }

    fun onboardingVmFactory(): ViewModelProvider.Factory = factory {
        OnboardingViewModel(application, settings = settingsRepository)
    }

    fun orchestratorVmFactory(): ViewModelProvider.Factory = factory {
        OrchestratorViewModel(
            application = application,
            settings = settingsRepository,
            tasksRepo = taskRepository,
            promptBuilder = promptBuilder,
            logBuffer = logBuffer,
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
        DiagnosticsViewModel(logBuffer)
    }

    private inline fun <reified VM : ViewModel> factory(crossinline build: () -> VM): ViewModelProvider.Factory =
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T = build() as T
        }
}
