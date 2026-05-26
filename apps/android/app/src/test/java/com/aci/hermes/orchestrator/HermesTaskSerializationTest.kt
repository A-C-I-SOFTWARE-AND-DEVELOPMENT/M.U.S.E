package com.aci.hermes.orchestrator

import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.data.model.TaskType
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Mirrors the persistence format used by [com.aci.hermes.data.orchestrator.HermesTaskRepository]
 * — we serialize the list with the same Json config (`ignoreUnknownKeys = true`,
 * `encodeDefaults = true`) so a round-trip here also proves on-disk
 * forward-compatibility.
 */
class HermesTaskSerializationTest {

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
        prettyPrint = false
    }

    private fun listSerializer() = ListSerializer(HermesTask.serializer())

    @Test
    fun `single task round-trips through json`() {
        val original = HermesTask(
            id = "deterministic-id",
            title = "Round-trip me",
            description = "Some description.",
            workspacePath = "/tmp/workspace",
            targetTool = TargetTool.CODEX,
            taskType = TaskType.BUILD,
            status = TaskStatus.DRAFT,
            createdAt = 1_700_000_000_000L,
            updatedAt = 1_700_000_000_500L,
        )
        val encoded = json.encodeToString(listSerializer(), listOf(original))
        val decoded = json.decodeFromString(listSerializer(), encoded)
        assertEquals(listOf(original), decoded)
    }

    @Test
    fun `empty list round-trips`() {
        val encoded = json.encodeToString(listSerializer(), emptyList())
        val decoded = json.decodeFromString(listSerializer(), encoded)
        assertTrue(decoded.isEmpty())
    }

    @Test
    fun `unknown keys in stored json are ignored`() {
        val withUnknown = """[
            {
              "id": "x",
              "title": "T",
              "description": "D",
              "workspacePath": null,
              "targetTool": "CODEX",
              "taskType": "BUILD",
              "status": "DRAFT",
              "createdAt": 1,
              "updatedAt": 2,
              "promptBody": null,
              "resultNotes": null,
              "reviewNotes": null,
              "nextAction": null,
              "someFutureField": "ignored"
            }
        ]"""
        val decoded = json.decodeFromString(listSerializer(), withUnknown)
        assertEquals(1, decoded.size)
        assertEquals("x", decoded[0].id)
    }

    @Test
    fun `all task statuses survive round trip`() {
        val tasks = TaskStatus.values().mapIndexed { i, status ->
            HermesTask(
                id = "id-$i",
                title = "t-$i",
                description = "",
                status = status,
                createdAt = i.toLong(),
                updatedAt = i.toLong(),
            )
        }
        val encoded = json.encodeToString(listSerializer(), tasks)
        val decoded = json.decodeFromString(listSerializer(), encoded)
        assertEquals(tasks, decoded)
    }

    @Test
    fun `all task types survive round trip`() {
        val tasks = TaskType.values().mapIndexed { i, type ->
            HermesTask(
                id = "id-$i",
                title = "t-$i",
                description = "",
                taskType = type,
                createdAt = i.toLong(),
                updatedAt = i.toLong(),
            )
        }
        val encoded = json.encodeToString(listSerializer(), tasks)
        val decoded = json.decodeFromString(listSerializer(), encoded)
        assertEquals(tasks, decoded)
    }

    @Test
    fun `target tool enum survives round trip`() {
        val tasks = TargetTool.values().mapIndexed { i, tool ->
            HermesTask(
                id = "id-$i",
                title = "t-$i",
                description = "",
                targetTool = tool,
                createdAt = i.toLong(),
                updatedAt = i.toLong(),
            )
        }
        val encoded = json.encodeToString(listSerializer(), tasks)
        val decoded = json.decodeFromString(listSerializer(), encoded)
        assertEquals(tasks, decoded)
    }
}
