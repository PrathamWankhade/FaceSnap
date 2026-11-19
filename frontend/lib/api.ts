import { getBackendUrl } from './utils';
import { authHeaders } from './attendance';

export class ApiError extends Error {
  status: number;
  /** Structured `detail` body when the backend sent one (e.g. enrollment quality). */
  detail?: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

interface ParsedError {
  message: string;
  detail?: unknown;
}

async function parseError(res: Response): Promise<ParsedError> {
  try {
    const body = await res.json();
    if (typeof body?.detail === 'string') return { message: body.detail };
    if (Array.isArray(body?.detail) && body.detail[0]?.msg) {
      return { message: String(body.detail[0].msg) };
    }
    // Structured detail from the enrollment quality gate: show the reason
    // (e.g. "Photo is blurry") instead of a generic 422, and keep the full
    // object so the UI can render a details panel.
    if (body?.detail && typeof body.detail === 'object') {
      const detail = body.detail as Record<string, unknown>;
      const message = typeof detail.message === 'string' ? detail.message : '';
      const reasons = Array.isArray(detail.reasons) ? detail.reasons.join(' ') : '';
      const combined = [message, reasons].filter(Boolean).join(' ');
      if (combined) return { message: combined, detail };
      return { message: `Request failed (${res.status})`, detail };
    }
  } catch {
    // Non-JSON error body.
  }
  return { message: `Request failed (${res.status})` };
}

/** Authenticated JSON request against the FaceSnap backend. */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = await authHeaders();
  const res = await fetch(getBackendUrl(path), {
    ...init,
    headers: {
      ...headers,
      ...(init?.headers as Record<string, string> | undefined),
    },
  });
  if (!res.ok) {
    const parsed = await parseError(res);
    throw new ApiError(parsed.message, res.status, parsed.detail);
  }
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: 'DELETE' }),
};
