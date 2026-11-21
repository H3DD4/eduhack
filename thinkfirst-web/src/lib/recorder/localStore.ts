/* Best-effort on-device recovery of recording chunks (IndexedDB). Storage can be evicted or fail, so this is
   never presented as guaranteed. Drafts expire 24 h after the last write; cleared after verified server receipt. */

const DB = "thinkfirst-audio";
const TTL_MS = 24 * 3600 * 1000;

export type LocalTake = { taskId: string; takeKey: string; mime: string; updatedAt: number; finalized: boolean; captureMs: number };

function open(): Promise<IDBDatabase | null> {
  return new Promise((resolve) => {
    try {
      if (typeof indexedDB === "undefined") return resolve(null);
      const req = indexedDB.open(DB, 1);
      req.onupgradeneeded = () => {
        const db = req.result;
        db.createObjectStore("takes", { keyPath: "taskId" });
        db.createObjectStore("chunks", { keyPath: ["takeKey", "seq"] });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
}

function tx<T>(db: IDBDatabase, stores: string[], mode: IDBTransactionMode, fn: (t: IDBTransaction) => T): Promise<T> {
  return new Promise((resolve, reject) => {
    const t = db.transaction(stores, mode);
    const out = fn(t);
    t.oncomplete = () => resolve(out);
    t.onerror = () => reject(t.error);
    t.onabort = () => reject(t.error);
  });
}

/** Returns true only after the write is acknowledged (drives the "On this device" badge). */
export async function saveChunk(meta: LocalTake, seq: number, blob: Blob): Promise<boolean> {
  const db = await open();
  if (!db) return false;
  try {
    await tx(db, ["takes", "chunks"], "readwrite", (t) => {
      t.objectStore("takes").put({ ...meta, updatedAt: Date.now() });
      t.objectStore("chunks").put({ takeKey: meta.takeKey, seq, blob });
    });
    return true;
  } catch {
    return false; // QuotaExceededError etc.: caller warns "This draft cannot be saved on this device."
  }
}

export async function markFinalized(meta: LocalTake): Promise<void> {
  const db = await open();
  if (!db) return;
  await tx(db, ["takes"], "readwrite", (t) => t.objectStore("takes").put({ ...meta, finalized: true, updatedAt: Date.now() })).catch(() => {});
}

export async function loadTake(taskId: string): Promise<{ meta: LocalTake; blob: Blob } | null> {
  const db = await open();
  if (!db) return null;
  try {
    const meta = await new Promise<LocalTake | undefined>((resolve) => {
      const r = db.transaction("takes").objectStore("takes").get(taskId);
      r.onsuccess = () => resolve(r.result);
      r.onerror = () => resolve(undefined);
    });
    if (!meta) return null;
    if (Date.now() - meta.updatedAt > TTL_MS) {
      await clearTake(taskId);
      return null;
    }
    const chunks = await new Promise<{ seq: number; blob: Blob }[]>((resolve) => {
      const r = db.transaction("chunks").objectStore("chunks").getAll(IDBKeyRange.bound([meta.takeKey, 0], [meta.takeKey, Infinity]));
      r.onsuccess = () => resolve(r.result || []);
      r.onerror = () => resolve([]);
    });
    if (!chunks.length) return null;
    chunks.sort((a, b) => a.seq - b.seq);
    // Only chunks from ONE take, same MIME — never concatenate incompatible takes.
    return { meta, blob: new Blob(chunks.map((c) => c.blob), { type: meta.mime }) };
  } catch {
    return null;
  }
}

export async function clearTake(taskId: string): Promise<void> {
  const db = await open();
  if (!db) return;
  try {
    const meta = await new Promise<LocalTake | undefined>((resolve) => {
      const r = db.transaction("takes").objectStore("takes").get(taskId);
      r.onsuccess = () => resolve(r.result);
      r.onerror = () => resolve(undefined);
    });
    await tx(db, ["takes", "chunks"], "readwrite", (t) => {
      t.objectStore("takes").delete(taskId);
      if (meta) t.objectStore("chunks").delete(IDBKeyRange.bound([meta.takeKey, 0], [meta.takeKey, Infinity]));
    });
  } catch {
    /* best effort */
  }
}
