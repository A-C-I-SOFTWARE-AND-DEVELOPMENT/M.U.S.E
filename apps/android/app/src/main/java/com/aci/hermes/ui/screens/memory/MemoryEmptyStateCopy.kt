package com.aci.hermes.ui.screens.memory

/**
 * Owner-facing copy for empty + filtered states on the Memory surface.
 * Pure Kotlin so the Compose screen and the JVM tests share one
 * source of truth — copy edits land here and the screen re-reads.
 */
object MemoryEmptyStateCopy {

    const val FILTER_HIDES_ALL =
        "No memory matches the current filter. Adjust search or category to see " +
            "more, or clear filters to see everything Jarvis has learned."

    const val GENUINELY_EMPTY =
        "No memory entries yet. Jarvis only remembers what you approve — you'll " +
            "see every entry here and you can correct or forget anything."

    const val OWNER_NOTE_REDACTED =
        "Secrets and private identifiers are redacted before they ever reach this screen."

    const val DELETE_OWNER_WARNING =
        "Owner action: Jarvis will forget this memory. Deletion is permanent " +
            "from the app — type DELETE to confirm."

    const val CORRECT_OWNER_NOTE =
        "Owner action: Jarvis will replace the stored content with your correction. " +
            "The original is dropped — capture the change in your reason note."

    /**
     * Pick the right empty-state copy for the current memory list.
     * @param filterActive true when search or a category filter is set.
     * @param totalItems the total in the underlying repository
     *   (post-redaction). Zero means genuinely empty.
     */
    fun chooseFor(filterActive: Boolean, totalItems: Int): String = when {
        totalItems == 0 -> GENUINELY_EMPTY
        filterActive -> FILTER_HIDES_ALL
        else -> GENUINELY_EMPTY
    }
}
