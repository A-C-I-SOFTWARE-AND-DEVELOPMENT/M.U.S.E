// ============================================================================
// Encrypted-at-rest store for credentials. AES-GCM with a NON-EXTRACTABLE key
// generated in the browser and kept in IndexedDB — the raw key bytes are never
// readable by JavaScript, so secrets are never persisted as clear text.
// Ciphertext lives in localStorage; the key handle lives in IndexedDB.
// ============================================================================

const DB_NAME = 'nexus-secure';
const STORE = 'kv';
const KEY_ID = 'aesgcm-master';

export function secureAvailable(): boolean {
  return (
    typeof crypto !== 'undefined' &&
    !!crypto.subtle &&
    typeof indexedDB !== 'undefined'
  );
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) req.result.createObjectStore(STORE);
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function idbGet(db: IDBDatabase, key: string): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).get(key);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function idbPut(db: IDBDatabase, key: string, value: unknown): Promise<void> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).put(value, key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

let keyPromise: Promise<CryptoKey> | null = null;

async function masterKey(): Promise<CryptoKey> {
  if (keyPromise) return keyPromise;
  keyPromise = (async () => {
    const db = await openDb();
    const existing = (await idbGet(db, KEY_ID)) as CryptoKey | undefined;
    if (existing) return existing;
    // extractable: false — the key bytes can never be read back out into JS.
    const key = await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, false, [
      'encrypt',
      'decrypt',
    ]);
    await idbPut(db, KEY_ID, key);
    return key;
  })();
  return keyPromise;
}

const enc = new TextEncoder();
const dec = new TextDecoder();

function b64(buf: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(buf)));
}
function unb64(s: string): BufferSource {
  return Uint8Array.from(atob(s), (c) => c.charCodeAt(0)) as BufferSource;
}

/** Encrypt an object → "ivB64.ctB64". */
export async function encryptJson(obj: unknown): Promise<string> {
  const key = await masterKey();
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv: iv as BufferSource },
    key,
    enc.encode(JSON.stringify(obj)) as BufferSource,
  );
  return `${b64(iv.buffer as ArrayBuffer)}.${b64(ct)}`;
}

/** Decrypt "ivB64.ctB64" → object (or null on any failure). */
export async function decryptJson<T = unknown>(blob: string): Promise<T | null> {
  try {
    const [ivB64, ctB64] = blob.split('.');
    if (!ivB64 || !ctB64) return null;
    const key = await masterKey();
    const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: unb64(ivB64) }, key, unb64(ctB64));
    return JSON.parse(dec.decode(pt)) as T;
  } catch {
    return null;
  }
}
