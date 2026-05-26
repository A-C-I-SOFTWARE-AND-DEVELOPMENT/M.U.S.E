package com.aci.hermes.ui.screens.avatar

import android.graphics.Bitmap
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.aci.hermes.ui.jarvis.JarvisAvatarProfile
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * UI state owned by [AvatarPickerScreen].
 *
 * The "current" profile is what the rest of the app should render —
 * either a built-in default or a previously-saved pixelated user
 * avatar. The "preview" bitmap is a candidate the user is staging
 * (the result of [pickAndPixelate] or [loadCustom]).
 */
data class AvatarPickerState(
    val current: JarvisAvatarProfile,
    val previewBitmap: Bitmap? = null,
    val customExists: Boolean = false,
    val statusMessage: String? = null,
)

/**
 * Orchestrates Android Photo Picker handoffs + local pixelation +
 * app-private storage. **No network**, no broadened manifest
 * permissions, no upload code paths.
 *
 * The screen passes a `Bitmap` (already decoded from the picker URI)
 * to [pixelate]. The view-model never touches the URI directly —
 * URIs come with one-shot read permission only and shouldn't survive
 * past the screen.
 */
class AvatarPickerViewModel(
    private val storage: AvatarStorage,
    private val pixelator: AvatarPixelator = AvatarPixelator,
    private val io: CoroutineDispatcher = Dispatchers.IO,
    private val defaultProfile: () -> JarvisAvatarProfile = { DefaultAvatars.defaultProfile() },
    private val clock: () -> Long = System::currentTimeMillis,
) : ViewModel() {

    private val _state: MutableStateFlow<AvatarPickerState> = MutableStateFlow(initialState())

    val state: StateFlow<AvatarPickerState> = _state.asStateFlow()

    private fun initialState(): AvatarPickerState {
        val custom = storage.exists()
        val current: JarvisAvatarProfile = if (custom) {
            JarvisAvatarProfile(
                name = JarvisAvatarProfile.DEFAULT_NAME,
                source = JarvisAvatarProfile.Source.UserGenerated(storage.path()),
                selectedAt = clock(),
            )
        } else {
            defaultProfile()
        }
        return AvatarPickerState(current = current, customExists = custom)
    }

    /** Pick a built-in default. Persists the choice in-memory only — no I/O. */
    fun chooseDefault(entry: DefaultAvatars.Entry) {
        _state.value = _state.value.copy(
            current = DefaultAvatars.toProfile(entry, clock()),
            previewBitmap = null,
            statusMessage = null,
        )
    }

    /**
     * Stage a candidate bitmap as the preview. Called by the screen
     * after the photo picker returns a decoded `Bitmap`. The picker
     * supplies the decoded bitmap so the view-model never sees the
     * URI or the picker contract.
     */
    fun pixelate(source: Bitmap) {
        viewModelScope.launch {
            val pixelated = withContext(Dispatchers.Default) {
                pixelator.pixelate(source)
            }
            _state.value = _state.value.copy(
                previewBitmap = pixelated,
                statusMessage = null,
            )
        }
    }

    /** Persist the staged preview to app-private storage. */
    fun savePreview() {
        val preview = _state.value.previewBitmap ?: return
        viewModelScope.launch {
            val path = withContext(io) { storage.save(preview) }
            _state.value = _state.value.copy(
                current = JarvisAvatarProfile(
                    name = JarvisAvatarProfile.DEFAULT_NAME,
                    source = JarvisAvatarProfile.Source.UserGenerated(path),
                    selectedAt = clock(),
                ),
                previewBitmap = null,
                customExists = true,
                statusMessage = null,
            )
        }
    }

    /** Delete the saved user avatar. Falls back to the default profile. */
    fun deleteCustom() {
        viewModelScope.launch {
            withContext(io) { storage.delete() }
            _state.value = _state.value.copy(
                current = defaultProfile(),
                previewBitmap = null,
                customExists = false,
                statusMessage = null,
            )
        }
    }

    /** Reset the active selection to the bundled default. */
    fun resetToDefault() {
        _state.value = _state.value.copy(
            current = defaultProfile(),
            previewBitmap = null,
            statusMessage = null,
        )
    }

    class Factory(
        private val storage: AvatarStorage,
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T =
            AvatarPickerViewModel(storage) as T
    }
}
