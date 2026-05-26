package com.aci.hermes.ui.screens.notifications

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.model.JarvisNotification
import com.aci.hermes.data.notifications.JarvisNotificationRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class NotificationsUiState(
    val items: List<JarvisNotification> = emptyList(),
)

class NotificationsViewModel(
    application: Application,
    private val notifications: JarvisNotificationRepository,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(NotificationsUiState())
    val state: StateFlow<NotificationsUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            notifications.items.collect { list ->
                _state.update { it.copy(items = list) }
            }
        }
    }

    fun markAllRead() {
        viewModelScope.launch { notifications.markAllRead() }
    }

    fun markRead(id: String) {
        viewModelScope.launch { notifications.markRead(id) }
    }

    fun clear() {
        viewModelScope.launch { notifications.clear() }
    }
}
