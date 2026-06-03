package com.aci.hermes.data.memory

import com.aci.hermes.data.cockpit.CockpitContradiction
import com.aci.hermes.data.cockpit.CockpitMemoryNode
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.cockpit.MemoryDecisionRequest
import com.aci.hermes.data.cockpit.ResolveContradictionRequest
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Memory Tree (MEM-2) domain model for the cockpit.
 *
 * Distinct from [MemoryItem] (the flat list/create/delete store): a
 * [MemoryNode] carries layer / approval / contradiction / freshness so the
 * owner can run the proposed-inbox, contradiction, and freshness-review flows
 * on mobile. These are the same provenance-first nodes the live JARVIS loop
 * captures into — nothing here is fabricated.
 */
data class MemoryNode(
    val id: String,
    val namespace: String,
    val layer: String,
    val title: String,
    val summary: String,
    val content: String,
    val sources: List<String>,
    val confidence: Float,
    val trust: String,
    val approvalState: String,
    val contradictionStatus: String,
    val contested: Boolean,
    val supersededBy: String?,
    val freshnessDue: String?,
    val createdAt: String?,
    val tags: List<String>,
) {
    val durableWorthy: Boolean
        get() = namespace in DURABLE_NAMESPACES

    companion object {
        private val DURABLE_NAMESPACES = setOf(
            "jarvis/decisions",
            "jarvis/architecture",
            "jarvis/code_practice",
        )
    }
}

data class MemoryContradiction(
    val id: String,
    val subject: String,
    val reason: String,
    val nodeAId: String,
    val nodeBId: String,
    val status: String,
    val winnerId: String?,
)

fun CockpitMemoryNode.toDomain(): MemoryNode = MemoryNode(
    id = id,
    namespace = namespace,
    layer = layer,
    title = title,
    summary = summary,
    content = content,
    sources = sources,
    confidence = confidence,
    trust = trust,
    approvalState = approvalState,
    contradictionStatus = contradictionStatus,
    contested = contested,
    supersededBy = supersededBy,
    freshnessDue = freshnessDue,
    createdAt = createdAt,
    tags = tags,
)

fun CockpitContradiction.toDomain(): MemoryContradiction = MemoryContradiction(
    id = id,
    subject = subject,
    reason = reason,
    nodeAId = nodeAId,
    nodeBId = nodeBId,
    status = status,
    winnerId = winnerId,
)

/** Sync state of a Memory Tree section against the cockpit gateway. */
sealed interface TreeSync {
    data object Idle : TreeSync
    data object Loading : TreeSync
    data object Unpaired : TreeSync
    data class Loaded(val count: Int) : TreeSync
    data class Error(val message: String) : TreeSync
}

/**
 * Owner-facing Memory Tree operations backed by the cockpit gateway.
 *
 * Read flows ([proposed], [contradictions], [freshness]) refresh from the
 * gateway when paired; unpaired they stay empty and [sync] reports it
 * honestly (no mock data). Owner decisions (approve/reject/supersede/resolve)
 * call the real endpoints — the proposed inbox is the owner gate that turns a
 * captured candidate into durable memory.
 */
class MemoryTreeRepository(
    private val client: HermesCockpitClient,
    private val paired: () -> Boolean = { false },
) {
    private val _proposed = MutableStateFlow<List<MemoryNode>>(emptyList())
    val proposed: StateFlow<List<MemoryNode>> = _proposed.asStateFlow()

    private val _contradictions = MutableStateFlow<List<MemoryContradiction>>(emptyList())
    val contradictions: StateFlow<List<MemoryContradiction>> = _contradictions.asStateFlow()

    private val _freshness = MutableStateFlow<List<MemoryNode>>(emptyList())
    val freshness: StateFlow<List<MemoryNode>> = _freshness.asStateFlow()

    private val _sync = MutableStateFlow<TreeSync>(TreeSync.Idle)
    val sync: StateFlow<TreeSync> = _sync.asStateFlow()

    val isLive: Boolean get() = paired()

    suspend fun refreshProposed() {
        if (!paired()) { _sync.value = TreeSync.Unpaired; return }
        _sync.value = TreeSync.Loading
        when (val res = client.memoryProposed()) {
            is CockpitResult.Success -> {
                _proposed.value = res.value.nodes.map { it.toDomain() }
                _sync.value = TreeSync.Loaded(_proposed.value.size)
            }
            is CockpitResult.Failure -> _sync.value =
                TreeSync.Error("Gateway error ${res.httpStatus}: ${res.error.message}")
            is CockpitResult.Unreachable -> _sync.value = TreeSync.Error(res.message)
        }
    }

    suspend fun refreshContradictions() {
        if (!paired()) { _sync.value = TreeSync.Unpaired; return }
        when (val res = client.memoryContradictions()) {
            is CockpitResult.Success ->
                _contradictions.value = res.value.contradictions.map { it.toDomain() }
            is CockpitResult.Failure -> _sync.value =
                TreeSync.Error("Gateway error ${res.httpStatus}: ${res.error.message}")
            is CockpitResult.Unreachable -> _sync.value = TreeSync.Error(res.message)
        }
    }

    suspend fun refreshFreshness(withinDays: Int = 0) {
        if (!paired()) { _sync.value = TreeSync.Unpaired; return }
        when (val res = client.memoryFreshness(withinDays)) {
            is CockpitResult.Success ->
                _freshness.value = res.value.nodes.map { it.toDomain() }
            is CockpitResult.Failure -> _sync.value =
                TreeSync.Error("Gateway error ${res.httpStatus}: ${res.error.message}")
            is CockpitResult.Unreachable -> _sync.value = TreeSync.Error(res.message)
        }
    }

    /** Approve a proposed node → promote to durable. Returns true on success. */
    suspend fun approve(id: String): DecisionOutcome =
        decide(id, MemoryDecisionRequest(decision = "approve"))

    /** Reject a proposed node (excluded from recall). */
    suspend fun reject(id: String, reason: String? = null): DecisionOutcome =
        decide(id, MemoryDecisionRequest(decision = "reject", note = reason))

    /** Supersede an older node with this one. */
    suspend fun supersede(id: String, supersedesId: String, note: String? = null): DecisionOutcome =
        decide(
            id,
            MemoryDecisionRequest(
                decision = "supersede",
                supersedesId = supersedesId,
                note = note,
            ),
        )

    private suspend fun decide(id: String, req: MemoryDecisionRequest): DecisionOutcome {
        if (!paired()) return DecisionOutcome.Unpaired
        return when (val res = client.memoryDecision(id, req)) {
            is CockpitResult.Success -> {
                refreshProposed()
                val contradiction = res.value.contradiction?.toDomain()
                if (contradiction != null) {
                    refreshContradictions()
                    DecisionOutcome.Conflict(contradiction)
                } else {
                    DecisionOutcome.Ok
                }
            }
            is CockpitResult.Failure -> DecisionOutcome.Error(
                "Gateway error ${res.httpStatus}: ${res.error.message}"
            )
            is CockpitResult.Unreachable -> DecisionOutcome.Error(res.message)
        }
    }

    suspend fun resolveContradiction(
        id: String,
        winnerId: String,
        note: String? = null,
    ): DecisionOutcome {
        if (!paired()) return DecisionOutcome.Unpaired
        return when (
            val res = client.memoryContradictionResolve(
                id,
                ResolveContradictionRequest(winnerId = winnerId, note = note),
            )
        ) {
            is CockpitResult.Success -> {
                refreshContradictions()
                DecisionOutcome.Ok
            }
            is CockpitResult.Failure -> DecisionOutcome.Error(
                "Gateway error ${res.httpStatus}: ${res.error.message}"
            )
            is CockpitResult.Unreachable -> DecisionOutcome.Error(res.message)
        }
    }
}

/** Result of an owner decision — surfaced honestly (incl. conflicts). */
sealed interface DecisionOutcome {
    data object Ok : DecisionOutcome
    data object Unpaired : DecisionOutcome
    /** Approval conflicted with a durable fact — a contradiction was opened. */
    data class Conflict(val contradiction: MemoryContradiction) : DecisionOutcome
    data class Error(val message: String) : DecisionOutcome
}
