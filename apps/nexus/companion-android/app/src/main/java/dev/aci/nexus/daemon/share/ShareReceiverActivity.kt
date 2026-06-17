package dev.aci.nexus.daemon.share

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import dev.aci.nexus.daemon.net.MuseClient
import dev.aci.nexus.daemon.service.Credentials
import kotlin.concurrent.thread

/** Share-sheet target: "Send to M.U.S.E." — turns shared text/links into a goal. */
class ShareReceiverActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val text = intent?.getStringExtra(Intent.EXTRA_TEXT)
        val creds = Credentials.load(this)
        if (text.isNullOrBlank() || creds == null) {
            Toast.makeText(this, "NEXUS not paired", Toast.LENGTH_SHORT).show()
            finish()
            return
        }
        thread {
            runCatching { MuseClient(creds.baseUrl, creds.token).sendGoal(text) }
            runOnUiThread {
                Toast.makeText(this, "Sent to M.U.S.E.", Toast.LENGTH_SHORT).show()
                finish()
            }
        }
    }
}
