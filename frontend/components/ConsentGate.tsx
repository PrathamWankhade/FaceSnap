'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ShieldAlert, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { api, ApiError } from '@/lib/api';
import { consentStaleCopy, isConsentStale, type ConsentNotice } from '@/lib/consent';

interface ConsentGateProps {
  /** Version recorded on the student row (null for pre-versioning enrollments). */
  studentConsentVersion?: string | null;
  /** Skip the check until the student profile has loaded. */
  enabled?: boolean;
  /** Called whenever staleness changes (parent disables attendance while true). */
  onStatusChange?: (stale: boolean) => void;
  /** Called after a successful re-consent. */
  onAccepted?: (version: string) => void;
}

/**
 * Blocks attendance when the recorded consent version is older than the
 * current notice. The gate only covers the client; enrollment itself fails
 * closed on the server (`consent_version` is required), and attendance is
 * always written by the backend after a server-side match.
 */
export default function ConsentGate({
  studentConsentVersion,
  enabled = true,
  onStatusChange,
  onAccepted,
}: ConsentGateProps) {
  const [notice, setNotice] = useState<ConsentNotice | null>(null);
  const [stale, setStale] = useState(false);
  const [accepting, setAccepting] = useState(false);

  const statusRef = useRef(onStatusChange);
  useEffect(() => {
    statusRef.current = onStatusChange;
  }, [onStatusChange]);

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    api
      .get<ConsentNotice>('/api/consent')
      .then((current) => {
        if (!active) return;
        setNotice(current);
        const needsRenewal = isConsentStale(studentConsentVersion, current.version);
        setStale(needsRenewal);
        statusRef.current?.(needsRenewal);
      })
      .catch(() => {
        // A failed notice fetch must not block the scan: the student can still
        // verify, and the backend never trusts the client for consent state.
        if (!active) return;
        setStale(false);
        statusRef.current?.(false);
      });
    return () => {
      active = false;
    };
  }, [enabled, studentConsentVersion]);

  const accept = useCallback(async () => {
    setAccepting(true);
    try {
      const result = await api.post<{ consentVersion: string }>('/api/consent/accept');
      setStale(false);
      statusRef.current?.(false);
      onAccepted?.(result.consentVersion);
      toast.success('Consent renewed. Attendance verification is unlocked.');
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : 'Could not record consent. Try again.');
    } finally {
      setAccepting(false);
    }
  }, [onAccepted]);

  if (!stale || !notice) return null;

  const copy = consentStaleCopy(studentConsentVersion, notice.version);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="consent-gate-title"
        aria-describedby="consent-gate-body"
        className="bg-white dark:bg-slate-900 p-8 rounded-[2rem] max-w-lg w-full shadow-2xl border border-slate-100 dark:border-slate-800"
      >
        <div className="w-16 h-16 bg-amber-100 dark:bg-amber-950/60 rounded-2xl flex items-center justify-center mb-6">
          <ShieldAlert className="w-8 h-8 text-amber-600 dark:text-amber-400" />
        </div>
        <h2 id="consent-gate-title" className="text-2xl font-bold text-slate-900 dark:text-white mb-3">
          {copy.title}
        </h2>
        <p id="consent-gate-body" className="text-slate-600 dark:text-slate-300 mb-5 leading-relaxed">
          {copy.body}
        </p>
        <div className="bg-amber-50 dark:bg-amber-950/40 border border-amber-100 dark:border-amber-900/50 rounded-2xl p-4 mb-6 text-sm text-amber-800 dark:text-amber-200 leading-relaxed">
          {notice.summary}
        </div>
        {notice.withdrawal && (
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-6">{notice.withdrawal}</p>
        )}
        <button
          type="button"
          onClick={accept}
          disabled={accepting}
          className="w-full py-4 px-6 bg-gradient-to-r from-amber-500 to-orange-500 text-white rounded-full font-bold hover:from-amber-600 hover:to-orange-600 transition-all shadow-md shadow-amber-500/20 disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {accepting ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" /> Recording consent…
            </>
          ) : (
            `Accept consent version ${notice.version}`
          )}
        </button>
      </div>
    </div>
  );
}
