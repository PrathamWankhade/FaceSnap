/** Consent helpers shared by the register page and the consent gate. */

export interface ConsentNotice {
  version: string;
  summary: string;
  policy?: string;
  withdrawal?: string;
}

/**
 * Is the student's recorded consent older than the current notice?
 *
 * Returns `false` when the current version is unknown (the notice failed to
 * load). The register flow still fails closed server-side, and the verify flow
 * must not break because a notice request timed out.
 */
export function isConsentStale(
  studentVersion: string | null | undefined,
  currentVersion: string | null | undefined,
): boolean {
  if (!currentVersion) return false;
  return studentVersion !== currentVersion;
}

/** Copy shown in the blocking modal. */
export function consentStaleCopy(
  studentVersion: string | null | undefined,
  currentVersion: string,
): { title: string; body: string } {
  const previous = studentVersion ? `version ${studentVersion}` : 'no recorded version';
  return {
    title: 'Consent needs renewal',
    body:
      `The biometric consent notice has been updated (${previous} → version ${currentVersion}). ` +
      'Attendance verification stays blocked until you review and accept the current notice. ' +
      'You can still delete your profile at any time.',
  };
}
