package com.aci.hermes.data.memory

import kotlinx.serialization.Serializable

/**
 * Immutable snapshot of the Jarvis Prime Memory Tree.
 *
 * Operations return a new [MemoryTree] rather than mutating in place so
 * StateFlow consumers can compare by reference. The tree is stored as a
 * flat map of nodes keyed by id; the parent/child relationship is
 * derived by [childrenOf] and [rootNodes].
 */
@Serializable
data class MemoryTree(
    val nodes: Map<String, MemoryNode> = emptyMap(),
) {
    val size: Int get() = nodes.size

    fun get(id: String): MemoryNode? = nodes[id]

    fun rootNodes(): List<MemoryNode> =
        nodes.values.filter { it.parentId == null }.sortedDescending()

    fun childrenOf(parentId: String): List<MemoryNode> =
        nodes.values.filter { it.parentId == parentId }.sortedDescending()

    /** Returns the path from the root to [id], inclusive. */
    fun pathTo(id: String): List<MemoryNode> {
        val out = ArrayDeque<MemoryNode>()
        var cursor: MemoryNode? = nodes[id]
        val seen = mutableSetOf<String>()
        while (cursor != null && cursor.id !in seen) {
            seen += cursor.id
            out.addFirst(cursor)
            cursor = cursor.parentId?.let(nodes::get)
        }
        return out.toList()
    }

    fun search(query: String): List<MemoryNode> {
        if (query.isBlank()) return emptyList()
        val needle = query.trim().lowercase()
        return nodes.values.filter {
            it.topic.lowercase().contains(needle) ||
                it.body.lowercase().contains(needle) ||
                it.tags.any { t -> t.lowercase().contains(needle) }
        }.sortedByDescending { it.updatedAt }
    }

    fun byTag(tag: String): List<MemoryNode> {
        val needle = tag.trim().lowercase()
        return nodes.values.filter { it.tags.any { t -> t.lowercase() == needle } }
            .sortedByDescending { it.updatedAt }
    }

    fun upsert(node: MemoryNode): MemoryTree {
        if (node.parentId != null && node.parentId !in nodes) {
            throw IllegalArgumentException("parent ${node.parentId} not found")
        }
        return copy(nodes = nodes + (node.id to node.copy(updatedAt = System.currentTimeMillis())))
    }

    /**
     * Remove a node and every descendant. Pinned descendants are
     * preserved (re-parented to the removed node's parent, or promoted
     * to root if there is none) so the owner cannot accidentally
     * forget a memory they marked important.
     */
    fun forget(id: String): MemoryTree {
        val target = nodes[id] ?: return this
        val (toRemove, toPromote) = collectSubtree(id).partition { !it.pinned || it.id == id }
        val promoted = toPromote.map { it.copy(parentId = target.parentId) }
        val keep = nodes.filterKeys { it !in toRemove.map(MemoryNode::id).toSet() }
        return copy(nodes = keep + promoted.associateBy { it.id })
    }

    private fun collectSubtree(rootId: String): List<MemoryNode> {
        val out = mutableListOf<MemoryNode>()
        val queue = ArrayDeque<String>().apply { add(rootId) }
        while (queue.isNotEmpty()) {
            val cur = queue.removeFirst()
            val node = nodes[cur] ?: continue
            out += node
            queue += nodes.values.filter { it.parentId == cur }.map(MemoryNode::id)
        }
        return out
    }

    private fun List<MemoryNode>.sortedDescending(): List<MemoryNode> =
        sortedByDescending { it.updatedAt }
}
