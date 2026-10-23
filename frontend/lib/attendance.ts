import { User } from 'firebase/auth';
import { auth } from './firebase';
import { getBackendUrl } from './utils';

export type CaptureMethod = 'individual_live' | 'doorway_batch' | 'cctv_stream' | 'upload';

/** Deterministic client-side session scope (YYYY-MM-DD). */
export function todaySessionId(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export async function getIdToken(): Promise<string | null> {
  try {
    const user: User | null = auth?.currentUser ?? null;
    if (!user) return null;
    return await user.getIdToken();
  } catch {
    return null;
  }
}

export async function authHeaders(): Promise<Record<string, string>> {
  const token = await getIdToken();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

export interface AttendanceResult {
  duplicate: boolean;
  record: {
    id: number;
    studentUid: string;
    studentId: string;
    name: string;
    rollNumber: string;
    department?: string;
    year?: string;
    semester?: string;
    timestamp: string;
    method: CaptureMethod;
    sessionId?: number | null;
  };
}

/**
 * Record attendance through the backend (single write path).
 * The server is idempotent: one mark per student per session, otherwise one
 * per student per day per capture method.
 */
export async function markAttendance(payload: {
  studentUid?: string;
  method: CaptureMethod;
  liveness_score?: number | null;
  session_id?: number | null;
}): Promise<AttendanceResult> {
  const headers = await authHeaders();
  const res = await fetch(getBackendUrl('/api/attendance'), {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let detail = `Could not record attendance (${res.status}).`;
    try {
      const body = await res.json();
      if (typeof body?.detail === 'string') detail = body.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return (await res.json()) as AttendanceResult;
}
