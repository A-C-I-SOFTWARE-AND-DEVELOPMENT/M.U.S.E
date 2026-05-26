package com.aci.hermes.data.memory

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MemoryTreeTest {

    @Test fun upsert_inserts_root_node() {
        val tree = MemoryTree().upsert(MemoryNode(topic = "Owner"))
        assertEquals(1, tree.size)
        assertEquals(1, tree.rootNodes().size)
    }

    @Test fun upsert_under_unknown_parent_fails() {
        val ex = runCatching {
            MemoryTree().upsert(MemoryNode(topic = "child", parentId = "missing"))
        }.exceptionOrNull()
        assertTrue(ex is IllegalArgumentException)
    }

    @Test fun children_only_lists_direct_descendants() {
        val root = MemoryNode(topic = "Owner")
        val child = MemoryNode(topic = "Coffee", parentId = root.id)
        val grandchild = MemoryNode(topic = "Brand", parentId = child.id)
        val tree = MemoryTree().upsert(root).upsert(child).upsert(grandchild)
        assertEquals(listOf(child.id), tree.childrenOf(root.id).map(MemoryNode::id))
    }

    @Test fun path_walks_back_to_root() {
        val root = MemoryNode(topic = "Owner")
        val mid = MemoryNode(topic = "Habits", parentId = root.id)
        val leaf = MemoryNode(topic = "Morning", parentId = mid.id)
        val tree = MemoryTree().upsert(root).upsert(mid).upsert(leaf)
        val path = tree.pathTo(leaf.id)
        assertEquals(listOf(root.id, mid.id, leaf.id), path.map(MemoryNode::id))
    }

    @Test fun forget_removes_subtree() {
        val root = MemoryNode(topic = "Owner")
        val mid = MemoryNode(topic = "Habits", parentId = root.id)
        val leaf = MemoryNode(topic = "Morning", parentId = mid.id)
        val tree = MemoryTree().upsert(root).upsert(mid).upsert(leaf)
        val after = tree.forget(mid.id)
        assertEquals(1, after.size)
        assertNotNull(after.get(root.id))
        assertNull(after.get(mid.id))
        assertNull(after.get(leaf.id))
    }

    @Test fun forget_preserves_pinned_descendants_by_promoting_them() {
        val root = MemoryNode(topic = "Owner")
        val mid = MemoryNode(topic = "Habits", parentId = root.id)
        val pinnedLeaf = MemoryNode(topic = "Critical reminder", parentId = mid.id, pinned = true)
        val tree = MemoryTree().upsert(root).upsert(mid).upsert(pinnedLeaf)
        val after = tree.forget(mid.id)
        val promoted = after.get(pinnedLeaf.id)
        assertNotNull("pinned leaf must survive its parent being forgotten", promoted)
        assertEquals(root.id, promoted!!.parentId)
    }

    @Test fun search_is_case_insensitive_and_scans_topic_body_and_tags() {
        val root = MemoryNode(topic = "Owner")
        val a = MemoryNode(topic = "Coffee", body = "drinks espresso", tags = listOf("habit"), parentId = root.id)
        val b = MemoryNode(topic = "Wine", body = "occasional", parentId = root.id)
        val tree = MemoryTree().upsert(root).upsert(a).upsert(b)
        assertEquals(listOf(a.id), tree.search("ESPRESSO").map(MemoryNode::id))
        assertEquals(listOf(a.id), tree.search("habit").map(MemoryNode::id))
    }

    @Test fun by_tag_is_exact_after_normalisation() {
        val a = MemoryNode(topic = "x", tags = listOf("Work"))
        val b = MemoryNode(topic = "y", tags = listOf("work-2026"))
        val tree = MemoryTree().upsert(a).upsert(b)
        assertEquals(listOf(a.id), tree.byTag("work").map(MemoryNode::id))
    }

    @Test fun root_nodes_excludes_children() {
        val root = MemoryNode(topic = "Owner")
        val child = MemoryNode(topic = "Habits", parentId = root.id)
        val tree = MemoryTree().upsert(root).upsert(child)
        assertFalse(tree.rootNodes().any { it.id == child.id })
    }
}
