package com.aci.hermes.attention

enum class AttentionState {
    Looking,
    Away,
    Talking,
    Unknown,
}

data class AttentionSample(
    val state: AttentionState,
    val confidence: Float,
    val timestampMillis: Long,
)
