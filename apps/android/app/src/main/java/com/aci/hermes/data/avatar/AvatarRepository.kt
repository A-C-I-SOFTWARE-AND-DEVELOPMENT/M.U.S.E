package com.aci.hermes.data.avatar

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File

private val Context.avatarDataStore: DataStore<Preferences> by preferencesDataStore(name = "avatar_prefs")

class AvatarRepository(
    private val context: Context,
    private val imageStore: AvatarImageStore,
    private val store: DataStore<Preferences> = context.avatarDataStore,
    private val json: Json = Json { ignoreUnknownKeys = true },
) {

    private object Keys {
        val PROFILE_JSON = stringPreferencesKey("profile_json")
    }

    val profileFlow: Flow<AvatarProfile?> = store.data.map { prefs ->
        val raw = prefs[Keys.PROFILE_JSON] ?: return@map null
        runCatching { json.decodeFromString<AvatarProfile>(raw) }.getOrNull()
    }

    suspend fun current(): AvatarProfile? = profileFlow.first()

    suspend fun save(profile: AvatarProfile) {
        store.edit { it[Keys.PROFILE_JSON] = json.encodeToString(profile) }
        val keep = profile.generatedPath?.let { File(it) }
        if (keep != null && imageStore.pathInAppPrivate(keep)) {
            imageStore.deleteAllExcept(keep)
        } else {
            imageStore.deleteAll()
        }
    }

    suspend fun clear() {
        store.edit { it.remove(Keys.PROFILE_JSON) }
        imageStore.deleteAll()
    }
}
