package dev.aci.nexus.daemon.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import dev.aci.nexus.daemon.service.Credentials
import dev.aci.nexus.daemon.service.DaemonService
import dev.aci.nexus.daemon.tile.DaemonState

/**
 * The daemon's ONLY screen: pairing (base URL + token + PWA host) and a
 * start/stop toggle. Deliberately not a console — that lives in the PWA.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = darkColorScheme(background = Color(0xFF0A0E14))) {
                Surface(modifier = Modifier.fillMaxSize(), color = Color(0xFF0A0E14)) {
                    PairingScreen(
                        existing = Credentials.load(this),
                        running = DaemonState.isRunning(this),
                        onSave = { creds ->
                            Credentials.save(this, creds)
                            DaemonService.start(this)
                            DaemonState.setRunning(this, true)
                        },
                        onStop = {
                            DaemonService.stop(this)
                            DaemonState.setRunning(this, false)
                        },
                    )
                }
            }
        }
    }
}

@androidx.compose.runtime.Composable
private fun PairingScreen(
    existing: Credentials?,
    running: Boolean,
    onSave: (Credentials) -> Unit,
    onStop: () -> Unit,
) {
    var base by remember { mutableStateOf(existing?.baseUrl ?: "") }
    var token by remember { mutableStateOf(existing?.token ?: "") }
    var host by remember { mutableStateOf(existing?.pwaHost ?: "") }

    Column(
        modifier = Modifier.fillMaxSize().padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("NEXUS Daemon", color = Color(0xFFE6EDF3), style = MaterialTheme.typography.headlineSmall)
        Text(
            "Pair with your M.U.S.E. gateway. Status + authorization run in the background.",
            color = Color(0xFF8499AD),
            style = MaterialTheme.typography.bodySmall,
        )
        OutlinedTextField(base, { base = it }, label = { Text("M.U.S.E. base URL") })
        OutlinedTextField(
            token, { token = it }, label = { Text("Token") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
        )
        OutlinedTextField(host, { host = it }, label = { Text("NEXUS PWA host") })
        Button(
            onClick = { onSave(Credentials(base.trim(), token.trim(), host.trim().ifEmpty { base.trim() })) },
            enabled = base.isNotBlank() && token.isNotBlank(),
        ) { Text(if (running) "Re-pair & restart" else "Pair & start daemon") }
        if (running) {
            Button(onClick = onStop) { Text("Stop daemon") }
        }
    }
}
