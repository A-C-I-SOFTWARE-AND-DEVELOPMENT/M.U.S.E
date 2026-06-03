package com.aci.hermes.ui.screens.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.jarvis.JarvisApprovalGateway
import com.aci.hermes.data.jarvis.JarvisApprovalResult
import com.aci.hermes.data.jarvis.JarvisChatChunk
import com.aci.hermes.data.jarvis.JarvisChatGateway
import com.aci.hermes.data.jarvis.JarvisChatMessage
import com.aci.hermes.data.jarvis.JarvisClipboard
import com.aci.hermes.data.jarvis.JarvisDispatchResult
import com.aci.hermes.data.jarvis.JarvisInlineCard
import com.aci.hermes.data.jarvis.JarvisJobDispatcher
import com.aci.hermes.data.jarvis.JarvisRecordInspector
import com.aci.hermes.data.jarvis.JarvisRecordRef
import com.aci.hermes.data.jarvis.JarvisRecordView
import com.aci.hermes.data.jarvis.JarvisTaskSink
import com.aci.hermes.data.jarvis.JarvisToolCall
import com.aci.hermes.data.jarvis.MockJarvisChatGateway
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class JarvisChatUiState(
    val messages: List<JarvisChatMessage> = emptyList(),
    val draft: String = "",
    val responding: Boolean = false,
    val expanded: Set<String> = emptySet(),
    val ackedCritical: Set<String> = emptySet(),
    val approved: Set<String> = emptySet(),
    val held: Set<String> = emptySet(),
    val promotedTasks: Set<String> = emptySet(),
    val gatewayLabel: String = "",
    val mockMode: Boolean = true,
    val voiceCapturing: Boolean = false,
    val snackbar: String? = null,
    // Tool-visibility surfaces:
    val expandedTools: Set<String> = emptySet(),
    val recordSheet: JarvisRecordView? = null,
    val recordLoading: Boolean = false,
)

/**
 * Drives the Jarvis Prime chat surface (the "Chat" shell tab).
 *
 * Responsibilities:
 *  - own the chat transcript (user + jarvis + indicators + errors)
 *  - dispatch a single in-flight send at a time
 *  - translate streamed [JarvisChatChunk]s into transcript edits
 *  - support stop/abort by cancelling the streaming job
 *  - support retry by resending the last user prompt
 *  - bridge inline cards into the orchestrator (Task promotion via
 *    [JarvisTaskSink]; Approval / Critical decisions stay local to the
 *    chat state until a real gateway transport lands)
 *
 * Kept as a plain [ViewModel] (no Application) so it unit-tests without
 * a Context — the clipboard and task store are injected as narrow
 * interfaces.
 */
class JarvisChatViewModel(
    private val gateway: JarvisChatGateway,
    private val taskSink: JarvisTaskSink,
    private val logBuffer: LogBuffer,
    private val clipboard: JarvisClipboard,
    // Live cockpit ports (no-op defaults keep offline/mock + unit tests
    // working without a Context or network):
    private val jobDispatcher: JarvisJobDispatcher = JarvisJobDispatcher.Unavailable,
    private val approvalGateway: JarvisApprovalGateway = JarvisApprovalGateway.Unavailable,
    private val recordInspector: JarvisRecordInspector = JarvisRecordInspector.Unavailable,
) : ViewModel() {

    private val _state = MutableStateFlow(
        JarvisChatUiState(
            messages = listOf(welcomeMessage()),
            gatewayLabel = gateway.displayName,
            mockMode = gateway is MockJarvisChatGateway,
        ),
    )
    val state: StateFlow<JarvisChatUiState> = _state.asStateFlow()

    private var activeJob: Job? = null
    private var lastUserPrompt: String? = null

    fun onDraftChange(value: String) {
        _state.update { it.copy(draft = value) }
    }

    fun onVoiceCaptureStart() {
        _state.update { it.copy(voiceCapturing = true) }
    }

    fun onVoiceCaptureResult(text: String) {
        val merged = listOf(_state.value.draft, text)
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .joinToString(" ")
        _state.update { it.copy(draft = merged, voiceCapturing = false) }
    }

    fun onVoiceCaptureCancel() {
        _state.update { it.copy(voiceCapturing = false) }
    }

    fun send() {
        val text = _state.value.draft.trim()
        if (text.isEmpty() || _state.value.responding) return
        lastUserPrompt = text
        val userMsg = JarvisChatMessage.User(text = text)
        _state.update {
            it.copy(
                messages = it.messages + userMsg,
                draft = "",
                responding = true,
            )
        }
        startStreaming(text)
    }

    fun retry() {
        val prompt = lastUserPrompt ?: return
        if (_state.value.responding) return
        // Drop trailing error so the resumed stream replaces it cleanly.
        _state.update { it.copy(messages = it.messages.dropLastWhile { m -> m is JarvisChatMessage.Error }) }
        _state.update { it.copy(responding = true) }
        startStreaming(prompt)
    }

    fun stop() {
        val job = activeJob ?: return
        if (!job.isActive) return
        job.cancel(CancellationException("user_stop"))
        logBuffer.info(TAG, "Streaming cancelled by user")
    }

    /**
     * Ask Jarvis to keep going from where the last reply left off. Sends a
     * lightweight "continue" directive through the same streaming path so
     * the transport, gating, and routing are identical to a normal turn —
     * the prior transcript (already in history) is the context.
     */
    fun continueReply() {
        if (_state.value.responding) return
        if (_state.value.messages.none { it is JarvisChatMessage.Jarvis }) return
        _state.update { it.copy(responding = true) }
        startStreaming(CONTINUE_DIRECTIVE)
    }

    fun toggleExpanded(messageId: String) {
        _state.update {
            val next = it.expanded.toMutableSet().apply {
                if (!add(messageId)) remove(messageId)
            }
            it.copy(expanded = next)
        }
    }

    fun toggleToolExpanded(toolId: String) {
        _state.update {
            val next = it.expandedTools.toMutableSet().apply {
                if (!add(toolId)) remove(toolId)
            }
            it.copy(expandedTools = next)
        }
    }

    /**
     * Resolve an evidence/ledger reference into a readable view and surface
     * it in the bottom sheet. No-op (with an honest snackbar) when no live
     * backend is paired — refs only ever appear from the real gateway.
     */
    fun inspectRecord(ref: JarvisRecordRef) {
        if (!recordInspector.available) {
            _state.update { it.copy(snackbar = "Pair a gateway to inspect records.") }
            return
        }
        _state.update { it.copy(recordLoading = true) }
        viewModelScope.launch {
            val view = runCatching { recordInspector.load(ref) }.getOrNull()
            _state.update {
                if (view == null) it.copy(recordLoading = false, snackbar = "Couldn't load that record.")
                else it.copy(recordLoading = false, recordSheet = view)
            }
        }
    }

    fun dismissRecord() {
        _state.update { it.copy(recordSheet = null) }
    }

    fun copyMessage(messageId: String) {
        val msg = _state.value.messages.firstOrNull { it.id == messageId } ?: return
        val text = when (msg) {
            is JarvisChatMessage.User -> msg.text
            is JarvisChatMessage.Jarvis -> buildString {
                append(msg.body)
                msg.detail?.let { append("\n\n").append(it) }
            }
            is JarvisChatMessage.Error -> msg.text
            is JarvisChatMessage.Thinking, is JarvisChatMessage.Working -> return
        }
        val ok = clipboard.copy("Jarvis Prime", text)
        _state.update {
            it.copy(snackbar = if (ok) "Copied" else "Could not access clipboard")
        }
    }

    fun promoteInlineTask(messageId: String, card: JarvisInlineCard.Task) {
        val key = inlineKey(messageId, card)
        if (key in _state.value.promotedTasks) return
        viewModelScope.launch {
            val task = HermesTask(
                title = card.title,
                description = card.summary,
                targetTool = card.targetTool,
                taskType = card.taskType,
                status = TaskStatus.DRAFT,
                promptBody = card.summary,
            )
            taskSink.upsert(task)
            logBuffer.info(TAG, "Promoted inline task ${task.id}")
            _state.update {
                it.copy(
                    promotedTasks = it.promotedTasks + key,
                    snackbar = "Task added to orchestrator",
                )
            }
        }
    }

    /**
     * Promote any Jarvis reply into a job. Dispatches to the live cockpit
     * job queue when a backend is paired ([jobDispatcher] available); falls
     * back to a local DRAFT task in the orchestrator otherwise. Worker
     * routing reuses [JarvisIntentClassifier] so the mapping matches the
     * rest of the app.
     */
    fun createJob(messageId: String) {
        val msg = _state.value.messages.firstOrNull { it.id == messageId } as? JarvisChatMessage.Jarvis
            ?: return
        val prompt = lastUserPrompt?.takeIf { it.isNotBlank() } ?: msg.body
        val title = deriveJobTitle(msg.body, prompt)
        val target = com.aci.hermes.data.jarvis.JarvisIntentClassifier.inferTargetTool(prompt)
        val type = com.aci.hermes.data.jarvis.JarvisIntentClassifier.inferTaskType(prompt)
        viewModelScope.launch {
            if (jobDispatcher.available) {
                when (val result = jobDispatcher.dispatch(title, prompt, target)) {
                    is JarvisDispatchResult.Ok ->
                        _state.update { it.copy(snackbar = "Job dispatched (${result.jobId})") }
                    is JarvisDispatchResult.Failed ->
                        _state.update { it.copy(snackbar = "Couldn't dispatch job: ${result.message}") }
                    JarvisDispatchResult.Unavailable ->
                        dispatchLocalDraft(title, prompt, target, type)
                }
            } else {
                dispatchLocalDraft(title, prompt, target, type)
            }
        }
    }

    private suspend fun dispatchLocalDraft(
        title: String,
        prompt: String,
        target: TargetTool,
        type: com.aci.hermes.data.model.TaskType,
    ) {
        val task = HermesTask(
            title = title,
            description = prompt,
            targetTool = target,
            taskType = type,
            status = TaskStatus.DRAFT,
            promptBody = prompt,
        )
        taskSink.upsert(task)
        logBuffer.info(TAG, "Created local draft job ${task.id}")
        _state.update { it.copy(snackbar = "Draft job added to orchestrator") }
    }

    private fun deriveJobTitle(body: String, prompt: String): String {
        val source = body.lineSequence().firstOrNull { it.isNotBlank() }?.trim()
            ?: prompt.lineSequence().firstOrNull()?.trim()
            ?: "Jarvis job"
        return if (source.length <= 60) source else source.take(57).trimEnd() + "…"
    }

    fun approveInline(messageId: String, card: JarvisInlineCard.Approval) {
        val key = inlineKey(messageId, card)
        // Optimistically flip local state so the card reflects the owner's
        // decision immediately. When the card is backed by a real cockpit
        // approval and a backend is paired, also submit the owner phrase to
        // the gateway (which still enforces it server-side).
        _state.update {
            it.copy(
                approved = it.approved + key,
                held = it.held - key,
                snackbar = "${card.title} — approved",
            )
        }
        logBuffer.info(TAG, "Approval card accepted on $messageId")

        val approvalId = card.approvalId
        if (approvalId != null && approvalGateway.available) {
            viewModelScope.launch {
                when (val result = approvalGateway.approve(approvalId)) {
                    is JarvisApprovalResult.Accepted ->
                        _state.update { it.copy(snackbar = "${card.title} — approved on gateway") }
                    is JarvisApprovalResult.Rejected -> {
                        // Roll the local flip back so the UI stays honest.
                        _state.update {
                            it.copy(
                                approved = it.approved - key,
                                snackbar = "Gateway declined: ${result.message}",
                            )
                        }
                        logBuffer.warn(TAG, "Gateway approval failed: ${result.message}")
                    }
                    JarvisApprovalResult.Unavailable -> Unit // local-only, already reflected
                }
            }
        }
    }

    fun holdInline(messageId: String, card: JarvisInlineCard.Approval) {
        val key = inlineKey(messageId, card)
        _state.update {
            it.copy(
                held = it.held + key,
                approved = it.approved - key,
                snackbar = "${card.title} — held",
            )
        }
        logBuffer.info(TAG, "Approval card held on $messageId")
    }

    fun ackCritical(messageId: String, card: JarvisInlineCard.Critical, typed: String) {
        if (typed.trim() != card.requiredAck) {
            _state.update { it.copy(snackbar = "Ack string didn't match.") }
            return
        }
        val key = inlineKey(messageId, card)
        _state.update {
            it.copy(
                ackedCritical = it.ackedCritical + key,
                snackbar = "${card.title} — acknowledged",
            )
        }
        logBuffer.info(TAG, "Critical ack received on $messageId")
    }

    fun consumeSnackbar() {
        _state.update { it.copy(snackbar = null) }
    }

    fun clearTranscript() {
        if (_state.value.responding) stop()
        _state.update {
            JarvisChatUiState(
                messages = listOf(welcomeMessage()),
                gatewayLabel = gateway.displayName,
                mockMode = it.mockMode,
            )
        }
    }

    private fun startStreaming(prompt: String) {
        activeJob?.cancel()
        val historySnapshot = _state.value.messages
        val replyId = java.util.UUID.randomUUID().toString()
        val indicator = JarvisChatMessage.Thinking()
        _state.update { it.copy(messages = it.messages + indicator) }

        activeJob = viewModelScope.launch {
            var indicatorId: String = indicator.id
            var firstChunkSeen = false
            try {
                gateway.send(historySnapshot, prompt)
                    .catch { e ->
                        if (e is CancellationException) throw e
                        emitFailure(indicatorId, e.message)
                    }
                    .collect { chunk ->
                        when (chunk) {
                            is JarvisChatChunk.Thinking -> {
                                // Indicator already in place; ignore duplicate.
                            }

                            is JarvisChatChunk.Working -> {
                                // Working only swaps the indicator. Once a reply
                                // has started (firstChunkSeen) we silently drop
                                // late Working chunks — they'd otherwise stomp
                                // the in-flight reply.
                                if (!firstChunkSeen) {
                                    indicatorId = replaceIndicator(
                                        indicatorId,
                                        JarvisChatMessage.Working(label = chunk.label),
                                    )
                                }
                            }

                            is JarvisChatChunk.Tone -> {
                                if (!firstChunkSeen) {
                                    indicatorId = promoteToReply(indicatorId, replyId)
                                    firstChunkSeen = true
                                }
                                updateReply(replyId) { it.copy(tone = chunk.tone) }
                            }

                            is JarvisChatChunk.Body -> {
                                if (!firstChunkSeen) {
                                    indicatorId = promoteToReply(indicatorId, replyId)
                                    firstChunkSeen = true
                                }
                                updateReply(replyId) { it.copy(body = it.body + chunk.text) }
                            }

                            is JarvisChatChunk.Detail -> {
                                if (!firstChunkSeen) {
                                    indicatorId = promoteToReply(indicatorId, replyId)
                                    firstChunkSeen = true
                                }
                                updateReply(replyId) {
                                    val merged = (it.detail ?: "") + chunk.text
                                    it.copy(detail = merged)
                                }
                            }

                            is JarvisChatChunk.Inline -> {
                                if (!firstChunkSeen) {
                                    indicatorId = promoteToReply(indicatorId, replyId)
                                    firstChunkSeen = true
                                }
                                updateReply(replyId) { it.copy(inline = it.inline + chunk.card) }
                            }

                            is JarvisChatChunk.Phase -> {
                                if (!firstChunkSeen) {
                                    indicatorId = promoteToReply(indicatorId, replyId)
                                    firstChunkSeen = true
                                }
                                updateReply(replyId) {
                                    // Append only on transition so the rail reads as a
                                    // sequence, not a repeated label.
                                    if (it.phases.lastOrNull() == chunk.phase) it
                                    else it.copy(phases = it.phases + chunk.phase)
                                }
                            }

                            is JarvisChatChunk.ToolCall -> {
                                if (!firstChunkSeen) {
                                    indicatorId = promoteToReply(indicatorId, replyId)
                                    firstChunkSeen = true
                                }
                                updateReply(replyId) { it.copy(toolCalls = upsertTool(it.toolCalls, chunk)) }
                            }

                            is JarvisChatChunk.EvidenceRef -> {
                                if (!firstChunkSeen) {
                                    indicatorId = promoteToReply(indicatorId, replyId)
                                    firstChunkSeen = true
                                }
                                updateReply(replyId) {
                                    it.copy(records = it.records + JarvisRecordRef(chunk.auditId, chunk.title, JarvisRecordRef.Kind.EVIDENCE))
                                }
                            }

                            is JarvisChatChunk.LedgerRef -> {
                                if (!firstChunkSeen) {
                                    indicatorId = promoteToReply(indicatorId, replyId)
                                    firstChunkSeen = true
                                }
                                updateReply(replyId) {
                                    it.copy(records = it.records + JarvisRecordRef(chunk.ledgerId, chunk.title, JarvisRecordRef.Kind.LEDGER))
                                }
                            }

                            is JarvisChatChunk.Failure -> {
                                emitFailure(indicatorId, chunk.message, chunk.retryHint)
                            }

                            is JarvisChatChunk.Done -> {
                                if (!firstChunkSeen) {
                                    // Gateway returned Done with no body — show
                                    // an empty bubble rather than dangling indicator.
                                    indicatorId = promoteToReply(indicatorId, replyId)
                                    firstChunkSeen = true
                                    updateReply(replyId) { it.copy(body = "(no reply)") }
                                }
                                updateReply(replyId) { it.copy(streaming = false) }
                            }
                        }
                    }
            } catch (ce: CancellationException) {
                if (firstChunkSeen) {
                    updateReply(replyId) { it.copy(streaming = false, aborted = true) }
                } else {
                    removeMessage(indicatorId)
                }
                logBuffer.info(TAG, "Stream cancelled: ${ce.message}")
            } finally {
                _state.update { it.copy(responding = false) }
            }
        }
    }

    private fun promoteToReply(indicatorId: String, replyId: String): String {
        val placeholder = JarvisChatMessage.Jarvis(
            id = replyId,
            body = "",
            streaming = true,
        )
        _state.update { st ->
            val next = st.messages.map { if (it.id == indicatorId) placeholder else it }
            st.copy(messages = next)
        }
        return replyId
    }

    private fun replaceIndicator(currentId: String, replacement: JarvisChatMessage): String {
        _state.update { st ->
            val next = st.messages.map { if (it.id == currentId) replacement else it }
            st.copy(messages = next)
        }
        return replacement.id
    }

    private inline fun updateReply(replyId: String, transform: (JarvisChatMessage.Jarvis) -> JarvisChatMessage.Jarvis) {
        _state.update { st ->
            val next = st.messages.map {
                if (it is JarvisChatMessage.Jarvis && it.id == replyId) transform(it) else it
            }
            st.copy(messages = next)
        }
    }

    private fun removeMessage(id: String) {
        _state.update { st -> st.copy(messages = st.messages.filterNot { it.id == id }) }
    }

    /**
     * Fold a streamed [JarvisChatChunk.ToolCall] into the reply's tool list.
     * The same call id arrives twice (START then a terminal OK/FAIL); the
     * terminal update replaces the START entry in place rather than adding a
     * duplicate, so the chip animates instead of stacking.
     */
    private fun upsertTool(
        existing: List<JarvisToolCall>,
        chunk: JarvisChatChunk.ToolCall,
    ): List<JarvisToolCall> {
        val folded = JarvisToolCall(
            id = chunk.id,
            name = chunk.name,
            summary = chunk.summary,
            status = chunk.status,
            detail = chunk.detail,
        )
        val idx = existing.indexOfFirst { it.id == chunk.id }
        return if (idx < 0) existing + folded
        else existing.toMutableList().apply {
            // Keep a detail that arrived earlier if the terminal chunk omits it.
            this[idx] = folded.copy(detail = folded.detail ?: this[idx].detail)
        }
    }

    private fun emitFailure(indicatorId: String, message: String?, retryHint: String? = null) {
        val err = JarvisChatMessage.Error(
            text = message ?: "Gateway error",
            retryHint = retryHint ?: "Tap retry to resend the last message.",
        )
        _state.update { st ->
            val withoutIndicator = st.messages.filterNot { it.id == indicatorId }
            st.copy(messages = withoutIndicator + err)
        }
        logBuffer.info(TAG, "Gateway error surfaced: ${err.text}")
    }

    private fun inlineKey(messageId: String, card: JarvisInlineCard): String =
        "$messageId/${card::class.simpleName}/${cardSummary(card)}"

    private fun cardSummary(card: JarvisInlineCard): String = when (card) {
        is JarvisInlineCard.Task -> card.title
        is JarvisInlineCard.Approval -> card.title
        is JarvisInlineCard.Serious -> card.title
        is JarvisInlineCard.Critical -> card.title
    }

    private fun welcomeMessage(): JarvisChatMessage.Jarvis = JarvisChatMessage.Jarvis(
        body = "Jarvis Prime here. Short replies on phone — ask for detail when you want the deep cut.",
        detail = null,
    )

    companion object {
        private const val TAG = "JarvisChat"

        /** Sent by [continueReply] — the gateway treats it as "keep going". */
        const val CONTINUE_DIRECTIVE = "continue"
    }
}
