package com.aci.hermes.ui.screens.avatar

import android.graphics.BitmapFactory
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.material3.Surface
import com.aci.hermes.ui.screens.live.AvatarInputs
import com.aci.hermes.ui.screens.live.AvatarPose
import com.aci.hermes.ui.screens.live.PixelSpriteAvatar
import com.aci.hermes.ui.screens.live.PixelSprites
import androidx.compose.foundation.Image
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.avatar.AvatarProfile
import com.aci.hermes.data.avatar.AvatarSource
import com.aci.hermes.data.avatar.AvatarStyle
import com.aci.hermes.data.avatar.JarvisBuiltin
import com.aci.hermes.data.avatar.PixelSize

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AvatarPickerScreen(
    viewModel: AvatarPickerViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val selectedSpriteId by viewModel.selectedSpriteId.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Jarvis avatar") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("Characters", style = MaterialTheme.typography.titleMedium)
            CharacterGrid(
                selectedId = selectedSpriteId,
                onSelect = viewModel::selectSprite,
            )

            BuiltInGrid(
                selected = (state as? AvatarPickerState.PreviewReady)?.draft?.builtin,
                onSelect = viewModel::selectBuiltIn,
            )

            val photoLauncher = rememberLauncherForActivityResult(
                ActivityResultContracts.PickVisualMedia(),
            ) { uri -> viewModel.onPhotoPicked(uri) }

            Button(
                onClick = {
                    photoLauncher.launch(
                        PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly),
                    )
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Choose photo")
            }

            PixelSizeSelector(
                current = currentPixelSize(state),
                onChange = viewModel::setPixelSize,
            )

            StyleSelector(
                current = currentStyle(state),
                onChange = viewModel::setStyle,
            )

            PreviewArea(state)

            Text(
                text = "Processed on device. Stored locally. Not uploaded.",
                style = MaterialTheme.typography.bodySmall,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Button(
                    onClick = viewModel::save,
                    enabled = state is AvatarPickerState.PreviewReady,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Save")
                }
                OutlinedButton(
                    onClick = viewModel::reset,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Delete / Reset")
                }
            }

            (state as? AvatarPickerState.Error)?.let {
                Text(
                    text = it.message,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}

/** The redone "main selection" — a scrollable row of living pixel characters
 *  (robot/person/pets). Tapping one persists it as the avatar immediately. */
@Composable
private fun CharacterGrid(
    selectedId: String?,
    onSelect: (String) -> Unit,
) {
    val inputs = AvatarInputs(pose = AvatarPose.IDLE, energy = 0.45f, motionEnabled = true)
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        PixelSprites.catalog.forEach { sprite ->
            val selected = sprite.id == (selectedId ?: PixelSprites.default.id)
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Surface(
                    shape = RoundedCornerShape(16.dp),
                    color = MaterialTheme.colorScheme.surfaceVariant,
                    border = if (selected) {
                        BorderStroke(2.dp, MaterialTheme.colorScheme.primary)
                    } else {
                        null
                    },
                    modifier = Modifier
                        .size(80.dp)
                        .clickable { onSelect(sprite.id) },
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        PixelSpriteAvatar(
                            sprite = sprite,
                            inputs = inputs,
                            contentDescription = sprite.label,
                            modifier = Modifier.size(64.dp),
                        )
                    }
                }
                Text(sprite.label, style = MaterialTheme.typography.labelSmall)
            }
        }
    }
}

@Composable
private fun BuiltInGrid(
    selected: JarvisBuiltin?,
    onSelect: (JarvisBuiltin) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Built-in avatars", style = MaterialTheme.typography.titleMedium)
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            JarvisBuiltin.entries.forEach { item ->
                BuiltInCard(
                    item = item,
                    selected = selected == item,
                    onClick = { onSelect(item) },
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun BuiltInCard(
    item: JarvisBuiltin,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val borderColor = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline
    val borderWidth = if (selected) 2.dp else 1.dp
    Card(
        onClick = onClick,
        border = BorderStroke(borderWidth, borderColor),
        modifier = modifier.height(96.dp),
    ) {
        Column(
            modifier = Modifier.fillMaxSize().padding(8.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp, Alignment.CenterVertically),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Icon(
                imageVector = builtInIcon(item),
                contentDescription = builtInLabel(item),
                modifier = Modifier.size(36.dp),
            )
            Text(
                builtInLabel(item),
                style = MaterialTheme.typography.labelSmall,
                textAlign = TextAlign.Center,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PixelSizeSelector(current: PixelSize, onChange: (PixelSize) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text("Pixel size", style = MaterialTheme.typography.titleSmall)
        SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
            val values = PixelSize.entries
            values.forEachIndexed { index, size ->
                SegmentedButton(
                    selected = current == size,
                    onClick = { onChange(size) },
                    shape = SegmentedButtonDefaults.itemShape(index = index, count = values.size),
                ) { Text(pixelSizeLabel(size)) }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun StyleSelector(current: AvatarStyle, onChange: (AvatarStyle) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text("Style", style = MaterialTheme.typography.titleSmall)
        SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
            val values = AvatarStyle.entries
            values.forEachIndexed { index, style ->
                SegmentedButton(
                    selected = current == style,
                    onClick = { onChange(style) },
                    shape = SegmentedButtonDefaults.itemShape(index = index, count = values.size),
                ) { Text(styleLabel(style)) }
            }
        }
    }
}

@Composable
private fun PreviewArea(state: AvatarPickerState) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(280.dp)
            .border(
                width = 1.dp,
                color = MaterialTheme.colorScheme.outline,
                shape = RoundedCornerShape(8.dp),
            ),
        contentAlignment = Alignment.Center,
    ) {
        when (state) {
            is AvatarPickerState.Processing -> {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    CircularProgressIndicator()
                    Spacer(Modifier.height(8.dp))
                    Text("Processing locally…", style = MaterialTheme.typography.bodySmall)
                }
            }
            is AvatarPickerState.PreviewReady -> RenderPreview(state.previewFile, state.draft)
            is AvatarPickerState.Saved -> RenderPreview(savedPreviewFile(state.profile), state.profile)
            is AvatarPickerState.Error -> Text("Preview unavailable", style = MaterialTheme.typography.bodyMedium)
            AvatarPickerState.Idle -> Text(
                "Pick a built-in avatar or choose a photo",
                style = MaterialTheme.typography.bodyMedium,
                textAlign = TextAlign.Center,
            )
        }
    }
}

@Composable
private fun RenderPreview(file: java.io.File?, draft: AvatarProfile) {
    when (draft.source) {
        AvatarSource.BUILTIN -> {
            val builtin = draft.builtin
            if (builtin != null) {
                Icon(
                    imageVector = builtInIcon(builtin),
                    contentDescription = builtInLabel(builtin),
                    modifier = Modifier.size(192.dp),
                )
            }
        }
        AvatarSource.GENERATED -> {
            val bitmap = remember(file?.absolutePath, file?.lastModified()) {
                file?.takeIf { it.exists() }?.let { BitmapFactory.decodeFile(it.absolutePath) }
            }
            if (bitmap != null) {
                Image(
                    bitmap = bitmap.asImageBitmap(),
                    contentDescription = "Generated pixel avatar",
                    modifier = Modifier.size(256.dp),
                )
            } else {
                Text("Preview unavailable", style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

private fun savedPreviewFile(profile: AvatarProfile): java.io.File? =
    profile.generatedPath?.let { java.io.File(it) }?.takeIf { it.exists() }

private fun currentPixelSize(state: AvatarPickerState): PixelSize = when (state) {
    is AvatarPickerState.PreviewReady -> state.draft.pixelSize
    is AvatarPickerState.Saved -> state.profile.pixelSize
    else -> PixelSize.BALANCED_32
}

private fun currentStyle(state: AvatarPickerState): AvatarStyle = when (state) {
    is AvatarPickerState.PreviewReady -> state.draft.style
    is AvatarPickerState.Saved -> state.profile.style
    else -> AvatarStyle.NAVY_GOLD
}

private fun builtInIcon(item: JarvisBuiltin): ImageVector = when (item) {
    JarvisBuiltin.GUARDIAN_SHIELD -> Icons.Filled.Shield
    JarvisBuiltin.FAST_WORKER_BOLT -> Icons.Filled.Bolt
    JarvisBuiltin.KNOWLEDGE_MEMORY -> Icons.Filled.Memory
    JarvisBuiltin.COMMAND_AUTO -> Icons.Filled.AutoAwesome
}

private fun builtInLabel(item: JarvisBuiltin): String = when (item) {
    JarvisBuiltin.GUARDIAN_SHIELD -> "Guardian"
    JarvisBuiltin.FAST_WORKER_BOLT -> "Fast worker"
    JarvisBuiltin.KNOWLEDGE_MEMORY -> "Knowledge"
    JarvisBuiltin.COMMAND_AUTO -> "Command"
}

private fun pixelSizeLabel(size: PixelSize): String = when (size) {
    PixelSize.CHUNKY_16 -> "16 chunky"
    PixelSize.BALANCED_32 -> "32 balanced"
    PixelSize.DETAILED_48 -> "48 detailed"
}

private fun styleLabel(style: AvatarStyle): String = when (style) {
    AvatarStyle.NONE -> "Original"
    AvatarStyle.NAVY_GOLD -> "Navy/Gold"
    AvatarStyle.CYAN_GLOW -> "Cyan glow"
    AvatarStyle.MONOCHROME_TERMINAL -> "Terminal"
}

