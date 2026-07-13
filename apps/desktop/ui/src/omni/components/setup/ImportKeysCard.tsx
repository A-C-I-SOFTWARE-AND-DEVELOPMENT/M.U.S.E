import { useState } from 'react';
import { importSecretsFromGateway, type ImportResult } from '@/lib/secretImport';

/**
 * One-tap import of the keys the user already has in their gateway's
 * ~/.hermes/.env, so they don't re-type them. Values are written to NEXUS's
 * encrypted on-device store and the provider/add-on cards light up as Connected.
 */
export function ImportKeysCard() {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);

  const run = async () => {
    setBusy(true);
    setResult(null);
    setResult(await importSecretsFromGateway());
    setBusy(false);
  };

  return (
    <div className="glass px-3 py-3">
      <div className="text-[12px] font-semibold">Import keys I already have</div>
      <p className="mt-1 text-[10px] leading-relaxed text-[var(--ink-dim)]">
        Pulls every API key / token you already have in your gateway's
        <span className="mono"> ~/.hermes/.env</span> and fills them in here — no re-typing. Values are stored
        <b className="text-[var(--ink)]"> encrypted on this device</b>. Requires a connected gateway with
        <span className="mono"> HERMES_COCKPIT_SECRET_IMPORT=1</span> (owner-gated, loopback-only).
      </p>
      <button
        onClick={run}
        disabled={busy}
        className="mt-2 w-full rounded-md px-3 py-2 text-[12px] font-semibold text-black disabled:opacity-40"
        style={{ background: 'var(--octa-glow)' }}
      >
        {busy ? 'Importing…' : '⤓ Scan gateway & import my keys'}
      </button>
      {result && (
        <div className="mt-2 text-[10px] leading-relaxed">
          {result.ok ? (
            <span style={{ color: 'var(--state-running)' }}>
              Imported {result.count} key{result.count === 1 ? '' : 's'}
              {result.count > 0 ? ` — ${result.imported.slice(0, 6).join(', ')}${result.imported.length > 6 ? '…' : ''}. Providers now show Connected.` : '. Nothing new found in ~/.hermes/.env.'}
            </span>
          ) : (
            <span style={{ color: 'var(--state-error)' }}>{result.error}</span>
          )}
        </div>
      )}
    </div>
  );
}
