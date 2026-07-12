// ============================================================================
// Auto-sync to MUSE on device, at launch.
//
// Best-effort and silent: when a MUSE gateway is reachable on THIS device (the
// app served same-origin by the gateway — e.g. Termux serving NEXUS — or a
// gateway this device already paired with), reconnect and pull the owner's
// existing providers & API keys so every model/provider from their Hermes
// install is available here too, with nothing to re-type.
//
// This never bypasses the owner gate: first-time device pairing still needs the
// owner phrase via the Connect wizard. Here we only (a) reconnect with an
// existing device token, (b) pre-fill a same-origin gateway, and (c) import the
// owner's keys once a paired/same-origin gateway answers.
// ============================================================================

import { detectSameOriginGateway, establishConnections } from './connect';
import { getConfig, setConfig, museToken } from './config';
import { importSecretsFromGateway } from './secretImport';

let started = false;

export async function autoSyncOnLaunch(): Promise<void> {
  if (started || typeof window === 'undefined') return;
  started = true;

  try {
    // Served by a gateway on this device? Adopt that origin as the gateway.
    const sameOrigin = await detectSameOriginGateway();
    if (sameOrigin && !getConfig().museBaseUrl) setConfig({ museBaseUrl: sameOrigin });

    const target = sameOrigin || getConfig().museBaseUrl;
    // Nothing on-device to sync with yet — the Connect wizard handles first
    // pairing (owner-gated). Don't nag or spuriously attempt to pair here.
    if (!target && !museToken()) return;

    // Reconnect / refresh the full bring-up. No owner phrase is supplied: an
    // existing device token reconnects silently; a fresh device intentionally
    // falls through to the wizard for the one-time owner-gated pairing.
    await establishConnections({ baseUrl: target || undefined, ownerPhrase: '' }, () => {}).catch(
      () => {},
    );

    // With a working gateway (existing token or same-origin), import the owner's
    // existing provider keys so all their Hermes models & providers are present.
    if (museToken() || sameOrigin) {
      await importSecretsFromGateway().catch(() => {});
    }

    window.dispatchEvent(new CustomEvent('nexus:auto-synced'));
  } catch {
    /* best-effort — never block boot */
  }
}
