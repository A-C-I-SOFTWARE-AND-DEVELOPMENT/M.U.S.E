// ============================================================================
// On-device data store for training/knowledge uploads. Real persistence in
// IndexedDB (files can be large — localStorage is unsuitable). This is the
// "Local" option: uploaded material stays on THIS device; nothing leaves it
// unless you point training at a gateway or a local trainer you run.
// ============================================================================

const DB_NAME = 'nexus-data';
const STORE = 'docs';

export interface StoredDoc {
  id: string;
  packId: string;
  name: string;
  type: string;
  bytes: number;
  addedAt: number;
  blob: Blob;
}

export function localStoreAvailable(): boolean {
  return typeof indexedDB !== 'undefined';
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const os = db.createObjectStore(STORE, { keyPath: 'id' });
        os.createIndex('packId', 'packId', { unique: false });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function tx<T>(mode: IDBTransactionMode, fn: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  return openDb().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const t = db.transaction(STORE, mode);
        const req = fn(t.objectStore(STORE));
        req.onsuccess = () => resolve(req.result as T);
        req.onerror = () => reject(req.error);
      }),
  );
}

/** Store an uploaded file on-device. Returns the stored doc metadata. */
export async function putDoc(packId: string, file: File): Promise<Omit<StoredDoc, 'blob'>> {
  const id = `doc-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
  const doc: StoredDoc = { id, packId, name: file.name, type: file.type || 'application/octet-stream', bytes: file.size, addedAt: Date.now(), blob: file };
  await tx('readwrite', (s) => s.put(doc));
  const { blob: _omit, ...meta } = doc;
  return meta;
}

export async function deleteDoc(id: string): Promise<void> {
  await tx('readwrite', (s) => s.delete(id));
}

export async function getDocBlob(id: string): Promise<Blob | null> {
  const d = (await tx<StoredDoc | undefined>('readonly', (s) => s.get(id))) ?? null;
  return d?.blob ?? null;
}

export async function listDocs(packId?: string): Promise<Omit<StoredDoc, 'blob'>[]> {
  const all = (await tx<StoredDoc[]>('readonly', (s) => s.getAll())) ?? [];
  return all
    .filter((d) => !packId || d.packId === packId)
    .map(({ blob: _b, ...m }) => m)
    .sort((a, b) => a.addedAt - b.addedAt);
}

export async function totalBytes(): Promise<number> {
  const all = (await tx<StoredDoc[]>('readonly', (s) => s.getAll())) ?? [];
  return all.reduce((n, d) => n + (d.bytes || 0), 0);
}

export async function clearPack(packId: string): Promise<void> {
  const docs = await listDocs(packId);
  await Promise.all(docs.map((d) => deleteDoc(d.id)));
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Build a training-ready JSONL dataset from a pack's stored docs and trigger a
 * download. Text-like files become one record per doc; binary files are listed
 * by reference. This is the honest "local training" hand-off: the browser can't
 * run QLoRA, so it prepares the exact dataset your local trainer ingests.
 */
export async function exportPackJsonl(packId: string, packName: string): Promise<number> {
  const docs = await listDocs(packId);
  const lines: string[] = [];
  for (const d of docs) {
    const blob = await getDocBlob(d.id);
    if (!blob) continue;
    const isText = /^text\/|json|markdown|xml|csv|javascript|typescript/.test(d.type) || /\.(txt|md|json|csv|c|cpp|h|hpp|py|ts|js|rs|go)$/i.test(d.name);
    if (isText) {
      const text = await blob.text();
      lines.push(JSON.stringify({ source: d.name, pack: packName, text }));
    } else {
      lines.push(JSON.stringify({ source: d.name, pack: packName, note: 'binary asset — convert before training', bytes: d.bytes }));
    }
  }
  const content = lines.join('\n');
  const url = URL.createObjectURL(new Blob([content], { type: 'application/jsonl' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `${packName.replace(/\s+/g, '_')}.jsonl`;
  a.click();
  URL.revokeObjectURL(url);
  return lines.length;
}
