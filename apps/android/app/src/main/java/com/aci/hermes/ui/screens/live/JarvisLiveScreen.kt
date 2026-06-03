package com.aci.hermes.ui.screens.live

import android.Manifest
import android.content.pm.PackageManager
import android.speech.SpeechRecognizer
import androidx.compose.ui.platform.LocalContext
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import com.aci.hermes.service.VoiceLoopService
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Brush
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.outlined.Menu
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.ui.theme.HermesCrimson
import com.aci.hermes.ui.theme.HermesCyan
import com.aci.hermes.ui.theme.HermesGold
import com.aci.hermes.ui.theme.HermesInk
import com.aci.hermes.ui.theme.HermesInkSoft
import com.aci.hermes.ui.theme.HermesViolet

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JarvisLiveScreen(
    viewModel: JarvisLiveViewModel,
    onBack: () -> Unit,
    onOpenAvatarPicker: () -> Unit,
    onOpenSettings: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val showStatusSheet by viewModel.showStatusSheet.collectAsState()
    val showEmergencyConfirm by viewModel.showEmergencyConfirm.collectAsState()
    val projection = remember(state) { JarvisLiveStateMapper.project(state) }
    var overflowOpen by remember { mutableStateOf(false) }

    // Hands-free voice: the on-device barge-in loop, started behind RECORD_AUDIO
    // consent. Available only where the device has a speech recognizer.
    val context = LocalContext.current
    val voiceSupported = remember { SpeechRecognizer.isRecognitionAvailable(context) }
    var voiceActive by remember { mutableStateOf(false) }
    val micPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) {
            VoiceLoopService.start(context)
            voiceActive = true
        }
    }
    val onMic: () -> Unit = {
        if (voiceActive) {
            VoiceLoopService.stop(context)
            voiceActive = false
        } else if (
            ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED
        ) {
            VoiceLoopService.start(context)
            voiceActive = true
        } else {
            micPermission.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    LaunchedEffect(Unit) { viewModel.refreshReducedMotion() }

    Scaffold(
        containerColor = HermesInk,
        topBar = {
            JarvisTopBar(
                projection = projection,
                onMenu = onBack,
                onEditAvatar = onOpenAvatarPicker,
                onOverflowToggle = { overflowOpen = !overflowOpen },
                overflowOpen = overflowOpen,
                onOverflowDismiss = { overflowOpen = false },
                onOpenSettings = {
                    overflowOpen = false
                    onOpenSettings()
                },
                onOpenStatusSheet = {
                    overflowOpen = false
                    viewModel.openStatusSheet()
                },
            )
        },
        bottomBar = {
            JarvisCommandBar(
                command = state.command,
                voiceAvailable = voiceSupported,
                voiceActive = voiceActive,
                emergencyActive = projection.isEmergency,
                onCommandChange = viewModel::onCommandChange,
                onSend = viewModel::onSend,
                onAttach = onOpenAvatarPicker,
                onMic = onMic,
            )
        },
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(jarvisBackground()),
        ) {
            JarvisLiveParticles(enabled = projection.particlesEnabled)

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Spacer(Modifier.height(40.dp))

                Box(
                    modifier = Modifier.pointerInput(projection.state) {
                        detectTapGestures(
                            onTap = { viewModel.openStatusSheet() },
                            onDoubleTap = { viewModel.cycleSprite() },
                            onLongPress = { viewModel.requestEmergencyConfirm() },
                        )
                    },
                ) {
                    // The living, breathing body. Priority: a saved photo → a
                    // breathing photo face; reduced motion → the calm Orb; otherwise
                    // a pixel-sprite character (robot/person/pets) that breathes and
                    // reacts to the real agent state. Double-tap cycles characters.
                    val inputs = AvatarAnimation.inputsFor(
                        state = projection.state,
                        behavior = state.avatarBehavior,
                        activeClip = null,
                        motionEnabled = projection.motionEnabled,
                    )
                    val cd = stringResource(projection.contentDescription)
                    val hasRive = remember { riveAvatarAvailable(context) }
                    when {
                        state.avatarPhoto != null -> LivingAvatarHost(
                            kind = AvatarKind.Photo,
                            inputs = inputs,
                            contentDescription = cd,
                            modifier = Modifier.size(220.dp),
                            photo = state.avatarPhoto,
                        )
                        !projection.motionEnabled -> LivingAvatarHost(
                            kind = AvatarKind.Orb,
                            inputs = inputs,
                            contentDescription = cd,
                        )
                        // Top-tier animated art auto-activates when shipped.
                        hasRive -> LivingAvatarHost(
                            kind = AvatarKind.Rive,
                            inputs = inputs,
                            contentDescription = cd,
                            modifier = Modifier.size(240.dp),
                        )
                        else -> PixelSpriteAvatar(
                            sprite = PixelSprites.byId(state.spriteId),
                            inputs = inputs,
                            contentDescription = cd,
                            modifier = Modifier.size(220.dp),
                        )
                    }
                }

                Spacer(Modifier.height(20.dp))

                Text(
                    text = state.voiceLine.ifBlank { stringResource(projection.voiceLineFallback) },
                    color = MaterialTheme.colorScheme.onSurface,
                    style = MaterialTheme.typography.titleMedium,
                    textAlign = TextAlign.Center,
                )

                Spacer(Modifier.height(24.dp))

                if (projection.showApprovalCta) {
                    Button(
                        onClick = viewModel::approveApproval,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = HermesGold,
                            contentColor = HermesInk,
                        ),
                    ) { Text(stringResource(R.string.jarvis_cta_approve)) }
                }
                if (projection.showFixCta) {
                    Button(
                        onClick = { viewModel.openStatusSheet() },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = HermesCrimson,
                            contentColor = Color.White,
                        ),
                    ) { Text(stringResource(R.string.jarvis_cta_fix)) }
                }
                if (projection.showEmergencyReleaseCta) {
                    Button(
                        onClick = viewModel::releaseEmergencyStop,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = HermesCrimson,
                            contentColor = Color.White,
                        ),
                    ) { Text(stringResource(R.string.jarvis_cta_emergency_release)) }
                }
            }
        }
    }

    if (showStatusSheet) {
        val sheetState = rememberModalBottomSheetState()
        ModalBottomSheet(
            onDismissRequest = viewModel::dismissStatusSheet,
            sheetState = sheetState,
            containerColor = HermesInkSoft,
        ) {
            StatusDetailContent(projection = projection)
            Spacer(Modifier.height(16.dp))
        }
    }

    if (showEmergencyConfirm) {
        AlertDialog(
            onDismissRequest = viewModel::dismissEmergencyConfirm,
            title = { Text(stringResource(R.string.jarvis_emergency_dialog_title)) },
            text = { Text(stringResource(R.string.jarvis_emergency_dialog_body)) },
            confirmButton = {
                Button(
                    onClick = viewModel::confirmEmergencyStop,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = HermesCrimson,
                        contentColor = Color.White,
                    ),
                ) { Text(stringResource(R.string.jarvis_cta_emergency_stop)) }
            },
            dismissButton = {
                TextButton(onClick = viewModel::dismissEmergencyConfirm) {
                    Text(stringResource(R.string.action_cancel))
                }
            },
            containerColor = HermesInkSoft,
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun JarvisTopBar(
    projection: JarvisLiveProjection,
    onMenu: () -> Unit,
    onEditAvatar: () -> Unit,
    onOverflowToggle: () -> Unit,
    overflowOpen: Boolean,
    onOverflowDismiss: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenStatusSheet: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .statusBarsPadding()
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        CircleIconButton(
            onClick = onMenu,
            contentDescription = stringResource(R.string.jarvis_menu_cd),
        ) {
            Icon(Icons.Outlined.Menu, contentDescription = null, tint = Color.White)
        }

        JarvisStatusPill(projection = projection)

        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            CircleIconButton(
                onClick = onEditAvatar,
                contentDescription = stringResource(R.string.jarvis_edit_avatar_cd),
            ) {
                Icon(Icons.Default.Brush, contentDescription = null, tint = Color.White)
            }
            Box {
                CircleIconButton(
                    onClick = onOverflowToggle,
                    contentDescription = stringResource(R.string.jarvis_more_cd),
                ) {
                    Icon(Icons.Default.MoreVert, contentDescription = null, tint = Color.White)
                }
                DropdownMenu(
                    expanded = overflowOpen,
                    onDismissRequest = onOverflowDismiss,
                ) {
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.jarvis_overflow_status_detail)) },
                        onClick = onOpenStatusSheet,
                    )
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.nav_settings)) },
                        onClick = onOpenSettings,
                    )
                }
            }
        }
    }
}

@Composable
private fun JarvisStatusPill(projection: JarvisLiveProjection) {
    val (bg, fg) = pillColorsFor(projection.state)
    val description = stringResource(R.string.jarvis_status_pill_cd, stringResource(projection.pillText))
    Surface(
        shape = RoundedCornerShape(50),
        color = bg,
        modifier = Modifier
            .padding(horizontal = 12.dp)
            .clip(RoundedCornerShape(50)),
    ) {
        Row(
            modifier = Modifier
                .padding(horizontal = 16.dp, vertical = 8.dp)
                .semantics { contentDescription = description },
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Surface(
                shape = CircleShape,
                color = fg,
                modifier = Modifier.size(8.dp),
            ) {}
            Text(
                text = stringResource(projection.pillText),
                color = fg,
                style = MaterialTheme.typography.labelLarge,
            )
        }
    }
}

private fun pillColorsFor(state: JarvisLiveState): Pair<Color, Color> = when (state) {
    JarvisLiveState.Idle -> HermesInkSoft to HermesGold.copy(alpha = 0.85f)
    JarvisLiveState.Listening -> HermesInkSoft to HermesCyan
    JarvisLiveState.Thinking -> HermesViolet.copy(alpha = 0.25f) to HermesGold
    JarvisLiveState.Working -> HermesGold.copy(alpha = 0.18f) to HermesGold
    JarvisLiveState.Speaking -> HermesCyan.copy(alpha = 0.20f) to HermesCyan
    JarvisLiveState.ApprovalNeeded -> HermesGold.copy(alpha = 0.30f) to HermesGold
    JarvisLiveState.Blocked -> HermesCrimson.copy(alpha = 0.30f) to Color.White
    JarvisLiveState.EmergencyStop -> HermesCrimson to Color.White
}

@Composable
private fun CircleIconButton(
    onClick: () -> Unit,
    contentDescription: String,
    content: @Composable () -> Unit,
) {
    Surface(
        shape = CircleShape,
        color = Color.Black.copy(alpha = 0.55f),
        modifier = Modifier.size(44.dp),
    ) {
        IconButton(
            onClick = onClick,
            modifier = Modifier.semantics {
                this.contentDescription = contentDescription
            },
        ) { content() }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun JarvisCommandBar(
    command: String,
    voiceAvailable: Boolean,
    voiceActive: Boolean,
    emergencyActive: Boolean,
    onCommandChange: (String) -> Unit,
    onSend: () -> Unit,
    onAttach: () -> Unit,
    onMic: () -> Unit,
) {
    Surface(
        color = Color.Transparent,
        modifier = Modifier
            .fillMaxWidth()
            .navigationBarsPadding()
            .imePadding()
            .padding(horizontal = 12.dp, vertical = 12.dp),
    ) {
        Surface(
            shape = RoundedCornerShape(28.dp),
            color = HermesInkSoft,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                IconButton(
                    onClick = onAttach,
                    modifier = Modifier.semantics {
                        contentDescription = "Add avatar or attachment"
                    },
                ) {
                    Icon(Icons.Default.Add, contentDescription = null, tint = Color.White)
                }
                TextField(
                    value = command,
                    onValueChange = onCommandChange,
                    modifier = Modifier.weight(1f),
                    placeholder = { Text(stringResource(R.string.jarvis_input_hint)) },
                    singleLine = true,
                    enabled = !emergencyActive,
                    colors = TextFieldDefaults.colors(
                        focusedContainerColor = Color.Transparent,
                        unfocusedContainerColor = Color.Transparent,
                        disabledContainerColor = Color.Transparent,
                        focusedIndicatorColor = Color.Transparent,
                        unfocusedIndicatorColor = Color.Transparent,
                        disabledIndicatorColor = Color.Transparent,
                    ),
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                )
                IconButton(
                    onClick = onMic,
                    enabled = voiceAvailable && !emergencyActive,
                    modifier = Modifier.semantics {
                        contentDescription = when {
                            !voiceAvailable -> "Voice input unavailable on this device"
                            voiceActive -> "Stop hands-free voice"
                            else -> "Start hands-free voice"
                        }
                    },
                ) {
                    Icon(
                        Icons.Default.Mic,
                        contentDescription = null,
                        tint = when {
                            voiceActive -> HermesCyan
                            voiceAvailable -> HermesCyan.copy(alpha = 0.7f)
                            else -> Color.White.copy(alpha = 0.30f)
                        },
                    )
                }
                IconButton(
                    onClick = onSend,
                    enabled = command.isNotBlank() && !emergencyActive,
                    modifier = Modifier.semantics {
                        contentDescription = "Send command"
                    },
                ) {
                    val tint = if (command.isNotBlank() && !emergencyActive) HermesGold
                               else Color.White.copy(alpha = 0.30f)
                    Icon(
                        if (emergencyActive) Icons.Default.Stop else Icons.AutoMirrored.Filled.Send,
                        contentDescription = null,
                        tint = tint,
                    )
                }
            }
        }
    }
}

@Composable
private fun StatusDetailContent(projection: JarvisLiveProjection) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            stringResource(R.string.jarvis_status_sheet_title),
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.onSurface,
        )
        Text(
            stringResource(projection.pillText),
            style = MaterialTheme.typography.headlineSmall,
            color = HermesGold,
        )
        Text(
            stringResource(projection.voiceLineFallback),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurface,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            AssistChip(
                onClick = {},
                label = { Text(stringResource(R.string.jarvis_motion_label)) },
                trailingIcon = {
                    Text(
                        if (projection.motionEnabled) "On" else "Off",
                        color = if (projection.motionEnabled) HermesCyan else MaterialTheme.colorScheme.onSurface,
                    )
                },
                colors = AssistChipDefaults.assistChipColors(
                    containerColor = HermesInk,
                    labelColor = MaterialTheme.colorScheme.onSurface,
                ),
            )
            AssistChip(
                onClick = {},
                label = { Text(stringResource(R.string.jarvis_particles_label)) },
                trailingIcon = {
                    Text(
                        if (projection.particlesEnabled) "On" else "Off",
                        color = if (projection.particlesEnabled) HermesCyan else MaterialTheme.colorScheme.onSurface,
                    )
                },
                colors = AssistChipDefaults.assistChipColors(
                    containerColor = HermesInk,
                    labelColor = MaterialTheme.colorScheme.onSurface,
                ),
            )
        }
    }
}

@Composable
private fun jarvisBackground(): Brush = Brush.radialGradient(
    colors = listOf(
        HermesViolet.copy(alpha = 0.45f),
        HermesInkSoft,
        HermesInk,
    ),
    center = Offset(540f, 360f),
    radius = 1600f,
)
