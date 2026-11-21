/* API client. Same-origin /api (Next rewrite). Transient failures: at most three automatic retries at
   1/2/4 s respecting Retry-After, then an explicit Retry (blueprint recovery table). Idempotency keys make
   infrastructure retries safe (no extra attempt or charge). */

export class ApiError extends Error {
  status: number;
  code: string;
  data: any;
  constructor(status: number, code: string, message: string, data: any) {
    super(message);
    this.status = status;
    this.code = code;
    this.data = data;
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const RETRYABLE = new Set([429, 502, 503, 504]);

export async function api<T = any>(path: string, init: RequestInit & { json?: unknown; retries?: number } = {}): Promise<T> {
  const { json, retries = 3, ...rest } = init;
  const headers = new Headers(rest.headers);
  headers.set("x-thinkfirst-client", "web");
  let body = rest.body;
  if (json !== undefined) {
    headers.set("content-type", "application/json");
    body = JSON.stringify(json);
  }
  let attempt = 0;
  for (;;) {
    let res: Response;
    try {
      res = await fetch(`/api${path}`, { ...rest, headers, body, credentials: "same-origin" });
    } catch {
      if (attempt < retries) {
        await sleep(1000 * 2 ** attempt++);
        continue;
      }
      throw new ApiError(0, "NETWORK", "You appear to be offline. Your work on this page is kept.", null);
    }
    if (RETRYABLE.has(res.status) && attempt < retries) {
      const ra = Number(res.headers.get("retry-after"));
      await sleep(Number.isFinite(ra) && ra > 0 ? ra * 1000 : 1000 * 2 ** attempt);
      attempt++;
      continue;
    }
    const ct = res.headers.get("content-type") || "";
    const data = ct.includes("application/json") ? await res.json() : await res.blob();
    if (!res.ok) {
      const err = (data as any)?.error || {};
      throw new ApiError(res.status, err.code || `HTTP_${res.status}`, err.message || "Something went wrong.", err);
    }
    return data as T;
  }
}

export const newKey = () =>
  (globalThis.crypto && "randomUUID" in globalThis.crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);

/** Poll a job until terminal. Never treats a local timeout as server failure. */
export async function pollJob(jobId: string, onTick?: (job: any, elapsedMs: number) => void, maxMs = 180_000): Promise<any> {
  const start = Date.now();
  for (;;) {
    const job = await api(`/jobs/${jobId}`);
    onTick?.(job, Date.now() - start);
    if (["succeeded", "failed", "cancelled"].includes(job.status)) return job;
    if (Date.now() - start > maxMs) return { ...job, status: "slow" };
    await sleep(1000);
  }
}

export async function sha256Hex(data: ArrayBuffer): Promise<string | null> {
  if (!globalThis.crypto?.subtle) return null;
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function deviceId(): string {
  // Per-tab identity for the session owner lease (a second tab is a separate writer).
  try {
    let id = sessionStorage.getItem("tf_device");
    if (!id) {
      id = newKey();
      sessionStorage.setItem("tf_device", id);
    }
    return id;
  } catch {
    return "no-storage";
  }
}
