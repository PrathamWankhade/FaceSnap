import { User } from 'firebase/auth';
import { auth } from './firebase';

/** Canonical attendance payload. All capture methods must use these field names. */
export async function buildAttendanceRecord(
  student: { uid: string; name: string; rollNumber: string; department: string; year: string; semester: string },
  method: 'individual_live' | 'doorway_batch' | 'cctv_stream' | 'upload',
  extra?: { liveness_score?: number | null; sessionId?: string }
) {
  const { serverTimestamp } = await import('firebase/firestore');
  return {
    studentUid: student.uid,
    name: student.name,
    rollNumber: student.rollNumber,
    department: student.department,
    year: student.year,
    semester: student.semester,
    timestamp: serverTimestamp(),
    method,
    ...(extra?.liveness_score !== undefined ? { liveness_score: extra.liveness_score } : {}),
    ...(extra?.sessionId ? { sessionId: extra.sessionId } : {}),
  };
}

/** Deterministic client-side session scope (YYYY-MM-DD) to reduce duplicate writes. */
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
