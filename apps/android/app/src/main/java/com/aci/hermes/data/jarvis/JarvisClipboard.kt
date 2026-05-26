package com.aci.hermes.data.jarvis

import android.content.Context
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.orchestrator.HandoffLauncher
import com.aci.hermes.data.orchestrator.HermesTaskRepository

/**
 * Thin abstraction over the system clipboard so the chat view model
 * stays a plain [androidx.lifecycle.ViewModel] (no Application
 * dependency) and unit tests can substitute a fake.
 */
interface JarvisClipboard {
    fun copy(label: String, text: String): Boolean
}

class AndroidJarvisClipboard(private val context: Context) : JarvisClipboard {
    override fun copy(label: String, text: String): Boolean =
        HandoffLauncher.copyPrompt(context, label, text)
}

/** Test double — records writes and reports success. */
class FakeJarvisClipboard : JarvisClipboard {
    val writes: MutableList<Pair<String, String>> = mutableListOf()
    var nextResult: Boolean = true
    override fun copy(label: String, text: String): Boolean {
        writes += label to text
        return nextResult
    }
}

/**
 * Narrow surface the chat VM needs from the task store. Keeps the VM
 * unit-testable without standing up a Context-backed repository.
 */
interface JarvisTaskSink {
    suspend fun upsert(task: HermesTask): HermesTask
}

class RepositoryTaskSink(private val repo: HermesTaskRepository) : JarvisTaskSink {
    override suspend fun upsert(task: HermesTask): HermesTask = repo.upsert(task)
}

class FakeJarvisTaskSink : JarvisTaskSink {
    val saved: MutableList<HermesTask> = mutableListOf()
    override suspend fun upsert(task: HermesTask): HermesTask {
        saved += task
        return task
    }
}
