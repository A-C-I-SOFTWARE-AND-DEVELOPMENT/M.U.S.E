package com.aci.hermes.automation

enum class AndroidCapability {
    Overlay,
    Accessibility,
    MediaProjection,
    CameraAttention,
    MicrophoneWake,
    PackageVisibility,
    Notifications,
}

enum class AndroidCapabilityStatus {
    Unknown,
    Granted,
    Denied,
    TemporarilyUnavailable,
}

enum class PersonalActionRisk {
    Navigation,
    Input,
    ExternalCommunication,
    MoneyOrPurchase,
    AccountOrSecurity,
    Destructive,
}

enum class PersonalActionExecutionMode {
    AnimateOnly,
    DirectExecute,
    ExecuteWithPausePoint,
    BlockedMissingCapability,
    EmergencyStopped,
}

data class CapabilityGrant(
    val capability: AndroidCapability,
    val status: AndroidCapabilityStatus = AndroidCapabilityStatus.Unknown,
)

data class VisualBeat(
    val name: String,
    val description: String,
    val durationMs: Int = 350,
)

data class PersonalUseAuthorization(
    val ownerName: String = "Jeremiah Echerd",
    val personalUseOnly: Boolean = true,
    val developerMode: Boolean = true,
    val standingAuthorization: Boolean = true,
    val allowCrossAppNavigation: Boolean = true,
    val allowGestureExecution: Boolean = true,
    val allowOverlayAvatar: Boolean = true,
    val allowAttentionSensing: Boolean = true,
    val pauseForExternalSend: Boolean = true,
    val pauseForMoneySecurityOrDestructive: Boolean = true,
)

data class PersonalActionContract(
    val request: String,
    val targetAppLabel: String,
    val targetPackage: String?,
    val risk: PersonalActionRisk,
    val executionMode: PersonalActionExecutionMode,
    val requiredCapabilities: List<AndroidCapability>,
    val missingCapabilities: List<AndroidCapability>,
    val visualBeats: List<VisualBeat>,
    val rationale: String,
    val ownerAuthorized: Boolean,
    val pauseReason: String = "",
)
