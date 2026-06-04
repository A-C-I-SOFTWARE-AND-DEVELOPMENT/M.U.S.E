package com.aci.hermes.data.coding

import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.CodingRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import kotlinx.coroutines.flow.StateFlow
import java.util.UUID

/**
 * Orchestrates the standalone-local coding flow over three layers, with
 * honest degradation at each step:
 *
 *  - **Mock mode** → [MockCodingSource] serves a deterministic demo packet so
 *    the cockpit is fully usable with no backend (the task is marked `demo`).
 *  - **Paired** → the real `coding/{audit,plan,execute}` gateway routes
 *    ([HermesCockpitClient]); the backend owns classification, packet
 *    building, and the owner gate.
 *  - **Unpaired & not mock** → the draft is kept and queued offline; the user
 *    can still copy a Claude Code prompt and sync later. Nothing is fabricated.
 *
 * The owner authorization phrase is passed straight through to the gateway and
 * never stored. Execute is always gated server-side; this layer cannot bypass
 * it.
 */
class CodingRepository(
    private val client: HermesCockpitClient,
    private val store: CodingTaskStore,
    private val paired: () -> Boolean,
    private val mockMode: () -> Boolean,
) {
    val tasks: StateFlow<List<SavedCodingTask>> get() = store.tasks

    fun byId(id: String): SavedCodingTask? = store.byId(id)

    /** The Claude Code prompt for a task (packet-driven when planned). */
    fun promptFor(task: SavedCodingTask): String =
        CodingPromptBuilder.build(task.prompt, task.packet)

    suspend fun createDraft(prompt: String, repoRoot: String, title: String? = null): SavedCodingTask {
        val resolvedTitle = title?.takeIf { it.isNotBlank() } ?: deriveTitle(prompt)
        return store.upsert(
            SavedCodingTask(
                id = UUID.randomUUID().toString(),
                title = resolvedTitle,
                prompt = prompt.trim(),
                repoRoot = repoRoot.trim(),
                state = CodingHandoffState.DRAFT,
                demo = mockMode(),
            ),
        )
    }

    suspend fun runAudit(id: String): CodingActionResult {
        val task = store.byId(id) ?: return CodingActionResult.Failure(null, "Task not found")

        if (mockMode()) {
            val audit = MockCodingSource.audit(task.prompt, task.repoRoot)
            return ok(task.copy(audit = audit, state = CodingHandoffState.AUDITED, demo = true, note = null))
        }
        if (!paired()) return queueOfflineResult(task, "Pair a gateway to classify this task.")

        return when (val r = client.codingAudit(CodingRequest(prompt = task.prompt, repoRoot = task.repoRoot.ifBlank { null }))) {
            is CockpitResult.Success ->
                ok(task.copy(audit = r.value, state = CodingHandoffState.AUDITED, note = null))
            is CockpitResult.Unreachable -> queueOfflineResult(task, r.message)
            is CockpitResult.Failure -> failure(task, r.error.message)
        }
    }

    suspend fun runPlan(id: String): CodingActionResult {
        val task = store.byId(id) ?: return CodingActionResult.Failure(null, "Task not found")

        if (mockMode()) {
            val packet = MockCodingSource.packet(task.prompt, task.repoRoot)
            return ok(
                task.copy(
                    packet = packet,
                    validationOk = true,
                    state = CodingHandoffState.PLANNED,
                    demo = true,
                    note = null,
                ),
            )
        }
        if (!paired()) return queueOfflineResult(task, "Pair a gateway to build a work packet.")

        return when (val r = client.codingPlan(CodingRequest(prompt = task.prompt, repoRoot = task.repoRoot.ifBlank { null }))) {
            is CockpitResult.Success -> {
                val plan = r.value
                val note = if (plan.validation.ok) null else
                    plan.validation.findings.joinToString("; ") { it.message }.ifBlank { "Packet needs attention." }
                ok(
                    task.copy(
                        packet = plan.packet,
                        validationOk = plan.validation.ok,
                        state = CodingHandoffState.PLANNED,
                        note = note,
                    ),
                )
            }
            is CockpitResult.Unreachable -> queueOfflineResult(task, r.message)
            is CockpitResult.Failure -> failure(task, r.error.message)
        }
    }

    /**
     * Dispatch an execute. Without [authorization] (the exact owner phrase) the
     * gateway stages the job and returns `approval_required`; the task lands in
     * [CodingHandoffState.BLOCKED_OWNER] and the UI surfaces the gate.
     */
    suspend fun runExecute(id: String, authorization: String? = null): CodingActionResult {
        val task = store.byId(id) ?: return CodingActionResult.Failure(null, "Task not found")

        if (mockMode()) {
            val demo = MockCodingSource.execute(task.prompt)
            val staged = task.copy(
                state = CodingHandoffState.BLOCKED_OWNER,
                jobId = demo.job?.id,
                demo = true,
                note = demo.authorizationHint,
            )
            return CodingActionResult.OwnerGateRequired(
                store.upsert(staged),
                demo.authorizationHint ?: "Demo owner gate.",
            )
        }
        if (!paired()) return queueOfflineResult(task, "Pair a gateway to dispatch this job.")

        val req = CodingRequest(
            prompt = task.prompt,
            repoRoot = task.repoRoot.ifBlank { null },
            authorization = authorization,
        )
        return when (val r = client.codingExecute(req)) {
            is CockpitResult.Success -> {
                val res = r.value
                when {
                    res.error != null -> failure(task, res.error)
                    res.status.equals("dispatched", ignoreCase = true) ->
                        ok(task.copy(state = CodingHandoffState.EXECUTING, jobId = res.job?.id, note = null))
                    res.authorizationRequired || res.status.equals("approval_required", ignoreCase = true) -> {
                        val staged = store.upsert(
                            task.copy(
                                state = CodingHandoffState.BLOCKED_OWNER,
                                jobId = res.job?.id,
                                note = res.authorizationHint,
                            ),
                        )
                        CodingActionResult.OwnerGateRequired(
                            staged,
                            res.authorizationHint ?: "Requires the owner authorization phrase.",
                        )
                    }
                    else -> ok(task.copy(state = CodingHandoffState.EXECUTING, jobId = res.job?.id, note = res.status))
                }
            }
            is CockpitResult.Unreachable -> queueOfflineResult(task, r.message)
            is CockpitResult.Failure -> failure(task, r.error.message)
        }
    }

    suspend fun markHandedOff(id: String): SavedCodingTask? {
        val task = store.byId(id) ?: return null
        return store.upsert(task.copy(state = CodingHandoffState.HANDED_OFF, note = null))
    }

    suspend fun delete(id: String) = store.delete(id)

    suspend fun deleteAll() = store.deleteAll()

    // ── helpers ──────────────────────────────────────────────────────────

    private suspend fun ok(task: SavedCodingTask): CodingActionResult =
        CodingActionResult.Ok(store.upsert(task))

    private suspend fun failure(task: SavedCodingTask, message: String): CodingActionResult {
        val saved = store.upsert(task.copy(state = CodingHandoffState.ERROR, note = message))
        return CodingActionResult.Failure(saved, message)
    }

    private suspend fun queueOfflineResult(task: SavedCodingTask, message: String): CodingActionResult {
        // Don't downgrade a task that already has a packet — keep its progress,
        // just record that the backend is currently unreachable.
        val nextState = if (task.state == CodingHandoffState.PLANNED ||
            task.state == CodingHandoffState.AUDITED
        ) {
            task.state
        } else {
            CodingHandoffState.QUEUED_OFFLINE
        }
        return CodingActionResult.NeedsPairing(
            store.upsert(task.copy(state = nextState, note = message)),
        )
    }

    private fun deriveTitle(prompt: String): String {
        val firstLine = prompt.trim().lineSequence().firstOrNull()?.trim().orEmpty()
        val title = firstLine.ifBlank { "Coding task" }
        return if (title.length <= 60) title else title.take(57) + "…"
    }
}
