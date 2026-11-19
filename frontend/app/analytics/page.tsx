'use client';

import React, { useEffect, useState } from 'react';
import { BarChart3, Loader2, LogIn, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/components/AuthProvider';
import { api, ApiError } from '@/lib/api';
import { getBackendUrl } from '@/lib/utils';
import { authHeaders } from '@/lib/attendance';

interface Overview {
  studentsTotal: number;
  attendanceToday: number;
  byMethod: Record<string, number>;
}

interface TrendBucket {
  period: string;
  total: number;
  byMethod: Record<string, number>;
}

interface TrendsResponse {
  group: string;
  days: number;
  series: TrendBucket[];
  total: number;
}

export default function AnalyticsPage() {
  const { user, loading, signIn, role, roleLoading } = useAuth();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [trends, setTrends] = useState<TrendsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user || role !== 'admin') return;
    let active = true;

    (async () => {
      try {
        const headers = await authHeaders();
        const [overviewRes, trendsRes] = await Promise.all([
          fetch(getBackendUrl('/api/analytics/overview'), { headers }),
          fetch(getBackendUrl('/api/analytics/trends?group=day&days=30'), { headers }),
        ]);
        if (!overviewRes.ok || !trendsRes.ok) {
          throw new Error('Failed to load analytics.');
        }
        const overviewJson = (await overviewRes.json()) as Overview;
        const trendsJson = (await trendsRes.json()) as TrendsResponse;
        if (!active) return;
        setOverview(overviewJson);
        setTrends(trendsJson);
      } catch (err) {
        if (!active) return;
        const message = err instanceof Error ? err.message : 'Failed to load analytics.';
        setError(message);
        toast.error(message);
      } finally {
        if (active) setIsLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, [user, role]);

  if (loading || roleLoading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center">
        <Loader2 className="w-10 h-10 text-indigo-600 animate-spin" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-4">
        <div className="bg-white dark:bg-slate-900 p-10 rounded-[2rem] shadow-xl max-w-md w-full text-center border border-slate-100 dark:border-slate-800">
          <BarChart3 className="w-10 h-10 text-indigo-600 mx-auto mb-6" />
          <h2 className="text-3xl font-display font-bold text-slate-900 dark:text-white mb-4">Authentication Required</h2>
          <p className="text-slate-600 dark:text-slate-300 mb-8">Sign in with a staff account to view analytics.</p>
          <button
            onClick={signIn}
            className="w-full py-4 px-6 bg-gradient-to-r from-indigo-600 to-blue-600 text-white rounded-full font-bold hover:from-indigo-700 hover:to-blue-700 transition-all shadow-md shadow-indigo-500/20 flex items-center justify-center gap-3"
          >
            <LogIn className="w-5 h-5" /> Sign In
          </button>
        </div>
      </div>
    );
  }

  if (role !== 'admin') {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-4">
        <div className="bg-white dark:bg-slate-900 p-10 rounded-[2rem] shadow-xl max-w-md w-full text-center border border-slate-100 dark:border-slate-800">
          <ShieldAlert className="w-10 h-10 text-amber-600 mx-auto mb-6" />
          <h2 className="text-3xl font-display font-bold text-slate-900 dark:text-white mb-4">Staff Only</h2>
          <p className="text-slate-600 dark:text-slate-300">Analytics are restricted to staff accounts.</p>
        </div>
      </div>
    );
  }

  const maxTotal = Math.max(1, ...(trends?.series.map((b) => b.total) ?? [1]));

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-10">
          <h1 className="text-4xl font-display font-bold text-slate-900 dark:text-white mb-2">Attendance Analytics</h1>
          <p className="text-slate-600 dark:text-slate-300">Institution-wide overview and the last 30 days of attendance.</p>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-10 h-10 text-indigo-600 animate-spin" />
          </div>
        ) : error ? (
          <div role="alert" className="p-6 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-rose-800 dark:text-rose-200">
            {error}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-10">
              <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm">
                <p className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">Students enrolled</p>
                <p className="text-3xl font-bold text-slate-900 dark:text-white">{overview?.studentsTotal ?? 0}</p>
              </div>
              <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm">
                <p className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">Attendance today</p>
                <p className="text-3xl font-bold text-slate-900 dark:text-white">{overview?.attendanceToday ?? 0}</p>
              </div>
              <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm">
                <p className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">Total (30 days)</p>
                <p className="text-3xl font-bold text-slate-900 dark:text-white">{trends?.total ?? 0}</p>
              </div>
            </div>

            {overview?.byMethod && Object.keys(overview.byMethod).length > 0 && (
              <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm mb-10">
                <h2 className="text-lg font-bold text-slate-900 dark:text-white mb-4">By method</h2>
                <ul className="space-y-2">
                  {Object.entries(overview.byMethod).map(([method, count]) => (
                    <li key={method} className="flex items-center justify-between text-sm">
                      <span className="text-slate-700 dark:text-slate-300">{method}</span>
                      <span className="font-bold text-slate-900 dark:text-white">{count}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm">
              <h2 className="text-lg font-bold text-slate-900 dark:text-white mb-4">Daily trend (30 days)</h2>
              {trends && trends.series.length > 0 ? (
                <ul className="space-y-2" aria-label="Daily attendance totals">
                  {trends.series.map((bucket) => (
                    <li key={bucket.period} className="flex items-center gap-3">
                      <span className="w-24 text-xs text-slate-500 dark:text-slate-400 tabular-nums">{bucket.period}</span>
                      <div className="flex-1 bg-slate-100 dark:bg-slate-800 rounded-full h-3 overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-indigo-600 to-blue-600 rounded-full"
                          style={{ width: `${(bucket.total / maxTotal) * 100}%` }}
                          aria-hidden="true"
                        />
                      </div>
                      <span className="w-10 text-right text-xs font-bold text-slate-900 dark:text-white tabular-nums">
                        {bucket.total}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500 dark:text-slate-400">No attendance recorded in the selected window.</p>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
