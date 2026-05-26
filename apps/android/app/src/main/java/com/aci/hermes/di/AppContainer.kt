package com.aci.hermes.di

import android.app.Application
import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.aci.hermes.approvals.ApprovalQueue
import com.aci.hermes.audit.AuditLog
import com.aci.hermes.conversation.ConversationEngine
import com.aci.hermes.conversation.ConversationStore
import com.aci.hermes.conversation.MockConversationEngine
import com.aci.hermes.data.memory.MemoryRepository
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.events.EventSpine
import com.aci.hermes.gateway.JarvisGatewayClient
import com.aci.hermes.gateway.MockJarvisGatewayClient
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.orchestrator.PromptBuilder
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.safety.EmergencyStop
import com.aci.hermes.safety.PermissionKernel
import com.aci.hermes.ui.screens.approvals.ApprovalsViewModel
import com.aci.hermes.ui.screens.audit.AuditViewModel
import com.aci.hermes.ui.screens.conversation.ConversationViewModel
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsViewModel
import com.aci.hermes.ui.screens.memory.MemoryViewModel
import com.aci.hermes.ui.screens.operations.OperationsViewModel
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel
import com.aci.hermes.ui.screens.orchestrator.TaskDetailViewModel
import com.aci.hermes.ui.screens.settings.SettingsViewModel
import com.aci.hermes.util.LogBuffer
import java.util.concurrent.atomic.AtomicReference

/**
 * Process-scoped DI container for Jarvis Prime. Owned by
 * [com.aci.hermes.HermesApplication]. ViewModel factories pull
 * dependencies from here so screens never instantiate subsystems
 * directly.
 *
 * The Activity binds its system-prompt launcher into the container so
 * the [PermissionKernel] can hand off to the OS dialog from anywhere
 * in the app without holding an Activity reference.
 */
class AppContainer(private val application: Application) {

    private val context: Context = application

    val logBuffer: LogBuffer = LogBuffer()

    val settingsRepository: SettingsRepository = SettingsRepository(context)

    val taskRepository: HermesTaskRepository = HermesTaskRepository(context)

    val promptBuilder: PromptBuilder = PromptBuilder()

    val permissionKernel: PermissionKernel = PermissionKernel()

    val emergencyStop: EmergencyStop = EmergencyStop()

    val memoryRepository: MemoryRepository = MemoryRepository(context)

    /**
     * Conversation engine. Defaults to the offline mock so the UI works
     * before the gateway is wired in. The gateway-backed implementation
     * (see Wave 7) will replace this binding without changing the
     * `ConversationEngine` interface.
     */
    val conversationEngine: ConversationEngine = MockConversationEngine()

    val conversationStore: ConversationStore = ConversationStore()

    /** Event spine for in-process subsystem fan-out. */
    val eventSpine: EventSpine = EventSpine()

    /**
     * Jarvis Prime Gateway client. Defaults to the offline mock so
     * the Operations screen renders before a real gateway is configured.
     */
    val gatewayClient: JarvisGatewayClient = MockJarvisGatewayClient()

    /** Pending approvals. Hooked into the emergency stop at construction. */
    val approvalQueue: ApprovalQueue = ApprovalQueue(eventSpine, emergencyStop)

    /** Persistent audit log. Subscribes to the event spine at construction. */
    val auditLog: AuditLog = AuditLog(context, eventSpine)

    private val activityLauncher = AtomicReference<PermissionKernel.SystemPromptLauncher?>(null)

    fun bindActivityPromptLauncher(launcher: PermissionKernel.SystemPromptLauncher) {
        activityLauncher.set(launcher)
    }

    fun unbindActivityPromptLauncher(launcher: PermissionKernel.SystemPromptLauncher) {
        activityLauncher.compareAndSet(launcher, null)
    }

    fun systemPromptLauncher(): PermissionKernel.SystemPromptLauncher? = activityLauncher.get()

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

    fun memoryVmFactory(): ViewModelProvider.Factory = factory {
        MemoryViewModel(memoryRepository)
    }

    fun conversationVmFactory(): ViewModelProvider.Factory = factory {
        ConversationViewModel(
            engine = conversationEngine,
            store = conversationStore,
            logBuffer = logBuffer,
        )
    }

    fun operationsVmFactory(): ViewModelProvider.Factory = factory {
        OperationsViewModel(client = gatewayClient, spine = eventSpine)
    }

    fun approvalsVmFactory(): ViewModelProvider.Factory = factory {
        ApprovalsViewModel(queue = approvalQueue, audit = auditLog)
    }

    fun auditVmFactory(): ViewModelProvider.Factory = factory {
        AuditViewModel(audit = auditLog)
    }

    private inline fun <reified VM : ViewModel> factory(crossinline build: () -> VM): ViewModelProvider.Factory =
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T = build() as T
        }
}
