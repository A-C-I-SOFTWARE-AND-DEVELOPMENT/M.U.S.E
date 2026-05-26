package com.aci.hermes.data.mock

import com.aci.hermes.data.approval.ApprovalRepository
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.conversation.ConversationRepository
import com.aci.hermes.data.gateway.GatewayEventBus
import com.aci.hermes.data.memory.MemoryRepository
import com.aci.hermes.data.model.ApprovalCard
import com.aci.hermes.data.model.ApprovalSeverity
import com.aci.hermes.data.model.AuditEntry
import com.aci.hermes.data.model.AuditKind
import com.aci.hermes.data.model.BlastRadius
import com.aci.hermes.data.model.ChatMessage
import com.aci.hermes.data.model.ChatRole
import com.aci.hermes.data.model.ChatSuggestion
import com.aci.hermes.data.model.GatewayEvent
import com.aci.hermes.data.model.GatewayEventKind
import com.aci.hermes.data.model.ImpactReport
import com.aci.hermes.data.model.JarvisNotification
import com.aci.hermes.data.model.JarvisNotificationKind
import com.aci.hermes.data.model.MemoryBranch
import com.aci.hermes.data.model.MemoryConfidence
import com.aci.hermes.data.model.MemoryFact
import com.aci.hermes.data.model.SocialPattern
import com.aci.hermes.data.model.SocialPatternKind
import com.aci.hermes.data.model.SuggestionKind
import com.aci.hermes.data.notifications.JarvisNotificationRepository
import com.aci.hermes.data.social.SocialPatternRepository

/**
 * Mock Mode seeder.
 *
 * Mock mode is on by default so the user has something meaningful to
 * tap, scroll, and explore on first launch — without anything having
 * to be wired up, no external calls, no real risk.
 *
 * The seeder only writes when a store is empty, so re-seeding is safe
 * and never overwrites real data.
 */
class MockDataSeeder(
    private val conversations: ConversationRepository,
    private val approvals: ApprovalRepository,
    private val memory: MemoryRepository,
    private val audit: AuditRepository,
    private val gateway: GatewayEventBus,
    private val notifications: JarvisNotificationRepository,
    private val social: SocialPatternRepository,
) {

    suspend fun seedAll() {
        seedConversation()
        seedApprovals()
        seedMemory()
        seedAudit()
        seedGateway()
        seedNotifications()
        seedSocial()
    }

    private suspend fun seedConversation() {
        if (conversations.messages.value.isNotEmpty()) return
        val now = System.currentTimeMillis()
        listOf(
            ChatMessage(
                role = ChatRole.SYSTEM,
                body = "Mock mode is on. Replies are simulated locally.",
                createdAt = now - 600_000,
            ),
            ChatMessage(
                role = ChatRole.JARVIS,
                body = "Good to see you. I am Jarvis Prime — your local AI operating partner. Tell me what you need and I will plan, draft, or ask for approval before I act.",
                createdAt = now - 300_000,
                suggestion = ChatSuggestion(
                    label = "Show pending approvals",
                    kind = SuggestionKind.OPEN_APPROVALS,
                ),
            ),
            ChatMessage(
                role = ChatRole.USER,
                body = "Show me what you remember about me.",
                createdAt = now - 180_000,
            ),
            ChatMessage(
                role = ChatRole.JARVIS,
                body = "Memory is open in the Memory tab. Inferences are clearly marked; you can confirm, reject, or forget anything I have noted.",
                createdAt = now - 120_000,
                suggestion = ChatSuggestion(
                    label = "Open memory",
                    kind = SuggestionKind.OPEN_MEMORY,
                ),
            ),
        ).forEach { conversations.append(it) }
    }

    private suspend fun seedApprovals() {
        approvals.seedIfEmpty {
            listOf(
                ApprovalCard(
                    title = "Draft a PR description for branch claude/jarvis-prime-android-jW7sT",
                    summary = "I will assemble a summary, risks, and test plan. Nothing pushes. You approve before I send.",
                    severity = ApprovalSeverity.ROUTINE,
                    source = "task_planner",
                ),
                ApprovalCard(
                    title = "Forget memory item: \"prefers conference rooms quiet\"",
                    summary = "I will remove this inferred preference from memory. This is reversible — I will record the change in the audit log.",
                    severity = ApprovalSeverity.RISKY,
                    source = "memory_engine",
                ),
                ApprovalCard(
                    title = "Push branch and open draft pull request",
                    summary = "Push the local branch and open a draft PR upstream.",
                    severity = ApprovalSeverity.SERIOUS,
                    source = "publisher",
                    impact = ImpactReport(
                        summary = "Pushes the branch to origin and opens a draft PR. No code change yet — this just makes the branch visible to reviewers.",
                        risks = listOf(
                            "Branch becomes visible to repository collaborators.",
                            "Any CI hooks attached to the PR will start running.",
                        ),
                        affectedSurfaces = listOf("origin/claude/jarvis-prime-android-jW7sT", "GitHub PR feed"),
                        rollbackPlan = "Close the draft PR and delete the remote branch.",
                        estimatedBlastRadius = BlastRadius.ACCOUNT,
                    ),
                ),
                ApprovalCard(
                    title = "Deploy app to production",
                    summary = "Triggers the production release pipeline. This is irreversible without a manual rollback. Confirm twice with the authorization phrase to proceed.",
                    severity = ApprovalSeverity.CRITICAL,
                    source = "release_manager",
                    impact = ImpactReport(
                        summary = "Builds the signed release APK, uploads it to the Play console, and promotes to production.",
                        risks = listOf(
                            "Real users receive the new build.",
                            "Rollback requires a new release with a fixed version code.",
                            "Any regressions surface immediately in crash reports.",
                        ),
                        affectedSurfaces = listOf("Play Console", "Production users", "Crashlytics"),
                        rollbackPlan = "Cut a hotfix branch, bump versionCode, ship a corrective release. Plan reviewed: yes.",
                        estimatedBlastRadius = BlastRadius.IRREVERSIBLE,
                    ),
                ),
            )
        }
    }

    private suspend fun seedMemory() {
        memory.seedIfEmpty {
            listOf(
                MemoryFact(
                    branch = MemoryBranch.FACTS,
                    label = "Preferred name",
                    detail = "Jeremiah",
                    confidence = MemoryConfidence.CONFIRMED,
                    source = "onboarding",
                ),
                MemoryFact(
                    branch = MemoryBranch.PREFERENCES,
                    label = "Tone",
                    detail = "Direct, plain, no sycophancy.",
                    confidence = MemoryConfidence.CONFIRMED,
                ),
                MemoryFact(
                    branch = MemoryBranch.PREFERENCES,
                    label = "Risky asks",
                    detail = "Confirm once unless impact is large.",
                    confidence = MemoryConfidence.CONFIRMED,
                ),
                MemoryFact(
                    branch = MemoryBranch.GOALS,
                    label = "Ship Jarvis Prime mobile",
                    detail = "Mobile-first AI operating partner. Local, permission-safe.",
                    confidence = MemoryConfidence.CONFIRMED,
                ),
                MemoryFact(
                    branch = MemoryBranch.INFERENCES,
                    label = "Works late",
                    detail = "Most activity between 22:00 and 02:00. Inferred from message timestamps.",
                    confidence = MemoryConfidence.INFERRED,
                ),
                MemoryFact(
                    branch = MemoryBranch.HISTORY,
                    label = "Last release",
                    detail = "0.14.1+aci.1 — Jarvis Prime runtime v1.0.0.",
                    confidence = MemoryConfidence.CONFIRMED,
                ),
            )
        }
    }

    private suspend fun seedAudit() {
        audit.seedIfEmpty {
            val now = System.currentTimeMillis()
            listOf(
                AuditEntry(
                    kind = AuditKind.SYSTEM,
                    title = "Jarvis Prime started",
                    detail = "Application initialised. Mock mode active.",
                    createdAt = now - 60_000,
                ),
                AuditEntry(
                    kind = AuditKind.MEMORY_UPDATED,
                    title = "Memory: preferred tone confirmed",
                    detail = "Pref \"direct, plain, no sycophancy\" set to confirmed.",
                    createdAt = now - 45_000,
                ),
                AuditEntry(
                    kind = AuditKind.APPROVAL_GRANTED,
                    title = "Approved: cleanup conversation history older than 30 days",
                    detail = "Risky-tier approval. One confirmation. Reversible up to 24h.",
                    createdAt = now - 30_000,
                ),
            )
        }
    }

    private suspend fun seedGateway() {
        gateway.seedIfEmpty {
            val now = System.currentTimeMillis()
            listOf(
                GatewayEvent(
                    kind = GatewayEventKind.HEARTBEAT,
                    source = "mock-gateway",
                    message = "Mock gateway heartbeat",
                    createdAt = now - 90_000,
                ),
                GatewayEvent(
                    kind = GatewayEventKind.APPROVAL_REQUESTED,
                    source = "publisher",
                    message = "Publisher requested approval for branch push.",
                    createdAt = now - 60_000,
                    severity = "warn",
                ),
                GatewayEvent(
                    kind = GatewayEventKind.JOB_STARTED,
                    source = "worker.codex",
                    message = "Worker started: \"Draft PR description\"",
                    createdAt = now - 30_000,
                ),
            )
        }
    }

    private suspend fun seedNotifications() {
        notifications.seedIfEmpty {
            val now = System.currentTimeMillis()
            listOf(
                JarvisNotification(
                    kind = JarvisNotificationKind.INFO,
                    title = "Welcome to Jarvis Prime",
                    body = "Tap around — the app is in mock mode by default. You can wire a real gateway from Settings → Gateway.",
                    createdAt = now - 120_000,
                ),
                JarvisNotification(
                    kind = JarvisNotificationKind.APPROVAL_NEEDED,
                    title = "Approval waiting",
                    body = "A push-to-origin draft is awaiting your approval.",
                    createdAt = now - 60_000,
                ),
                JarvisNotification(
                    kind = JarvisNotificationKind.WARNING,
                    title = "Critical action queued",
                    body = "A production deploy is queued. It will require a typed authorization phrase.",
                    createdAt = now - 30_000,
                ),
            )
        }
    }

    private suspend fun seedSocial() {
        social.seedIfEmpty {
            listOf(
                SocialPattern(
                    kind = SocialPatternKind.COMMUNICATION_STYLE,
                    title = "Prefers short, direct messages",
                    observation = "Across the last 20 messages, responses average under 80 characters.",
                    signalStrength = 0.78f,
                ),
                SocialPattern(
                    kind = SocialPatternKind.SCHEDULE,
                    title = "Most active 22:00 – 02:00",
                    observation = "Activity clusters in late-night hours. Long pauses early afternoon.",
                    signalStrength = 0.62f,
                ),
                SocialPattern(
                    kind = SocialPatternKind.REPEATING_THEME,
                    title = "Mentions \"local-first\" often",
                    observation = "Three times in the last week. Suggests a strong design preference.",
                    signalStrength = 0.55f,
                ),
            )
        }
    }
}
