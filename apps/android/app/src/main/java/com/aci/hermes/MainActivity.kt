package com.aci.hermes

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import com.aci.hermes.data.preferences.ThemeMode
import com.aci.hermes.ui.navigation.HermesNavHost
import com.aci.hermes.ui.theme.HermesTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val container = (application as HermesApplication).container

        setContent {
            val themePref by container.settingsRepository.themeMode.collectAsState(
                initial = ThemeMode.SYSTEM
            )
            HermesTheme(themeMode = themePref) {
                HermesNavHost(container = container)
            }
        }
    }
}
