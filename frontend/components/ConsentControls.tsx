'use client';

import React, { useState } from 'react';
import { Loader2, ShieldCheck, ShieldOff } from 'lucide-react';
import { toast } from 'sonner';
import { api, ApiError } from '@/lib/api';

interface ConsentControlsProps {
  /** ISO timestamp recorded when the student withdrew consent (null = active). */
  withdrawnAt?: string | null;
  /** Called after withdraw / restore so the parent can update its own state. */
  onChanged?: (withdrawn: boolean) => void;
}

/**
 * Withdrawal control for the student's own consent.
 *
 * Withdrawing stops biometric processing (enrollment, verification and
 * attendance) while keeping the profile and attendance history; restoring
 * re-accepts the current notice. Both actions are the student's own and are
 * audited server-side — this component is the UI, never the authority.
 */
export default function ConsentControls({ withdrawnAt, onChanged }: ConsentControlsProps) {
  const [pending, setPending] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const withdrawn = Boolean(withdrawnAt);

  const message = (error: unknown, fallback: string) =>
    error instanceof ApiError ? error.message : fallback;

  const restore = async () => {
    setPending(true);
    try {
      await api.post<{ consentVersion: string }>('/api/consent/accept');
      onChanged?.(false);
      toast.success('Consent restored. Identity verification is unlocked.');
    } catch (error) {
      toast.error(message(error, 'Could not restore consent. Try again.'));
    } finally {
      setPending(false);
    }
  };

  const withdraw = async () => {
    setPending(true);
    try {
      const result = await api.post<{ withdrawnAt: string }>('/api/consent/withdraw');
      onChanged?.(true);
      setConfirming(false);
      toast.success('Consent withdrawn. Biometric verification is now disabled.');
      if (!result.withdrawnAt) {
        // Older servers reply without the timestamp; the UI state stays correct.
        onChanged?.(true);
      }
    } catch (error) {
      toast.error(message(error, 'Could not withdraw consent. Try again.'));
    } finally {
      setPending(false);
    }
  };

  if (withdrawn) {
    return (
      <section
        aria-labelledby="consent-withdrawn-title"
        className="rounded-3xl border border-amber-200 dark:border-amber-900/60 bg-amber-50 dark:bg-amber-950/40 p-6 mb-8"
      >
        <div className="flex items-start gap-4">
          <div className="w-11 h-11 rounded-2xl bg-amber-100 dark:bg-amber-950/60 flex items-center justify-center shrink-0">
            <ShieldOff className="w-5 h-5 text-amber-600 dark:text-amber-400" aria-hidden="true" />
          </div>
          <div className="flex-1">
            <h2 id="consent-withdrawn-title" className="font-bold text-slate-900 dark:text-white mb-1">
              Biometric consent withdrawn
            </h2>
            <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed mb-4">
              Identity verification, enrollment and attendance are disabled for this account.
              Your profile and attendance history are kept. Restore consent to verify again.
            </p>
            <button
              type="button"
              onClick={restore}
              disabled={pending}
              className="inline-flex items-center gap-2 py-2.5 px-5 rounded-full bg-amber-600 text-white text-sm font-bold hover:bg-amber-700 transition-colors disabled:opacity-50"
            >
              {pending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" /> Restoring…
                </>
              ) : (
                <>
                  <ShieldCheck className="w-4 h-4" aria-hidden="true" /> Restore consent
                </>
              )}
            </button>
          </div>
        </div>
      </section>
    );
  }

  if (!confirming) {
    return (
      <div className="mb-8">
        <button
          type="button"
          onClick={() => setConfirming(true)}
          className="inline-flex items-center gap-2 text-sm font-semibold text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
        >
          <ShieldOff className="w-4 h-4" aria-hidden="true" />
          Withdraw biometric consent
        </button>
      </div>
    );
  }

  return (
    <section
      aria-labelledby="consent-withdraw-title"
      className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 mb-8"
    >
      <h2 id="consent-withdraw-title" className="font-bold text-slate-900 dark:text-white mb-2">
        Withdraw consent for biometric processing?
      </h2>
      <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed mb-5">
        Identity verification, enrollment and attendance will stop for this account. Your profile
        and attendance history are kept, and you can restore consent at any time by accepting the
        current notice again.
      </p>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={withdraw}
          disabled={pending}
          className="inline-flex items-center gap-2 py-2.5 px-5 rounded-full bg-rose-600 text-white text-sm font-bold hover:bg-rose-700 transition-colors disabled:opacity-50"
        >
          {pending ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" /> Withdrawing…
            </>
          ) : (
            'Yes, withdraw consent'
          )}
        </button>
        <button
          type="button"
          onClick={() => setConfirming(false)}
          disabled={pending}
          className="py-2.5 px-5 rounded-full border border-slate-200 dark:border-slate-700 text-sm font-bold text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </section>
  );
}