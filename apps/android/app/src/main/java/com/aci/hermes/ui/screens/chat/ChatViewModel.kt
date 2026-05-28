package com.aci.hermes.ui.screens.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.jarvis.JarvisChatChunk
import com.aci.hermes.data.jarvis.JarvisChatGateway
import com.aci.hermes.data.jarvis.JarvisChatMessage
import com.aci.hermes.data.jarvis.JarvisInlineCard
import com.aci.hermes.data.jarvis.JarvisTone
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * Drives the Jarvis Prime Chat surface.
 *
 * The view model is the only thing that talks to a [JarvisChatGateway]; it
 * turns the gateway's [JarvisChatChunk] stream into a stable transcript of
 * [JarvisChatMessage] values the renderer can draw without knowing anything
 * about the wire format. Streaming, abort, and retry are all expressed here
 * so the screen stays declarative.
 *
 * Kept as a plain [ViewModel] (not AndroidViewModel) so it is unit-testable
 * on the JVM with an injected test dispatcher, matching the convention used
 * by MemoryViewModel.
 */
class ChatViewModel(
    private val gateway: JarvisChatGateway,
    private val logBuffer: LogBuffer,
) : ViewModel() {

    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state.asStateFlow()

    private var streamJob: Job? = null
    private var lastPrompt: String? = null

    fun onInputChange(value: String) {
        _state.update { it.copy(input = value) }
    }

    fun onMicToggle() {
        // Speech-to-text is owned by the voice subsystem and not wired into
        // this surface yet. The toggle only flips the visible listening state
        // so the input bar reflects intent; it never fabricates a transcript.
        _state.update { it.copy(isListening = !it.isListening) }
    }

    fun send() {
        val prompt = _state.value.input.trim()
        if (prompt.isEmpty() || _state.value.isStreaming) return
        dispatch(prompt)
    }

    fun retry() {
        val prompt = lastPrompt ?: return
        if (_state.value.isStreaming) return
        // Drop a trailing error bubble before retrying so the transcript reads
        // as a clean re-attempt rather than error-then-answer.
        _state.update { st ->
            val trimmed = st.messages.dropLastWhile { it is JarvisChatMessage.Error }
            st.copy(messages = trimmed)
        }
        stream(prompt)
    }

    fun abort() {
        streamJob?.cancel()
        streamJob = null
        _state.update { st ->
            val messages = st.messages.map { msg ->
                if (msg is JarvisChatMessage.Jarvis && msg.streaming) {
                    msg.copy(streaming = false, aborted = true)
                } else {
                    msg
                }
            }.filterNot { it is JarvisChatMessage.Thinking || it is JarvisChatMessage.Working }
            st.copy(messages = messages, isStreaming = false)
        }
        logBuffer.info(TAG, "Chat stream aborted by user")
    }

    fun consumeSnackbar() {
        _state.update { it.copy(snackbar = null) }
    }

    private fun dispatch(prompt: String) {
        lastPrompt = prompt
        _state.update {
            it.copy(
                messages = it.messages + JarvisChatMessage.User(text = prompt),
                input = "",
                isListening = false,
            )
        }
        stream(prompt)
    }

    private fun stream(prompt: String) {
        val history = _state.value.messages
        val replyId = java.util.UUID.randomUUID().toString()
        _state.update { it.copy(isStreaming = true) }

        streamJob?.cancel()
        streamJob = viewModelScope.launch {
            var started = false
            val body = StringBuilder()
            val detail = StringBuilder()
            var tone = JarvisTone.NORMAL
            val cards = mutableListOf<JarvisInlineCard>()

            // Show the transient "thinking" bubble immediately.
            _state.update { it.copy(messages = it.messages + JarvisChatMessage.Thinking()) }

            fun projectReply(streaming: Boolean) {
                val reply = JarvisChatMessage.Jarvis(
                    id = replyId,
                    body = body.toString(),
                    detail = detail.toString().ifBlank { null },
                    tone = tone,
                    streaming = streaming,
                    inline = cards.toList(),
                )
                _state.update { st ->
                    // Remove transient indicators, then upsert the reply by id.
                    val base = st.messages.filterNot {
                        it is JarvisChatMessage.Thinking || it is JarvisChatMessage.Working
                    }
                    val replaced = base.map { if (it.id == replyId) reply else it }
                    val messages = if (replaced.any { it.id == replyId }) replaced else replaced + reply
                    st.copy(messages = messages)
                }
            }

            gateway.send(history, prompt)
                .catch { t ->
                    emitError(t.message ?: "Gateway error")
                }
                .collect { chunk ->
                    when (chunk) {
                        is JarvisChatChunk.Thinking -> {
                            // Already showing the thinking bubble.
                        }
                        is JarvisChatChunk.Working -> {
                            _state.update { st ->
                                val base = st.messages.filterNot {
                                    it is JarvisChatMessage.Thinking || it is JarvisChatMessage.Working
                                }
                                st.copy(messages = base + JarvisChatMessage.Working(label = chunk.label))
                            }
                        }
                        is JarvisChatChunk.Tone -> {
                            tone = chunk.tone
                            if (started) projectReply(streaming = true)
                        }
                        is JarvisChatChunk.Body -> {
                            started = true
                            body.append(chunk.text)
                            projectReply(streaming = true)
                        }
                        is JarvisChatChunk.Detail -> {
                            started = true
                            detail.append(chunk.text)
                            projectReply(streaming = true)
                        }
                        is JarvisChatChunk.Inline -> {
                            started = true
                            cards.add(chunk.card)
                            projectReply(streaming = true)
                        }
                        is JarvisChatChunk.Done -> {
                            started = true
                            projectReply(streaming = false)
                        }
                        is JarvisChatChunk.Failure -> {
                            emitError(chunk.message, chunk.retryHint)
                        }
                    }
                }

            _state.update { it.copy(isStreaming = false) }
            streamJob = null
            logBuffer.info(TAG, "Chat reply complete via ${gateway.displayName}")
        }
    }

    private fun emitError(message: String, retryHint: String? = null) {
        _state.update { st ->
            val base = st.messages.filterNot {
                it is JarvisChatMessage.Thinking || it is JarvisChatMessage.Working
            }
            st.copy(
                messages = base + JarvisChatMessage.Error(text = message, retryHint = retryHint),
                isStreaming = false,
            )
        }
        logBuffer.warn(TAG, "Chat gateway failure: $message")
    }

    companion object {
        const val TAG = "JarvisChat"
    }
}

data class ChatUiState(
    val messages: List<JarvisChatMessage> = emptyList(),
    val input: String = "",
    val isStreaming: Boolean = false,
    val isListening: Boolean = false,
    val snackbar: String? = null,
)
