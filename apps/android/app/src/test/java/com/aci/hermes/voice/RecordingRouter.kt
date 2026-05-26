package com.aci.hermes.voice

/**
 * In-memory [VoiceCaptureRouter] that records every routing call. Used
 * to assert that vague/serious commands do not auto-execute and that
 * "Send to chat" / "Create task" each hit the right path.
 */
class RecordingRouter(
    var sendResult: VoiceCaptureRouter.RoutingResult =
        VoiceCaptureRouter.RoutingResult.Ok("Sent to chat draft."),
    var createResult: VoiceCaptureRouter.RoutingResult =
        VoiceCaptureRouter.RoutingResult.Ok("Saved as draft task."),
) : VoiceCaptureRouter {

    data class Call(
        val kind: Kind,
        val transcript: String,
        val classification: VoiceCommandClassification,
    )

    enum class Kind { SEND_TO_CHAT, CREATE_TASK }

    val calls: MutableList<Call> = mutableListOf()

    override suspend fun sendToChat(
        transcript: String,
        classification: VoiceCommandClassification,
    ): VoiceCaptureRouter.RoutingResult {
        calls += Call(Kind.SEND_TO_CHAT, transcript, classification)
        return sendResult
    }

    override suspend fun createTask(
        transcript: String,
        classification: VoiceCommandClassification,
    ): VoiceCaptureRouter.RoutingResult {
        calls += Call(Kind.CREATE_TASK, transcript, classification)
        return createResult
    }

    fun reset() {
        calls.clear()
    }
}
