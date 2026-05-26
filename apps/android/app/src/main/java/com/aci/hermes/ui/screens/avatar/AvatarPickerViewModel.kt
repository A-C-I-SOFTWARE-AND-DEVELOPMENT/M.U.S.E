package com.aci.hermes.ui.screens.avatar

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.avatar.AvatarImageStore
import com.aci.hermes.data.avatar.AvatarPixelator
import com.aci.hermes.data.avatar.AvatarProfile
import com.aci.hermes.data.avatar.AvatarRepository
import com.aci.hermes.data.avatar.AvatarSource
import com.aci.hermes.data.avatar.AvatarStyle
import com.aci.hermes.data.avatar.JarvisBuiltin
import com.aci.hermes.data.avatar.PixelSize
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.File

sealed class AvatarPickerState {
    data object Idle : AvatarPickerState()
    data object Processing : AvatarPickerState()
    data class PreviewReady(val previewFile: File?, val draft: AvatarProfile) : AvatarPickerState()
    data class Saved(val profile: AvatarProfile) : AvatarPickerState()
    data class Error(val message: String) : AvatarPickerState()
}

class AvatarPickerViewModel(
    application: Application,
    private val pixelator: AvatarPixelator,
    private val imageStore: AvatarImageStore,
    private val repo: AvatarRepository,
    private val logBuffer: LogBuffer,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow<AvatarPickerState>(AvatarPickerState.Idle)
    val state: StateFlow<AvatarPickerState> = _state.asStateFlow()

    private var lastPickedUri: Uri? = null
    private var pixelSize: PixelSize = PixelSize.BALANCED_32
    private var style: AvatarStyle = AvatarStyle.NAVY_GOLD

    init {
        viewModelScope.launch {
            val existing = repo.current()
            if (existing != null) {
                pixelSize = existing.pixelSize
                style = existing.style
                val file = existing.generatedPath?.let { File(it) }?.takeIf {
                    imageStore.pathInAppPrivate(it) && it.exists()
                }
                _state.value = AvatarPickerState.PreviewReady(file, existing)
            }
        }
    }

    fun selectBuiltIn(builtin: JarvisBuiltin) {
        lastPickedUri = null
        val draft = AvatarProfile(
            source = AvatarSource.BUILTIN,
            builtin = builtin,
            generatedPath = null,
            pixelSize = pixelSize,
            style = style,
        )
        _state.value = AvatarPickerState.PreviewReady(previewFile = null, draft = draft)
    }

    fun onPhotoPicked(uri: Uri?) {
        if (uri == null) return
        lastPickedUri = uri
        regenerate(uri)
    }

    fun setPixelSize(size: PixelSize) {
        if (pixelSize == size) return
        pixelSize = size
        applyDraftUpdate()
    }

    fun setStyle(newStyle: AvatarStyle) {
        if (style == newStyle) return
        style = newStyle
        applyDraftUpdate()
    }

    private fun applyDraftUpdate() {
        val current = _state.value
        if (current is AvatarPickerState.PreviewReady) {
            when (current.draft.source) {
                AvatarSource.BUILTIN -> {
                    _state.value = current.copy(
                        draft = current.draft.copy(pixelSize = pixelSize, style = style),
                    )
                }
                AvatarSource.GENERATED -> {
                    val uri = lastPickedUri
                    if (uri != null) regenerate(uri)
                }
            }
        } else if (current is AvatarPickerState.Saved) {
            val uri = lastPickedUri
            if (current.profile.source == AvatarSource.GENERATED && uri != null) regenerate(uri)
        }
    }

    private fun regenerate(uri: Uri) {
        _state.value = AvatarPickerState.Processing
        viewModelScope.launch {
            try {
                val file = pixelator.pixelate(uri, pixelSize, style)
                val draft = AvatarProfile(
                    source = AvatarSource.GENERATED,
                    builtin = null,
                    generatedPath = file.absolutePath,
                    pixelSize = pixelSize,
                    style = style,
                )
                _state.value = AvatarPickerState.PreviewReady(previewFile = file, draft = draft)
            } catch (t: Throwable) {
                logBuffer.error("AvatarPicker", "Pixelation failed: ${t.message}")
                _state.value = AvatarPickerState.Error(t.message ?: "Unable to process image")
            }
        }
    }

    fun save() {
        val current = _state.value as? AvatarPickerState.PreviewReady ?: return
        viewModelScope.launch {
            try {
                repo.save(current.draft)
                logBuffer.info("AvatarPicker", "Saved ${current.draft.source} avatar")
                _state.value = AvatarPickerState.Saved(current.draft)
            } catch (t: Throwable) {
                logBuffer.error("AvatarPicker", "Save failed: ${t.message}")
                _state.value = AvatarPickerState.Error(t.message ?: "Unable to save avatar")
            }
        }
    }

    fun reset() {
        lastPickedUri = null
        viewModelScope.launch {
            try {
                repo.clear()
                logBuffer.info("AvatarPicker", "Avatar reset")
                _state.value = AvatarPickerState.Idle
            } catch (t: Throwable) {
                logBuffer.error("AvatarPicker", "Reset failed: ${t.message}")
                _state.value = AvatarPickerState.Error(t.message ?: "Unable to reset avatar")
            }
        }
    }
}
