import type { ReactNode } from 'react';

function read(record: Record<string, unknown> | null, path: string): unknown {
  let current: unknown = record;
  for (const part of path.split('.')) {
    if (!current || typeof current !== 'object') return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

function format(value: unknown): string {
  if (value == null || value === '') return 'Not reported';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (Array.isArray(value)) return value.length === 0 ? 'None reported' : `${value.length} records`;
  if (typeof value === 'object') return `${Object.keys(value as object).length} fields reported`;
  return String(value);
}

export function EvidencePanel({
  title,
  eyebrow,
  record,
  fields,
  children,
}: {
  title: string;
  eyebrow: string;
  record: Record<string, unknown> | null;
  fields: Array<{ label: string; path: string }>;
  children?: ReactNode;
}) {
  return (
    <section className="evidence-panel universe-panel">
      <header>
        <div><p className="universe-eyebrow">{eyebrow}</p><h2>{title}</h2></div>
        <span className={`universe-chip universe-chip--${record ? 'observed' : 'unavailable'}`}>{record ? 'Reported' : 'Unavailable'}</span>
      </header>
      <dl className="universe-definition-grid">
        {fields.map((field) => <div key={field.label}><dt>{field.label}</dt><dd>{format(read(record, field.path))}</dd></div>)}
      </dl>
      {children}
    </section>
  );
}
