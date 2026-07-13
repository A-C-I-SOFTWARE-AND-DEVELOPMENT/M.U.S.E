package com.aci.hermes.automation

class PersonalActionPlanner(
    private val authorization: PersonalUseAuthorization = PersonalUseAuthorization(),
) {
    fun buildContract(
        request: String,
        targetAppLabel: String = "target app",
        targetPackage: String? = null,
        grants: List<CapabilityGrant> = emptyList(),
        emergencyStopped: Boolean = false,
        needsAttention: Boolean = false,
    ): PersonalActionContract {
        val risk = classifyRisk(request)
        val required = requiredCapabilities(needsAttention)
        val statusByCapability = grants.associate { it.capability to it.status }
        val missing = required.filter {
            statusByCapability[it] != AndroidCapabilityStatus.Granted
        }
        val beats = visualBeats(request, targetAppLabel)

        if (emergencyStopped) {
            return contract(
                request,
                targetAppLabel,
                targetPackage,
                risk,
                PersonalActionExecutionMode.EmergencyStopped,
                required,
                missing,
                beats,
                "Emergency stop is active.",
                authorization.standingAuthorization,
            )
        }

        if (!authorization.standingAuthorization) {
            return contract(
                request,
                targetAppLabel,
                targetPackage,
                risk,
                PersonalActionExecutionMode.AnimateOnly,
                required,
                missing,
                beats,
                "Standing owner authorization is disabled; avatar can preview only.",
                false,
            )
        }

        if (missing.isNotEmpty()) {
            return contract(
                request,
                targetAppLabel,
                targetPackage,
                risk,
                PersonalActionExecutionMode.BlockedMissingCapability,
                required,
                missing,
                beats,
                "Owner has authorized this local build, but Android capability grants are missing.",
                true,
            )
        }

        val pauseReason = when {
            risk == PersonalActionRisk.ExternalCommunication && authorization.pauseForExternalSend ->
                "pause before final send/post/publish gesture"
            risk in setOf(
                PersonalActionRisk.MoneyOrPurchase,
                PersonalActionRisk.AccountOrSecurity,
                PersonalActionRisk.Destructive,
            ) && authorization.pauseForMoneySecurityOrDestructive ->
                "pause before money/security/destructive final gesture"
            else -> ""
        }

        return contract(
            request,
            targetAppLabel,
            targetPackage,
            risk,
            if (pauseReason.isBlank()) PersonalActionExecutionMode.DirectExecute else PersonalActionExecutionMode.ExecuteWithPausePoint,
            required,
            emptyList(),
            beats,
            "Standing personal-use authorization is active and required Android capabilities are granted.",
            true,
            pauseReason,
        )
    }

    fun classifyRisk(request: String): PersonalActionRisk {
        val text = request.lowercase()
        val destructive = listOf("delete", "wipe", "factory reset", "uninstall", "remove account")
        val money = listOf("buy", "purchase", "pay", "send money", "checkout", "subscribe")
        val security = listOf("password", "2fa", "oauth", "login", "bank", "security", "permission")
        val communication = listOf("post", "send", "email", "message", "dm", "publish", "comment")
        val input = listOf("type", "fill", "enter", "submit", "tap", "click")

        return when {
            destructive.any { it in text } -> PersonalActionRisk.Destructive
            money.any { it in text } -> PersonalActionRisk.MoneyOrPurchase
            security.any { it in text } -> PersonalActionRisk.AccountOrSecurity
            communication.any { it in text } -> PersonalActionRisk.ExternalCommunication
            input.any { it in text } -> PersonalActionRisk.Input
            else -> PersonalActionRisk.Navigation
        }
    }

    private fun requiredCapabilities(needsAttention: Boolean): List<AndroidCapability> = buildList {
        add(AndroidCapability.PackageVisibility)
        add(AndroidCapability.Overlay)
        add(AndroidCapability.Accessibility)
        if (needsAttention) add(AndroidCapability.CameraAttention)
    }.distinct()

    private fun visualBeats(request: String, targetAppLabel: String): List<VisualBeat> = buildList {
        add(VisualBeat("acknowledge", "Mini JARVIS looks at Jeremiah and nods."))
        add(VisualBeat("think", "Mini JARVIS compresses the task into a small work card."))
        add(VisualBeat("move_to_target", "Mini JARVIS runs toward $targetAppLabel."))
        val text = request.lowercase()
        if (listOf("next screen", "next page", "swipe", "scroll").any { it in text }) {
            add(VisualBeat("turn_page", "Mini JARVIS grabs the screen edge and turns the page."))
        }
        add(VisualBeat("point", "Mini JARVIS points at the $targetAppLabel target."))
        add(VisualBeat("tap", "Mini JARVIS performs the visible tap animation at the same coordinate as the broker gesture."))
        add(VisualBeat("report", "Mini JARVIS returns to the corner and reports what happened."))
    }

    private fun contract(
        request: String,
        targetAppLabel: String,
        targetPackage: String?,
        risk: PersonalActionRisk,
        executionMode: PersonalActionExecutionMode,
        required: List<AndroidCapability>,
        missing: List<AndroidCapability>,
        beats: List<VisualBeat>,
        rationale: String,
        ownerAuthorized: Boolean,
        pauseReason: String = "",
    ) = PersonalActionContract(
        request = request,
        targetAppLabel = targetAppLabel,
        targetPackage = targetPackage,
        risk = risk,
        executionMode = executionMode,
        requiredCapabilities = required,
        missingCapabilities = missing,
        visualBeats = beats,
        rationale = rationale,
        ownerAuthorized = ownerAuthorized,
        pauseReason = pauseReason,
    )
}
