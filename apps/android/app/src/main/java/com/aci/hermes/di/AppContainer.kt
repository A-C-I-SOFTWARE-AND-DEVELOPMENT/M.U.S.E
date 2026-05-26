package com.aci.hermes.di

import android.app.Application
import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.aci.hermes.data.approvals.ApprovalRepository
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.gateway.FakeGatewayClient
import com.aci.hermes.data.gateway.GatewayClient
import com.aci.hermes.data.gateway.GatewayEventSpine
import com.aci.hermes.data.gateway.TermuxGatewayClient
import com.aci.hermes.data.memory.MemoryRepository
import com.aci.hermes.data.model.Approval
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.orchestrator.PromptBuilder
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.data.social.SocialIntelligenceRepository
import com.aci.hermes.data.termux.TermuxIntentBridge
import com.aci.hermes.ui.screens.approvals.ApprovalDetailViewModel
import com.aci.hermes.ui.screens.approvals.ApprovalsViewModel
import com.aci.hermes.ui.screens.audit.AuditDetailViewModel
import com.aci.hermes.ui.screens.audit.AuditViewModel
import com.aci.hermes.ui.screens.chat.ChatViewModel
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsViewModel
import com.aci.hermes.ui.screens.home.HomeViewModel
import com.aci.hermes.ui.screens.memory.MemoryViewModel
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel
import com.aci.hermes.ui.screens.orchestrator.TaskDetailViewModel
import com.aci.hermes.ui.screens.settings.SettingsViewModel
import com.aci.hermes.ui.screens.social.SocialIntelligenceViewModel
import com.aci.hermes.ui.screens.voice.VoiceCaptureViewModel
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/**
 * Hand-rolled DI container. Held by [com.aci.hermes.HermesApplication]
 * for the lifetime of the process. ViewModel factories pull
 * dependencies out of this container.
 *
 * The Jarvis Prime integration adds repositories for approvals,
 * memory, social intelligence, audit and the gateway spine. The
 * spine swaps the active gateway client when the user toggles
 * Mock / Termux mode in settings.
 */
class AppContainer(private val application: Application) {

    private val context: Context = application
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    val logBuffer: LogBuffer = LogBuffer()

    val settingsRepository: SettingsRepository = SettingsRepository(context)

    val taskRepository: HermesTaskRepository = HermesTaskRepository(context)

    val promptBuilder: PromptBuilder = PromptBuilder()

    val emergencyStop: EmergencyStopController = EmergencyStopController()
    val auditRepository: AuditRepository = AuditRepository()
    val approvalRepository: ApprovalRepository = ApprovalRepository(emergencyStop)
    val memoryRepository: MemoryRepository = MemoryRepository()
    val socialRepository: SocialIntelligenceRepository = SocialIntelligenceRepository()

    val termuxBridge: TermuxIntentBridge = TermuxIntentBridge(context)
    val spine: GatewayEventSpine = GatewayEventSpine()
    val fakeGateway: FakeGatewayClient = FakeGatewayClient()
    val termuxGateway: TermuxGatewayClient = TermuxGatewayClient(termuxBridge)

    init {
        spine.bind(fakeGateway)
        scope.launch {
            if (settingsRepository.emergencyStop.first()) {
                emergencyStop.arm(null)
            }
            fakeGateway.start()
            approvalRepository.replaceAll(fakeGateway.approvals)
            launch {
                fakeGateway.events.collect { _ ->
                    approvalRepository.replaceAll(fakeGateway.approvals)
                }
            }
        }
        scope.launch {
            settingsRepository.termuxMode.collect { enabled ->
                val target: GatewayClient = if (enabled) termuxGateway else fakeGateway
                spine.bind(target)
                target.start()
            }
        }
    }

    fun homeVmFactory(): ViewModelProvider.Factory = factory {
        HomeViewModel(
            approvals = approvalRepository,
            audit = auditRepository,
            emergency = emergencyStop,
            spine = spine,
            settings = settingsRepository,
        )
    }

    fun chatVmFactory(): ViewModelProvider.Factory = factory {
        ChatViewModel(spine = spine, emergency = emergencyStop, audit = auditRepository)
    }

    fun voiceVmFactory(): ViewModelProvider.Factory = factory {
        VoiceCaptureViewModel(spine = spine, tasksRepo = taskRepository)
    }

    fun approvalsVmFactory(): ViewModelProvider.Factory = factory {
        ApprovalsViewModel(approvalRepository, emergencyStop, auditRepository, spine)
    }

    fun approvalDetailVmFactory(id: String): ViewModelProvider.Factory = factory {
        ApprovalDetailViewModel(id, approvalRepository, emergencyStop, auditRepository, spine)
    }

    fun memoryVmFactory(): ViewModelProvider.Factory = factory {
        MemoryViewModel(memoryRepository, auditRepository)
    }

    fun socialVmFactory(): ViewModelProvider.Factory = factory {
        SocialIntelligenceViewModel(socialRepository)
    }

    fun auditVmFactory(): ViewModelProvider.Factory = factory {
        AuditViewModel(auditRepository)
    }

    fun auditDetailVmFactory(id: String): ViewModelProvider.Factory = factory {
        AuditDetailViewModel(id, auditRepository)
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

    @Suppress("unused")
    fun seedApprovalForTests(approval: Approval) {
        approvalRepository.upsert(approval)
    }
}
