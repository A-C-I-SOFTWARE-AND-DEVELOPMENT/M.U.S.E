package com.aci.hermes.data.avatar

sealed class AvatarPickerResult {
    data object Empty : AvatarPickerResult()
    data class Generated(val path: String) : AvatarPickerResult()
    data class BuiltIn(val builtin: JarvisBuiltin) : AvatarPickerResult()
}
