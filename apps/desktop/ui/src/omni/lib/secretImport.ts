// ============================================================================
// Import the user's EXISTING credential keys from their gateway's ~/.hermes/.env
// so they don't have to re-type them. The gateway endpoint is owner-gated, opt-in
// (HERMES_COCKPIT_SECRET_IMPORT=1), and loopback-only; it returns only
// credential-shaped names. Imported values land in NEXUS's encrypted on-device
// store (securestore, AES-GCM) — same protection as keys typed by hand.
// ============================================================================

import { museBase, authHeaders, setSecret } from './config';

export interface ImportResult {
  ok: boolean;
  imported: string[];
  count: number;
  error?: string;
}

/** Pull existing credential keys from the connected gateway and store them. */
export async function importSecretsFromGateway(): Promise<ImportResult> {
  const base = museBase();
  if (!base) {
    return { ok: false, imported: [], count: 0, error: 'No gateway connected — connect a MUSE gateway first (Settings → Connections).' };
  }
  let res: Response;
  try {
    res = await fetch(`${base}/v1/cockpit/secrets/import`, { headers: authHeaders() });
  } catch {
    return { ok: false, imported: [], count: 0, error: 'Could not reach the gateway.' };
  }
  if (res.status === 401) {
    return { ok: false, imported: [], count: 0, error: 'Not paired — pair this device with the gateway first.' };
  }
  if (res.status === 403) {
    let hint = 'Key import is disabled on the gateway.';
    try {
      hint = (await res.json())?.hint || hint;
    } catch {
      /* ignore */
    }
    return { ok: false, imported: [], count: 0, error: hint };
  }
  if (!res.ok) {
    return { ok: false, imported: [], count: 0, error: `Gateway responded ${res.status}.` };
  }
  let data: { keys?: Record<string, string> };
  try {
    data = await res.json();
  } catch {
    return { ok: false, imported: [], count: 0, error: 'Unexpected response from the gateway.' };
  }
  const keys = data.keys ?? {};
  const imported: string[] = [];
  for (const [name, value] of Object.entries(keys)) {
    if (value) {
      setSecret(name, value); // encrypted at rest; emits nexus:config so the UI refreshes
      imported.push(name);
    }
  }
  return { ok: true, imported, count: imported.length };
}
