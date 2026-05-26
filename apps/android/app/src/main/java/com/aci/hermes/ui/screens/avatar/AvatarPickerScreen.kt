package com.aci.hermes.ui.screens.avatar

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.painter.Painter
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.ui.jarvis.JarvisAvatarProfile
import com.aci.hermes.ui.screens.live.JarvisLiveColors

/**
 * On-device avatar picker.
 *
 * Flow:
 *  1. The user can pick one of the bundled defaults (no permission, no I/O).
 *  2. Or hit "Pick from photos" → Android Photo Picker
 *     ([ActivityResultContracts.PickVisualMedia], image-only). The
 *     picker returns a URI with one-shot read permission; the screen
 *     decodes it to a Bitmap once and hands the Bitmap to the VM.
 *  3. The VM pixelates on `Dispatchers.Default` and surfaces the
 *     result as `previewBitmap`.
 *  4. "Save" persists the preview to `context.filesDir/avatars/`.
 *
 * No `READ_MEDIA_*` / `READ_EXTERNAL_STORAGE` permission is requested.
 * No upload happens. The "local-only" reassurance is also on-screen.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AvatarPickerScreen(
    viewModel: AvatarPickerViewModel,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current

    val picker = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickVisualMedia(),
    ) { uri: Uri? ->
        if (uri != null) {
            val bitmap: Bitmap? = runCatching {
                context.contentResolver.openInputStream(uri)?.use { input ->
                    BitmapFactory.decodeStream(input)
                }
            }.getOrNull()
            if (bitmap != null) viewModel.pixelate(bitmap)
        }
    }

    Scaffold(
        modifier = modifier,
        containerColor = JarvisLiveColors.Background,
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.avatar_picker_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            imageVector = Icons.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.action_back),
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = JarvisLiveColors.Background,
                    titleContentColor = JarvisLiveColors.OnBackground,
                    navigationIconContentColor = JarvisLiveColors.OnBackground,
                ),
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            // ─── Preview (staged) ──────────────────────────────────
            Text(
                text = stringResource(R.string.avatar_picker_custom_header),
                color = JarvisLiveColors.OnBackground,
                style = MaterialTheme.typography.titleMedium,
            )
            Spacer(modifier = Modifier.height(8.dp))
            AvatarPreviewTile(
                profile = state.current,
                previewBitmap = state.previewBitmap,
            )
            Spacer(modifier = Modifier.height(12.dp))

            // ─── Pick + Save / Reset row ────────────────────────────
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {
                    picker.launch(
                        PickVisualMediaRequest(
                            ActivityResultContracts.PickVisualMedia.ImageOnly,
                        ),
                    )
                }) {
                    Text(stringResource(R.string.avatar_picker_pick_photo))
                }
                Button(
                    onClick = { viewModel.savePreview() },
                    enabled = state.previewBitmap != null,
                ) {
                    Text(stringResource(R.string.avatar_picker_pixelate_save))
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = { viewModel.deleteCustom() },
                    enabled = state.customExists,
                ) {
                    Text(stringResource(R.string.avatar_picker_delete))
                }
                OutlinedButton(onClick = { viewModel.resetToDefault() }) {
                    Text(stringResource(R.string.avatar_picker_reset))
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = stringResource(R.string.avatar_picker_local_only_note),
                color = JarvisLiveColors.OnBackgroundMuted,
                style = MaterialTheme.typography.bodySmall,
            )

            Spacer(modifier = Modifier.height(20.dp))

            // ─── Bundled defaults grid ─────────────────────────────
            Text(
                text = stringResource(R.string.avatar_picker_defaults_header),
                color = JarvisLiveColors.OnBackground,
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.fillMaxWidth().padding(start = 4.dp),
            )
            Spacer(modifier = Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                for (entry in DefaultAvatars.ALL) {
                    DefaultAvatarTile(
                        painter = painterResource(entry.drawableResId),
                        label = stringResource(entry.nameStringResId),
                        onClick = { viewModel.chooseDefault(entry) },
                    )
                }
            }
        }
    }
}

@Composable
private fun AvatarPreviewTile(
    profile: JarvisAvatarProfile,
    previewBitmap: Bitmap?,
) {
    Box(
        modifier = Modifier
            .size(192.dp)
            .clip(RoundedCornerShape(16.dp))
            .background(JarvisLiveColors.Surface)
            .border(2.dp, JarvisLiveColors.Active, RoundedCornerShape(16.dp)),
        contentAlignment = Alignment.Center,
    ) {
        when {
            previewBitmap != null -> Image(
                bitmap = previewBitmap.asImageBitmap(),
                contentDescription = null,
                modifier = Modifier.fillMaxSize(),
            )
            profile.source is JarvisAvatarProfile.Source.BuiltIn -> Image(
                painter = painterResource(profile.source.drawableResId),
                contentDescription = null,
                modifier = Modifier.fillMaxSize(),
            )
            else -> Text(
                text = stringResource(R.string.avatar_picker_custom_empty),
                color = JarvisLiveColors.OnBackgroundMuted,
                modifier = Modifier.padding(12.dp),
            )
        }
    }
}

@Composable
private fun DefaultAvatarTile(
    painter: Painter,
    label: String,
    onClick: () -> Unit,
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Box(
            modifier = Modifier
                .size(72.dp)
                .clip(RoundedCornerShape(12.dp))
                .background(JarvisLiveColors.Surface)
                .border(1.dp, JarvisLiveColors.OnBackgroundMuted, RoundedCornerShape(12.dp)),
        ) {
            Image(
                painter = painter,
                contentDescription = label,
                modifier = Modifier.fillMaxSize(),
            )
        }
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = label,
            color = JarvisLiveColors.OnBackgroundMuted,
            style = MaterialTheme.typography.labelMedium,
            modifier = Modifier.width(72.dp),
        )
        Spacer(modifier = Modifier.height(4.dp))
        OutlinedButton(onClick = onClick, modifier = Modifier.height(28.dp)) {
            Text("Use", style = MaterialTheme.typography.labelSmall)
        }
    }
}
