package com.aci.hermes.data.cockpit

/**
 * Repository over the cockpit GraphRAG API (`/v1/cockpit/graph/*`): related
 * items for an entity, the three query modes, and an on-demand rebuild —
 * backed by the real knowledge graph through [HermesCockpitClient].
 *
 * There is **no mock seed**: an unpaired or unreachable gateway, or an entity
 * not yet in the graph, yields an empty list, never fabricated relationships.
 */
class CockpitGraphRepository(
    private val client: HermesCockpitClient,
) {
    /** Related files/sources/decisions for a job (the TaskDetail screen). */
    suspend fun relatedForJob(jobId: String): CockpitResult<RelatedItemList> =
        client.graphRelated(jobId = jobId)

    /** Related items for a memory entry (the Memory screen). */
    suspend fun relatedForMemory(memoryId: String): CockpitResult<RelatedItemList> =
        client.graphRelated(memoryId = memoryId)

    /** Related items for an evidence / audit entry (the Audit screen). */
    suspend fun relatedForEvidence(evidenceId: String): CockpitResult<RelatedItemList> =
        client.graphRelated(evidenceId = evidenceId)

    /** Related items for an arbitrary graph node id or key. */
    suspend fun relatedForNode(node: String): CockpitResult<RelatedItemList> =
        client.graphRelated(node = node)

    /** Run a GraphRAG query (mode = local | global | coding). */
    suspend fun query(question: String, mode: String = "coding"): CockpitResult<GraphAnswer> =
        client.graphQuery(question, mode)

    /** Rebuild + persist the knowledge-graph cache. */
    suspend fun build(): CockpitResult<GraphBuildResult> = client.graphBuild()

    fun isPaired(): Boolean = client.isPaired()
}
