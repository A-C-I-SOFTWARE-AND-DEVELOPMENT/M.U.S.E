package dev.aci.nexus.daemon.widget

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.appwidget.AppWidgetManager
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.glance.GlanceId
import androidx.glance.GlanceModifier
import androidx.glance.action.actionStartActivity
import androidx.glance.action.clickable
import androidx.glance.appwidget.GlanceAppWidget
import androidx.glance.appwidget.GlanceAppWidgetReceiver
import androidx.glance.appwidget.provideContent
import androidx.glance.background
import androidx.glance.layout.Alignment
import androidx.glance.layout.Column
import androidx.glance.layout.Row
import androidx.glance.layout.fillMaxSize
import androidx.glance.layout.padding
import androidx.glance.text.Text
import androidx.glance.text.TextStyle
import androidx.glance.unit.ColorProvider

/**
 * Compact agent-status board (idle/running/error/needs-auth). Tapping deep-links
 * into the installed PWA. Reads only the cached snapshot — no network here.
 */
class StatusWidget : GlanceAppWidget() {
    override suspend fun provideGlance(context: Context, id: GlanceId) {
        val snap = StatusStore.load(context)
        provideContent {
            WidgetBody(snap.running, snap.error, snap.needsAuth, snap.idle)
        }
    }
}

@Composable
private fun WidgetBody(running: Int, error: Int, needsAuth: Int, idle: Int) {
    val open = actionStartActivity(
        Intent(Intent.ACTION_VIEW, Uri.parse("https://nexus.local/agents"))
    )
    Column(
        modifier = GlanceModifier
            .fillMaxSize()
            .background(Color(0xFF0A0E14))
            .padding(12.dp)
            .clickable(open),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text("NEXUS", style = TextStyle(color = ColorProvider(Color(0xFFE6EDF3))))
        Row {
            Counter("RUN", running, Color(0xFF34E5C8))
            Counter("ERR", error, Color(0xFFFF5470))
            Counter("AUTH", needsAuth, Color(0xFFFFB020))
            Counter("IDLE", idle, Color(0xFF5A6B7D))
        }
    }
}

@Composable
private fun Counter(label: String, value: Int, color: Color) {
    Column(modifier = GlanceModifier.padding(6.dp)) {
        Text("$value", style = TextStyle(color = ColorProvider(color)))
        Text(label, style = TextStyle(color = ColorProvider(Color(0xFF8499AD))))
    }
}

class StatusWidgetReceiver : GlanceAppWidgetReceiver() {
    override val glanceAppWidget: GlanceAppWidget = StatusWidget()

    companion object {
        fun requestUpdate(ctx: Context) {
            val mgr = AppWidgetManager.getInstance(ctx)
            val ids = mgr.getAppWidgetIds(
                android.content.ComponentName(ctx, StatusWidgetReceiver::class.java)
            )
            val i = Intent(AppWidgetManager.ACTION_APPWIDGET_UPDATE).apply {
                setClass(ctx, StatusWidgetReceiver::class.java)
                putExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS, ids)
            }
            ctx.sendBroadcast(i)
        }
    }
}
