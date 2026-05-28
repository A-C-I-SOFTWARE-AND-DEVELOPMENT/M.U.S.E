package com.aci.hermes.ui.screens.live

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.ui.jarvis.JarvisLivingAvatar
import com.aci.hermes.ui.jarvis.JarvisLivingAvatarDimens
import com.aci.hermes.ui.jarvis.LocalReduceMotion

/**
 * Full-screen Jarvis Live command screen.
 *
 * Layout:
 *  - Top app bar: title "Jarvis", back arrow.
 *  - Large central living avatar (192 dp).
 *  - Status text below the avatar — "Jarvis is …" — resolved from
 *    the avatar render spec's `statusStringResId`.
 *  - Background: deep navy (`JarvisLiveColors.Background`).
 *
 * No new permission needed. The screen is read-only — it does not
 * trigger any owner-gated action. Emergency stop, when engaged,
 * surfaces here as the `BLOCKED` icon-state and the
 * `avatar_status_blocked` status string.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JarvisLiveScreen(
    viewModel: JarvisLiveViewModel,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val spec by viewModel.renderSpec.collectAsState()

    CompositionLocalProvider(LocalReduceMotion provides spec.reducedMotion) {
        Scaffold(
            modifier = modifier,
            containerColor = JarvisLiveColors.Background,
            topBar = {
                TopAppBar(
                    title = {
                        Text(
                            text = stringResource(R.string.app_name),
                            color = JarvisLiveColors.OnBackground,
                            fontWeight = FontWeight.SemiBold,
                        )
                    },
                    navigationIcon = {
                        IconButton(onClick = onBack) {
                            Icon(
                                imageVector = Icons.Filled.ArrowBack,
                                contentDescription = stringResource(R.string.action_back),
                                tint = JarvisLiveColors.OnBackground,
                            )
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = JarvisLiveColors.Background,
                        titleContentColor = JarvisLiveColors.OnBackground,
                    ),
                )
            },
        ) { padding ->
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .background(JarvisLiveColors.Background),
                contentAlignment = Alignment.Center,
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) {
                    JarvisLivingAvatar(
                        spec = spec,
                        size = JarvisLivingAvatarDimens.FullScreen,
                    )
                    Spacer(modifier = Modifier.height(32.dp))
                    Text(
                        text = stringResource(spec.statusStringResId),
                        color = JarvisLiveColors.OnBackground,
                        fontWeight = FontWeight.Medium,
                        style = MaterialTheme.typography.titleLarge,
                    )
                }
            }
        }
    }
}
