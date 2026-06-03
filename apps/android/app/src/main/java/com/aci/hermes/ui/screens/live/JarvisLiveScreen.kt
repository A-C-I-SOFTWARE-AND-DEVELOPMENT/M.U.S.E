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
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.activity.result.contract.ActivityResultContracts.StartActivityForResult
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.offset
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.IntOffset
import kotlin.math.roundToInt
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.PictureInPictureAlt
import androidx.compose.ui.draw.scale
import com.aci.hermes.data.life.AvatarBehavior
import com.aci.hermes.service.JarvisOverlayService
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
    onOpenApprovals: () -> Unit = {},
    onOpenCurrentJob: (String?) -> Unit = {},
) {
    val state by viewModel.state.collectAsState()
    val furniture by viewModel.furniture.collectAsState()
    val showStatusSheet by viewModel.showStatusSheet.collectAsState()
    val showEmergencyConfirm by viewModel.showEmergencyConfirm.collectAsState()
    val currentJobId by viewModel.currentJobId.collectAsState()
    val presenceEnabled by viewModel.presenceEnabled.collectAsState()
    val presenceState by viewModel.presenceState.collectAsState()
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

    fun hasMic() = ContextCompat.checkSelfPermission(
        context, Manifest.permission.RECORD_AUDIO,
    ) == PackageManager.PERMISSION_GRANTED

    // Tap-to-talk / mic fallback: open the mic now, behind RECORD_AUDIO consent.
    val talkPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted -> if (granted) viewModel.talkNow() }
    val onTapToTalk: () -> Unit = {
        if (hasMic()) viewModel.talkNow() else talkPermission.launch(Manifest.permission.RECORD_AUDIO)
    }

    // Toggling Presence Mode on arms the wake word (needs the mic); off is free.
    val presencePermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted -> if (granted) viewModel.togglePresenceMode() }
    val onTogglePresence: () -> Unit = {
        if (presenceEnabled || hasMic()) viewModel.togglePresenceMode()
        else presencePermission.launch(Manifest.permission.RECORD_AUDIO)
    }

    // Float JARVIS over other apps: start the overlay service behind the
    // draw-over-other-apps consent (a high-risk permission granted in Settings).
    var overlayOn by remember { mutableStateOf(JarvisOverlayService.active != null) }
    val overlayPermission = rememberLauncherForActivityResult(StartActivityForResult()) {
        if (JarvisOverlayService.canDraw(context)) {
            JarvisOverlayService.start(context)
            overlayOn = true
        }
    }
    val onToggleOverlay: () -> Unit = {
        when {
            overlayOn -> {
                JarvisOverlayService.stop(context)
                overlayOn = false
            }
            JarvisOverlayService.canDraw(context) -> {
                JarvisOverlayService.start(context)
                overlayOn = true
            }
            else -> overlayPermission.launch(
                Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + context.packageName),
                ),
            )
        }
    }
    // Mirror the live agent state onto the floating avatar while it's showing.
    LaunchedEffect(projection.state, overlayOn) {
        if (overlayOn) JarvisOverlayService.active?.setLiveState(projection.state)
    }

    LaunchedEffect(Unit) { viewModel.refreshReducedMotion() }

    Scaffold(
        containerColor = HermesInk,
        topBar = {
            JarvisTopBar(
                projection = projection,
                presenceEnabled = presenceEnabled,
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
                onTogglePresence = {
                    overflowOpen = false
                    onTogglePresence()
                },
                onCycleSprite = {
                    overflowOpen = false
                    viewModel.cycleSprite()
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
                .background(jarvisBackground())
                // Swipe left → jump to the current job (Tasks when none is active).
                .pointerInput(currentJobId) {
                    detectHorizontalDragGestures { _, dragAmount ->
                        if (dragAmount < -SWIPE_TO_JOB_THRESHOLD) onOpenCurrentJob(currentJobId)
                    }
                },
        ) {
            // The companion's pixel bedroom (wall, window, desk, bed, plant).
            PixelRoom(modifier = Modifier.fillMaxSize())

            // AI-generated furniture, draggable; placement persists.
            DenFurnitureLayer(
                furniture = furniture,
                onPlaced = viewModel::placeFurniture,
            )

            JarvisLiveParticles(enabled = projection.particlesEnabled)

            // Toggle the floating JARVIS that lives over every app.
            IconButton(
                onClick = onToggleOverlay,
                modifier = Modifier.align(Alignment.TopEnd).padding(8.dp),
            ) {
                Icon(
                    Icons.Default.PictureInPictureAlt,
                    contentDescription = if (overlayOn) {
                        "Stop floating JARVIS over other apps"
                    } else {
                        "Float JARVIS over other apps"
                    },
                    tint = if (overlayOn) HermesCyan else Color.White.copy(alpha = 0.6f),
                )
            }

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Spacer(Modifier.height(40.dp))

                // The companion walks around its room: to the desk when working,
                // strolls when wandering, and down to the bed to snooze — gliding
                // (tween) so it reads as walking, not teleporting.
                val sleeping = state.avatarBehavior == AvatarBehavior.SLEEP
                val wandering = state.avatarBehavior == AvatarBehavior.WANDER
                val working = projection.state == JarvisLiveState.Working
                val sway by rememberInfiniteTransition(label = "stroll").animateFloat(
                    initialValue = -1f,
                    targetValue = 1f,
                    animationSpec = infiniteRepeatable(tween(5200), RepeatMode.Reverse),
                    label = "sway",
                )
                val glideDx by animateFloatAsState(
                    targetValue = if (working) 96f else 0f,
                    animationSpec = tween(1100),
                    label = "walk-x",
                )
                val walkX = if (wandering && projection.motionEnabled) sway * 92f else glideDx
                val walkY by animateFloatAsState(
                    targetValue = when {
                        sleeping -> 200f          // down onto the bed mat
                        working -> 28f            // settle at the desk
                        else -> 0f
                    },
                    animationSpec = tween(1100),
                    label = "walk-y",
                )
                val bodyScale by animateFloatAsState(
                    targetValue = if (sleeping) 0.58f else 1f,
                    animationSpec = tween(900),
                    label = "body-scale",
                )
                Box(
                    modifier = Modifier
                        .offset(x = walkX.dp, y = walkY.dp)
                        .scale(bodyScale)
                        .pointerInput(projection.state) {
                            detectTapGestures(
                                // Presence-Mode interaction model: tap to talk,
                                // double-tap for status, long-press to stop.
                                onTap = { onTapToTalk() },
                                onDoubleTap = { viewModel.openStatusSheet() },
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
                    text = if (sleeping) {
                        "Snoozing… 💤"
                    } else {
                        state.voiceLine.ifBlank { stringResource(projection.voiceLineFallback) }
                    },
                    color = MaterialTheme.colorScheme.onSurface,
                    style = MaterialTheme.typography.titleMedium,
                    textAlign = TextAlign.Center,
                )

                // Hands-free Presence Mode status — a real label, never just an
                // animation, so the listening state is conveyed accessibly.
                if (presenceEnabled) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        text = stringResource(presenceLabelFor(presenceState)),
                        color = HermesCyan,
                        style = MaterialTheme.typography.labelMedium,
                        textAlign = TextAlign.Center,
                    )
                }

                Spacer(Modifier.height(24.dp))

                if (projection.showApprovalCta) {
                    // Do NOT approve from the avatar — route to the gated
                    // Approvals screen which enforces the owner phrase.
                    Button(
                        onClick = onOpenApprovals,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = HermesGold,
                            contentColor = HermesInk,
                        ),
                    ) { Text(stringResource(R.string.jarvis_cta_open_approvals)) }
                }
                if (projection.showFixCta) {
                    Button(
                        onClick = { onOpenCurrentJob(currentJobId) },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = HermesCrimson,
                            contentColor = Color.White,
                        ),
                    ) { Text(stringResource(R.string.jarvis_cta_fix)) }
                }
                if (projection.showWarningCta) {
                    Button(
                        onClick = { onOpenCurrentJob(currentJobId) },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = HermesGold,
                            contentColor = HermesInk,
                        ),
                    ) { Text(stringResource(R.string.jarvis_cta_warning)) }
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

/** Renders AI-generated furniture in the Den; each piece is draggable and its
 *  placement persists to the runtime on release. */
@Composable
private fun DenFurnitureLayer(
    furniture: List<JarvisLiveViewModel.DenFurniture>,
    onPlaced: (String, Float, Float) -> Unit,
) {
    BoxWithConstraints(modifier = Modifier.fillMaxSize()) {
        val wPx = constraints.maxWidth.toFloat()
        val hPx = constraints.maxHeight.toFloat()
        val itemPx = with(LocalDensity.current) { 72.dp.toPx() }
        furniture.forEach { item ->
            var pos by remember(item.id) {
                mutableStateOf(Offset(item.x * wPx, item.y * hPx))
            }
            Image(
                bitmap = item.bitmap.asImageBitmap(),
                contentDescription = item.id,
                modifier = Modifier
                    .size(72.dp)
                    .offset {
                        IntOffset(
                            (pos.x - itemPx / 2f).roundToInt(),
                            (pos.y - itemPx / 2f).roundToInt(),
                        )
                    }
                    .pointerInput(item.id) {
                        detectDragGestures(
                            onDrag = { change, drag ->
                                change.consume()
                                pos = Offset(pos.x + drag.x, pos.y + drag.y)
                            },
                            onDragEnd = {
                                onPlaced(
                                    item.id,
                                    (pos.x / wPx).coerceIn(0f, 1f),
                                    (pos.y / hPx).coerceIn(0f, 1f),
                                )
                            },
                        )
                    },
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun JarvisTopBar(
    projection: JarvisLiveProjection,
    presenceEnabled: Boolean,
    onMenu: () -> Unit,
    onEditAvatar: () -> Unit,
    onOverflowToggle: () -> Unit,
    overflowOpen: Boolean,
    onOverflowDismiss: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenStatusSheet: () -> Unit,
    onTogglePresence: () -> Unit,
    onCycleSprite: () -> Unit,
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

        JarvisStatusPill(projection = projection, onClick = onOpenStatusSheet)

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
                        text = {
                            Text(
                                stringResource(
                                    if (presenceEnabled) {
                                        R.string.jarvis_presence_toggle_off
                                    } else {
                                        R.string.jarvis_presence_toggle_on
                                    },
                                ),
                            )
                        },
                        onClick = onTogglePresence,
                    )
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.jarvis_overflow_change_companion)) },
                        onClick = onCycleSprite,
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun JarvisStatusPill(projection: JarvisLiveProjection, onClick: () -> Unit) {
    val (bg, fg) = pillColorsFor(projection.state)
    val description = stringResource(R.string.jarvis_status_pill_cd, stringResource(projection.pillText))
    Surface(
        shape = RoundedCornerShape(50),
        color = bg,
        onClick = onClick,
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
    JarvisLiveState.Researching -> HermesViolet.copy(alpha = 0.25f) to HermesCyan
    JarvisLiveState.Coding -> HermesGold.copy(alpha = 0.18f) to HermesGold
    JarvisLiveState.Reviewing -> HermesCyan.copy(alpha = 0.18f) to HermesCyan
    JarvisLiveState.Working -> HermesGold.copy(alpha = 0.18f) to HermesGold
    JarvisLiveState.Speaking -> HermesCyan.copy(alpha = 0.20f) to HermesCyan
    JarvisLiveState.ApprovalNeeded -> HermesGold.copy(alpha = 0.30f) to HermesGold
    JarvisLiveState.Blocked -> HermesCrimson.copy(alpha = 0.30f) to Color.White
    JarvisLiveState.Warning -> HermesGold.copy(alpha = 0.35f) to HermesGold
    JarvisLiveState.Disconnected -> HermesInkSoft to Color.White.copy(alpha = 0.7f)
    JarvisLiveState.EmergencyStop -> HermesCrimson to Color.White
}

/** Horizontal drag (px) past which a left-swipe opens the current job. */
private const val SWIPE_TO_JOB_THRESHOLD = 120f

private fun presenceLabelFor(state: com.aci.hermes.voice.PresenceState): Int = when (state) {
    com.aci.hermes.voice.PresenceState.OFF,
    com.aci.hermes.voice.PresenceState.ARMED -> R.string.jarvis_presence_armed
    com.aci.hermes.voice.PresenceState.LISTENING -> R.string.jarvis_presence_listening
    com.aci.hermes.voice.PresenceState.THINKING -> R.string.jarvis_presence_thinking
    com.aci.hermes.voice.PresenceState.SPEAKING -> R.string.jarvis_presence_speaking
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
