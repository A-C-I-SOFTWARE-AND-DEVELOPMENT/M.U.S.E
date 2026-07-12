import { useState } from 'react';
import { getSecret, setSecret } from '@/lib/config';

export interface FieldSpec {
  env: string;
  label: string;
  type: 'text' | 'password' | 'url';
  placeholder?: string;
}

/** A single encrypted-at-rest credential field (autosaves on blur). */
export function SecretField({ f }: { f: FieldSpec }) {
  const [val, setVal] = useState(getSecret(f.env));
  const [reveal, setReveal] = useState(false);
  const [saved, setSaved] = useState(false);
  const secret = f.type === 'password';
  return (
    <div className="flex flex-col gap-1">
      <label className="hud-label">{f.label}</label>
      <div className="flex gap-2">
        <input
          value={val}
          onChange={(e) => { setVal(e.target.value); setSaved(false); }}
          onBlur={() => { setSecret(f.env, val.trim()); setSaved(true); }}
          type={secret && !reveal ? 'password' : 'text'}
          placeholder={f.placeholder}
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          className="flex-1 rounded-md border px-2.5 py-2 text-[12px] text-[var(--ink)]"
          style={{ borderColor: saved ? 'var(--state-running)' : 'var(--hairline)', background: 'var(--panel-solid)' }}
        />
        {secret && (
          <button onClick={() => setReveal((r) => !r)} className="rounded-md border border-[var(--hairline)] px-2 text-[11px] text-[var(--ink-dim)]">
            {reveal ? '🙈' : '👁'}
          </button>
        )}
      </div>
      <div className="mono text-[8px] text-[var(--ink-faint)]">{f.env}{saved ? ' · saved' : ''}</div>
    </div>
  );
}
