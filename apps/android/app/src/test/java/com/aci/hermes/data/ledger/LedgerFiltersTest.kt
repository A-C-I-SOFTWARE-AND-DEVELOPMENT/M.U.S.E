package com.aci.hermes.data.ledger

import com.aci.hermes.data.model.ledger.LedgerFilters
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LedgerFiltersTest {

    @Test
    fun `empty filters report empty and only carry default order`() {
        val f = LedgerFilters()
        assertTrue(f.isEmpty)
        // toQuery always carries order; the client drops blank values before sending.
        assertEquals("desc", f.toQuery()["order"])
        assertEquals("", f.toQuery()["job"])
    }

    @Test
    fun `set filters are not empty and map to query keys`() {
        val f = LedgerFilters(
            job = "job_alpha",
            risk = "SERIOUS",
            worker = "codex-execute",
            file = "app.py",
            since = "2026-06-01",
            until = "2026-06-30",
            order = "asc",
        )
        assertFalse(f.isEmpty)
        val q = f.toQuery()
        assertEquals("job_alpha", q["job"])
        assertEquals("SERIOUS", q["risk"])
        assertEquals("codex-execute", q["worker"])
        assertEquals("app.py", q["file"])
        assertEquals("2026-06-01", q["since"])
        assertEquals("2026-06-30", q["until"])
        assertEquals("asc", q["order"])
    }
}
