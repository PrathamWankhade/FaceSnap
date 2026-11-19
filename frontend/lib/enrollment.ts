/**
 * Enrollment quality gate helpers.
 *
 * The backend rejects a bad enrollment photo with a structured 422:
 *
 *   { detail: { message, reasons: string[], metrics: {...}, face_count } }
 *
 * `reasons` are human-readable sentences produced by the quality gate. This
 * module turns them into stable, actionable issues plus a compact metric table
 * so the UI never shows a bare "Request failed (422)".
 */

export interface EnrollmentQualityDetail {
  message: string;
  reasons: string[];
  metrics: Record<string, number | null>;
  faceCount: number;
}

export type QualityIssueCode =
  | 'face_count'
  | 'face_too_small'
  | 'low_confidence'
  | 'blurry'
  | 'too_dark'
  | 'turned'
  | 'tilted'
  | 'model_unavailable'
  | 'invalid_image'
  | 'embedding_failed'
  | 'unknown';

export interface QualityIssue {
  code: QualityIssueCode;
  title: string;
  fix: string;
  /** The original backend sentence, kept for support/debugging. */
  reason: string;
}

interface QualityRule {
  match: RegExp;
  code: QualityIssueCode;
  title: string;
  fix: string;
}

// Order matters: the first matching rule wins. The backend sentences are
// defined in backend/app/services/face_service.py::assess_enrollment.
const RULES: QualityRule[] = [
  {
    match: /exactly one clearly visible face/i,
    code: 'face_count',
    title: 'One face required',
    fix: 'Make sure only your face is in frame and that nobody else is behind you.',
  },
  {
    match: /too small in frame/i,
    code: 'face_too_small',
    title: 'Move closer',
    fix: 'Your face is too small. Move closer to the camera and fill the frame.',
  },
  {
    match: /not clear enough/i,
    code: 'low_confidence',
    title: 'Face not clear',
    fix: 'Look straight at the camera with your whole face visible and retake.',
  },
  {
    match: /blurry/i,
    code: 'blurry',
    title: 'Photo is blurry',
    fix: 'Hold still for a moment before capturing and retake.',
  },
  {
    match: /too dark/i,
    code: 'too_dark',
    title: 'Too dark',
    fix: 'Move to better lighting or face a light source, then retake.',
  },
  {
    match: /turned too far/i,
    code: 'turned',
    title: 'Face turned away',
    fix: 'Look straight at the camera instead of to the side.',
  },
  {
    match: /head is tilted/i,
    code: 'tilted',
    title: 'Head tilted',
    fix: 'Keep your head level with your eyes on the camera.',
  },
  {
    match: /model is not loaded/i,
    code: 'model_unavailable',
    title: 'Recognition model offline',
    fix: 'Registration cannot run right now. Ask staff to check the backend, then retry.',
  },
  {
    match: /could not be decoded|empty or too large/i,
    code: 'invalid_image',
    title: 'Image unreadable',
    fix: 'Retake the photo. If it keeps failing, lower the camera resolution.',
  },
  {
    match: /embedding/i,
    code: 'embedding_failed',
    title: 'Face could not be encoded',
    fix: 'Retake with a clear, front-facing photo. If it persists, re-enroll with staff present.',
  },
];

function toReasons(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
}

function toMetrics(value: unknown): Record<string, number | null> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const metrics: Record<string, number | null> = {};
  for (const [key, raw] of Object.entries(value as Record<string, unknown>)) {
    if (raw === null || typeof raw === 'number') metrics[key] = raw as number | null;
  }
  return metrics;
}

/** Narrow an unknown `detail` payload to the enrollment-quality shape. */
export function parseEnrollmentQualityDetail(detail: unknown): EnrollmentQualityDetail | null {
  if (!detail || typeof detail !== 'object' || Array.isArray(detail)) return null;
  const body = detail as Record<string, unknown>;
  const reasons = toReasons(body.reasons);
  const metrics = toMetrics(body.metrics);
  if (reasons.length === 0 && Object.keys(metrics).length === 0) return null;
  return {
    message: typeof body.message === 'string' && body.message ? body.message : 'Enrollment photo rejected.',
    reasons,
    metrics,
    faceCount: typeof body.face_count === 'number' ? body.face_count : 0,
  };
}

/** Map backend rejection sentences to deduplicated, actionable issues. */
export function describeQualityIssues(reasons: string[]): QualityIssue[] {
  const issues: QualityIssue[] = [];
  const seen = new Set<QualityIssueCode>();
  for (const reason of reasons) {
    const rule = RULES.find((candidate) => candidate.match.test(reason));
    const code = rule?.code ?? 'unknown';
    if (seen.has(code)) continue;
    seen.add(code);
    issues.push({
      code,
      title: rule?.title ?? 'Photo rejected',
      fix: rule?.fix ?? 'Retake the photo in even lighting with one face in frame.',
      reason,
    });
  }
  return issues;
}

const METRIC_LABELS: Record<string, { label: string; format: (value: number) => string }> = {
  face_width: { label: 'Face width', format: (v) => `${Math.round(v)} px` },
  face_height: { label: 'Face height', format: (v) => `${Math.round(v)} px` },
  det_score: { label: 'Detection confidence', format: (v) => v.toFixed(3) },
  sharpness: { label: 'Sharpness', format: (v) => v.toFixed(1) },
  brightness: { label: 'Brightness', format: (v) => `${v.toFixed(1)} / 255` },
  yaw_ratio: { label: 'Yaw (0 = facing camera)', format: (v) => v.toFixed(3) },
  roll_degrees: { label: 'Roll', format: (v) => `${v.toFixed(1)}°` },
};

export interface QualityMetricRow {
  key: string;
  label: string;
  value: string;
}

/** Present the measurements that came with a rejection, skipping nulls. */
export function qualityMetricRows(metrics: Record<string, number | null> | undefined): QualityMetricRow[] {
  if (!metrics) return [];
  const rows: QualityMetricRow[] = [];
  for (const [key, raw] of Object.entries(metrics)) {
    if (raw === null || raw === undefined) continue;
    const known = METRIC_LABELS[key];
    rows.push({
      key,
      label: known?.label ?? key.replace(/_/g, ' '),
      value: known ? known.format(raw) : String(raw),
    });
  }
  return rows;
}
