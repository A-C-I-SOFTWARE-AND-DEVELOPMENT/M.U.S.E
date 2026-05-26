package com.aci.hermes.data.gateway

/**
 * Hand-written demo payload replayed on [MockGatewayClient.connect] so
 * the full Android UI is navigable with no backend attached.
 *
 * Every record here is fictitious. None of the strings are real user
 * data, real task ids, or real PR references — anyone reading the
 * stream should see at a glance that this is mock content.
 */
internal object FakeData {

    fun demoEvents(
        clock: () -> Long,
        idFactory: () -> String,
    ): List<GatewayEvent> {
        val baseTime = clock()
        var step = 0
        fun ts(): String = isoFormat(baseTime + (step++).toLong() * 250L)
        fun id(prefix: String): String = "$prefix-${idFactory().take(8)}"

        return buildList {
            // Conversation seed
            add(
                JarvisResponseEvent(
                    eventId = id("evt"),
                    occurredAt = ts(),
                    text = "Mock gateway connected. You are seeing demo data — no real workers are running.",
                    responseMode = "companion",
                )
            )

            // Tasks
            val taskA = GatewayTaskSnapshot(
                taskId = "task-mock-001",
                title = "Mock: outline Q3 product brief",
                summary = "Draft outline, capture open questions, hand off to Builder for prose.",
                status = "drafting",
                workspacePath = "/mock/workspace/product-brief",
                workerKind = "planner",
            )
            val taskB = GatewayTaskSnapshot(
                taskId = "task-mock-002",
                title = "Mock: refactor android navigation graph",
                summary = "Extract nested graph for cockpit screens; preserve back stack.",
                status = "in_progress",
                workspacePath = "/mock/workspace/apps/android",
                workerKind = "claude_code_builder",
            )
            add(TaskCreatedEvent(id("evt"), ts(), task = taskA))
            add(TaskCreatedEvent(id("evt"), ts(), task = taskB))
            add(
                TaskUpdatedEvent(
                    eventId = id("evt"),
                    occurredAt = ts(),
                    task = taskB.copy(status = "awaiting_review"),
                    reason = "builder_completed",
                )
            )

            // Memory
            add(
                MemoryUpdatedEvent(
                    eventId = id("evt"),
                    occurredAt = ts(),
                    entry = MemoryEntry(
                        memoryId = "mem-mock-001",
                        kind = "preference",
                        text = "Prefers short mobile responses while moving.",
                        source = "operator_mode",
                    ),
                )
            )
            add(
                MemoryUpdatedEvent(
                    eventId = id("evt"),
                    occurredAt = ts(),
                    entry = MemoryEntry(
                        memoryId = "mem-mock-002",
                        kind = "decision",
                        text = "Claude Code is primary builder; Codex is reviewer.",
                        source = "operator_mode",
                    ),
                )
            )

            // Audit
            add(
                AuditRecordCreatedEvent(
                    eventId = id("evt"),
                    occurredAt = ts(),
                    record = AuditRecord(
                        recordId = "audit-mock-001",
                        action = "task_created",
                        actor = "mock_user",
                        outcome = "ok",
                        details = mapOf("task_id" to taskA.taskId),
                    ),
                )
            )

            // Workers
            val worker = WorkerSnapshot(
                workerId = "worker-mock-001",
                kind = "claude_code_builder",
                title = "Builder — refactor nav graph",
                taskId = taskB.taskId,
            )
            add(WorkerStartedEvent(id("evt"), ts(), worker = worker))
            add(
                WorkerProgressEvent(
                    eventId = id("evt"),
                    occurredAt = ts(),
                    workerId = worker.workerId,
                    fraction = 0.35f,
                    message = "Reading nav graph",
                )
            )
            add(
                WorkerProgressEvent(
                    eventId = id("evt"),
                    occurredAt = ts(),
                    workerId = worker.workerId,
                    fraction = 0.75f,
                    message = "Generating patch",
                )
            )

            // Approvals — one standard, one serious, one critical so the
            // UI demo exercises all three confirmation paths.
            add(
                ApprovalRequestedEvent(
                    eventId = id("evt"),
                    occurredAt = ts(),
                    approvalId = "approval-mock-std",
                    actionId = "open_pr",
                    summary = "Open draft PR for nav-graph refactor.",
                    riskClass = ApprovalRiskClass.STANDARD,
                )
            )
            add(
                ApprovalRequestedEvent(
                    eventId = id("evt"),
                    occurredAt = ts(),
                    approvalId = "approval-mock-serious",
                    actionId = "force_push_branch",
                    summary = "Force-push refactor branch to overwrite remote.",
                    riskClass = ApprovalRiskClass.SERIOUS,
                )
            )
            add(
                SeriousConfirmationRequiredEvent(
                    eventId = id("evt"),
                    occurredAt = ts(),
                    approvalId = "approval-mock-serious",
                    summary = "Force-push will overwrite remote history.",
                )
            )
            add(
                ApprovalRequestedEvent(
                    eventId = id("evt"),
                    occurredAt = ts(),
                    approvalId = "approval-mock-critical",
                    actionId = "rotate_signing_key",
                    summary = "Rotate Play Store signing key.",
                    riskClass = ApprovalRiskClass.CRITICAL,
                )
            )
            add(
                CriticalConfirmationRequiredEvent(
                    eventId = id("evt"),
                    occurredAt = ts(),
                    approvalId = "approval-mock-critical",
                    summary = "Rotating the signing key affects all future releases.",
                    impactReport = ImpactReport(
                        summary = "Rotating Play signing key.",
                        blastRadius = "all_future_releases",
                        reversibility = "irreversible_once_published",
                        affectedResources = listOf("play_store", "release_pipeline"),
                        rollbackPlan = "Cannot roll back once published; mitigate via emergency Play Console support ticket.",
                    ),
                )
            )

            // Initial icon state
            add(
                IconStateChangedEvent(
                    eventId = id("evt"),
                    occurredAt = ts(),
                    state = IconState.WAITING_APPROVAL,
                    detail = "3 approvals pending",
                )
            )
        }
    }
}
