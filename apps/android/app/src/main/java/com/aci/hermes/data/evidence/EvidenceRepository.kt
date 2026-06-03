package com.aci.hermes.data.evidence

import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.EvidenceVerifyRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Sync state of the evidence base against the cockpit gateway. */
sealed interface EvidenceSync {
    data object Idle : EvidenceSync
    data object Loading : EvidenceSync
    /** No gateway paired — items are the local seed, not live. */
    data object MockOnly : EvidenceSync
    data class Loaded(val count: Int) : EvidenceSync
    /** Paired but the gateway couldn't serve the request — honest, no fake data. */
    data class Error(val message: String) : EvidenceSync
}

/**
 * Store of [EvidenceItem]s backed by the cockpit Evidence Engine when paired.
 *
 * - **Paired**: [refresh]/[search] pull real artifacts via
 *   `GET /v1/cockpit/evidence`; [verify] and [promote] hit the engine;
 *   [demote] removes an artifact. No mock data is shown to a paired user.
 * - **Unpaired / preview / tests**: falls back to [seed].
 *
 * Mirrors `MemoryRepository`: a paired gateway error leaves items as-is and
 * records the error in [sync] — never replaced with stub data.
 */
class EvidenceRepository(
    seed: List<EvidenceItem> = MockEvidenceSeed.items,
    private val client: HermesCockpitClient? = null,
    private val paired: () -> Boolean = { false },
) {
    private val _items: MutableStateFlow<List<EvidenceItem>> = MutableStateFlow(seed)
    val items: StateFlow<List<EvidenceItem>> = _items.asStateFlow()

    private val _hits: MutableStateFlow<List<EvidenceHit>> = MutableStateFlow(emptyList())
    val hits: StateFlow<List<EvidenceHit>> = _hits.asStateFlow()

    private val _sync: MutableStateFlow<EvidenceSync> = MutableStateFlow(EvidenceSync.Idle)
    val sync: StateFlow<EvidenceSync> = _sync.asStateFlow()

    val isLive: Boolean get() = client != null && paired()

    /** Pull the full evidence list (no query). */
    suspend fun refresh() = load(query = null)

    /** Run server-side hybrid retrieval; ranked [hits] populate alongside [items]. */
    suspend fun search(query: String) = load(query = query.takeIf { it.isNotBlank() })

    private suspend fun load(query: String?) {
        val c = client
        if (c == null || !paired()) {
            _sync.value = EvidenceSync.MockOnly
            return
        }
        _sync.value = EvidenceSync.Loading
        when (val res = c.evidenceList(query)) {
            is CockpitResult.Success -> {
                if (res.value.items.isNotEmpty() || query == null) {
                    _items.value = res.value.items.map { it.toDomain() }
                }
                _hits.value = res.value.hits.map { it.toDomain() }
                _sync.value = EvidenceSync.Loaded(_items.value.size)
            }
            is CockpitResult.Failure ->
                _sync.value = EvidenceSync.Error("Gateway error ${res.httpStatus}: ${res.error.message}")
            is CockpitResult.Unreachable ->
                _sync.value = EvidenceSync.Error(res.message)
        }
    }

    fun byId(id: String): EvidenceItem? = _items.value.firstOrNull { it.id == id }

    /** Verify claims against the evidence base. Returns null on a gateway error. */
    suspend fun verify(claims: List<String>, query: String? = null): EvidenceVerification? {
        val c = client ?: return null
        if (!paired()) return null
        return when (val res = c.evidenceVerify(EvidenceVerifyRequest(claims, query))) {
            is CockpitResult.Success -> res.value.toDomain()
            is CockpitResult.Failure -> {
                _sync.value = EvidenceSync.Error("Verify failed ${res.httpStatus}: ${res.error.message}")
                null
            }
            is CockpitResult.Unreachable -> {
                _sync.value = EvidenceSync.Error(res.message)
                null
            }
        }
    }

    /**
     * Promote an artifact to durable memory. [authorization] is the owner
     * phrase required for low-confidence/unverified promotions; the gateway
     * returns the honest rejection reasons when it is missing.
     */
    suspend fun promote(id: String, authorization: String? = null): PromoteOutcome {
        val c = client ?: return PromoteOutcome.NotLive
        if (!paired()) return PromoteOutcome.NotLive
        return when (val res = c.evidencePromote(id, authorization)) {
            is CockpitResult.Success ->
                if (res.value.promoted) PromoteOutcome.Promoted(res.value.nodeId)
                else PromoteOutcome.Rejected(res.value.reasons, res.value.hint)
            is CockpitResult.Failure ->
                PromoteOutcome.Rejected(
                    res.error.details?.values?.toList() ?: listOf(res.error.message),
                    null,
                )
            is CockpitResult.Unreachable -> PromoteOutcome.Unreachable(res.message)
        }
    }

    suspend fun demote(id: String): Boolean {
        val c = client ?: return false
        if (!paired()) return false
        return when (val res = c.evidenceDemote(id)) {
            is CockpitResult.Success -> {
                _items.value = _items.value.filterNot { it.id == id }
                true
            }
            is CockpitResult.Failure -> {
                _sync.value = EvidenceSync.Error("Demote rejected by gateway")
                false
            }
            is CockpitResult.Unreachable -> {
                _sync.value = EvidenceSync.Error(res.message)
                false
            }
        }
    }
}

/** Outcome of a promote-to-memory attempt — honest about owner-gate rejection. */
sealed interface PromoteOutcome {
    data class Promoted(val nodeId: String?) : PromoteOutcome
    data class Rejected(val reasons: List<String>, val hint: String?) : PromoteOutcome
    data class Unreachable(val message: String) : PromoteOutcome
    data object NotLive : PromoteOutcome
}

/**
 * Seed data the Evidence screen renders while unpaired. Crafted to exercise
 * the trust ladder (a primary doc, a community blog) and a contradiction.
 */
object MockEvidenceSeed {
    private const val DAY = 86_400_000L
    private val now = System.currentTimeMillis()

    val items: List<EvidenceItem> = listOf(
        EvidenceItem(
            id = "vllm-batching",
            title = "vLLM continuous batching",
            sourceUri = "https://docs.vllm.ai/serving",
            sourceType = "official_doc",
            trust = EvidenceTrust.PRIMARY,
            evidenceStrength = "primary",
            excerpt = "vLLM uses continuous batching to improve serving throughput.",
            summary = "Continuous batching raises GPU utilisation under concurrent load.",
            tags = listOf("vllm", "serving"),
            retrievedAt = now - 3 * DAY,
            freshnessDue = now + 60 * DAY,
            checksum = "seed",
            citationAnchors = listOf("serving.md:12"),
            addedAt = now - 3 * DAY,
        ),
        EvidenceItem(
            id = "owasp-llm",
            title = "OWASP LLM Top 10 — prompt injection",
            sourceUri = "https://owasp.org/llm-top-10",
            sourceType = "official_doc",
            trust = EvidenceTrust.OFFICIAL_DOC,
            evidenceStrength = "strong",
            excerpt = "Prompt injection is the top risk for LLM applications.",
            summary = "Treat untrusted text as data, never instructions.",
            tags = listOf("security", "llm"),
            retrievedAt = now - 10 * DAY,
            freshnessDue = now - DAY, // stale on purpose to exercise the label
            checksum = "seed",
            addedAt = now - 10 * DAY,
        ),
        EvidenceItem(
            id = "blog-batching",
            title = "Community blog on batching",
            sourceUri = "https://blog.example/batching",
            sourceType = "blog",
            trust = EvidenceTrust.COMMUNITY,
            evidenceStrength = "weak",
            excerpt = "A blog claims batching does not help small models.",
            summary = "Anecdotal; conflicts with the vLLM docs.",
            tags = listOf("vllm"),
            retrievedAt = now - DAY,
            checksum = "seed",
            addedAt = now - DAY,
        ),
    )
}
