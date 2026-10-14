'use client';

import { useEffect } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Application error:', error);
  }, [error]);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-4">
      <div className="max-w-md w-full text-center bg-white dark:bg-slate-900 p-10 rounded-[2rem] shadow-xl border border-slate-100 dark:border-slate-800">
        <div className="w-20 h-20 bg-rose-100 dark:bg-rose-950/50 rounded-[2rem] flex items-center justify-center mx-auto mb-6 shadow-inner">
          <AlertTriangle className="w-10 h-10 text-rose-600" />
        </div>
        <h1 className="text-3xl font-display font-bold text-slate-900 dark:text-white mb-4 tracking-tight">
          Something went wrong
        </h1>
        <p className="text-slate-600 dark:text-slate-300 mb-8 leading-relaxed">
          An unexpected error occurred. Please try again.
          {error.digest && (
            <span className="block mt-2 text-xs font-mono text-slate-400 dark:text-slate-500">
              Error ID: {error.digest}
            </span>
          )}
        </p>
        <button
          onClick={reset}
          className="px-8 py-4 bg-gradient-to-r from-indigo-600 to-blue-600 text-white rounded-full font-bold hover:from-indigo-700 hover:to-blue-700 transition-all shadow-md shadow-indigo-500/20 hover:shadow-lg hover:shadow-indigo-500/30 hover:-translate-y-0.5 inline-flex items-center justify-center gap-3"
        >
          <RefreshCw className="w-5 h-5" />
          Try Again
        </button>
      </div>
    </div>
  );
}
