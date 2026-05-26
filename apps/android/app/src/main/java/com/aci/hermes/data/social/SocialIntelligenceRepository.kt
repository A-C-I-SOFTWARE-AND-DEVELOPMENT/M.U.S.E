package com.aci.hermes.data.social

import com.aci.hermes.data.model.SocialChannel
import com.aci.hermes.data.model.SocialSignal
import com.aci.hermes.data.redaction.Redactor
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class SocialIntelligenceRepository {

    private val _signals = MutableStateFlow<List<SocialSignal>>(emptyList())
    val signals: StateFlow<List<SocialSignal>> = _signals.asStateFlow()

    fun record(
        subjectName: String,
        channel: SocialChannel,
        summary: String,
        sentiment: Float = 0f,
        source: String = "user",
    ): SocialSignal {
        val token = Redactor.nameToken(subjectName)
        val redacted = Redactor.redact(summary).text
        val signal = SocialSignal(
            subjectToken = token,
            channel = channel,
            summary = redacted,
            sentiment = sentiment.coerceIn(-1f, 1f),
            source = source,
        )
        _signals.value = listOf(signal) + _signals.value
        return signal
    }

    fun clear() { _signals.value = emptyList() }
}
