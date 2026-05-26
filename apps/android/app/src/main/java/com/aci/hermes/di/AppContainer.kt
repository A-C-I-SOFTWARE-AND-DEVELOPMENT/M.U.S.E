package com.aci.hermes.di

import android.app.Application
import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.orchestrator.PromptBuilder
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsViewModel
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel
import com.aci.hermes.ui.screens.orchestrator.TaskDetailViewModel
import com.aci.hermes.ui.screens.settings.SettingsViewModel
import com.aci.hermes.util.LogBuffer
import com.aci.hermes.voice.AndroidSpeechRecognizer
import com.aci.hermes.voice.DefaultVoiceCaptureRouter
import com.aci.hermes.voice.ManualVoiceRecognizer
import com.aci.hermes.voice.VoiceCaptureViewModel
import com.aci.hermes.voice.VoiceIntentClassifier
import com.aci.hermes.voice.VoicePendingDraft
import com.aci.hermes.voice.VoiceRecognizer

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

    val voicePendingDraft: VoicePendingDraft = VoicePendingDraft()

    private val voiceIntentClassifier: VoiceIntentClassifier = VoiceIntentClassifier()

    fun voiceCaptureVmFactory(): ViewModelProvider.Factory = factory {
        val recognizer: VoiceRecognizer = runCatching { AndroidSpeechRecognizer(context) }
            .getOrElse { ManualVoiceRecognizer() }
        val effectiveRecognizer: VoiceRecognizer =
            if (recognizer.isAvailable) recognizer else ManualVoiceRecognizer()
        VoiceCaptureViewModel(
            recognizer = effectiveRecognizer,
            router = DefaultVoiceCaptureRouter(
                tasksRepo = taskRepository,
                pendingChatDraft = voicePendingDraft,
            ),
            classifier = voiceIntentClassifier,
        )
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
            voicePendingDraft = voicePendingDraft,
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
