import { apiRequest, jsonBody } from '../../lib/api';

type StoredFile = { key: string; blob: Blob; name: string };
type Operation = {
  id: string;
  path: string;
  method: 'POST' | 'PATCH';
  json?: Record<string, unknown>;
  files?: StoredFile[];
  createdAt: number;
  followup?: string;
};

const DB = 'kemta-field-outbox';
const STORE = 'operations';

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: 'id' });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function all(): Promise<Operation[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly');
    const request = tx.objectStore(STORE).getAll();
    request.onsuccess = () => resolve(request.result as Operation[]);
    request.onerror = () => reject(request.error);
  });
}

async function remove(id: string): Promise<void> {
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).delete(id);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function queueJson(path: string, method: Operation['method'], json: Record<string, unknown>, followup?: string): Promise<string> {
  const id = crypto.randomUUID();
  const operation: Operation = { id, path, method, json: { ...json, client_reference: String(json.client_reference ?? id) }, createdAt: Date.now(), ...(followup ? { followup } : {}) };
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).put(operation);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  return id;
}

export async function queueFile(path: string, fields: Record<string, string>, file: File, fileKey = 'image'): Promise<string> {
  const id = crypto.randomUUID();
  const operation: Operation = {
    id, path, method: 'POST', createdAt: Date.now(),
    json: { ...fields, client_reference: id },
    files: [{ key: fileKey, blob: file, name: file.name }],
  };
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).put(operation);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  return id;
}

/** Rejoue dans l'ordre les actions conservées localement. Les références client rendent les POST idempotents. */
export async function flushOutbox(): Promise<number> {
  if (!navigator.onLine) return 0;
  let completed = 0;
  for (const operation of await all()) {
    try {
      if (operation.files?.length) {
        const body = new FormData();
        Object.entries(operation.json ?? {}).forEach(([key, value]) => body.append(key, String(value)));
        operation.files.forEach((file) => body.append(file.key, file.blob, file.name));
        await apiRequest(operation.path, { method: operation.method, body, headers: { 'Idempotency-Key': operation.id } });
      } else {
        const result = await apiRequest<{ id?: number }>(operation.path, { method: operation.method, body: jsonBody(operation.json ?? {}), headers: { 'Idempotency-Key': operation.id } });
        if (operation.followup && result.id) {
          await apiRequest(operation.followup.replace(':id', String(result.id)), { method: 'POST', body: jsonBody({}), headers: { 'Idempotency-Key': `${operation.id}-submit` } });
        }
      }
      await remove(operation.id);
      completed += 1;
    } catch {
      // La première erreur réseau conserve l'ordre et laisse la synchronisation suivante reprendre sans doublon.
      break;
    }
  }
  return completed;
}
