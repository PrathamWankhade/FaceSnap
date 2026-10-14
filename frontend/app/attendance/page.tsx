'use client';

import React, { useEffect, useState } from 'react';
import { collection, getDocs, query, orderBy, limit } from 'firebase/firestore';
import { db } from '@/lib/firebase';
import { useAuth } from '@/components/AuthProvider';
import { motion } from 'motion/react';
import { CalendarDays, Clock, UserCheck, Loader2, LogIn } from 'lucide-react';
import type { AttendanceRecord } from '@/lib/types';

function methodBadgeClasses(method?: string): string {
  switch (method) {
    case 'individual_live':
      return 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300';
    case 'doorway_batch':
      return 'bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300';
    case 'cctv_stream':
      return 'bg-violet-50 text-violet-700 dark:bg-violet-950/60 dark:text-violet-300';
    case 'upload':
      return 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300';
    default:
      return 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300';
  }
}

export default function AttendancePage() {
  const { user, loading: authLoading } = useAuth();
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAttendance = async () => {
      if (!user) return;
      try {
        const q = query(
          collection(db, 'attendance'),
          orderBy('timestamp', 'desc'),
          limit(50)
        );
        const snapshot = await getDocs(q);
        const data = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() } as AttendanceRecord));
        setRecords(data);
      } catch (error) {
        console.error("Error fetching attendance:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchAttendance();
  }, [user]);

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 bg-white dark:bg-slate-900 p-8 rounded-3xl shadow-lg border border-slate-100 dark:border-slate-800">
          <Loader2 className="w-10 h-10 text-indigo-600 animate-spin" />
          <p className="text-slate-500 dark:text-slate-400 font-semibold">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-4">
        <p className="text-slate-600 dark:text-slate-300">Please sign in to view attendance records.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-12">
          <h1 className="text-4xl md:text-5xl font-display font-bold text-slate-900 dark:text-white tracking-tight mb-4">Attendance Records</h1>
          <p className="text-lg text-slate-600 dark:text-slate-300">View recent attendance history.</p>
        </motion.div>

        {loading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
          </div>
        ) : records.length === 0 ? (
          <div className="text-center py-20 bg-white dark:bg-slate-900 rounded-[2.5rem] shadow-xl border border-slate-100 dark:border-slate-800">
            <UserCheck className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-500 dark:text-slate-400 text-lg font-medium">No attendance records found.</p>
          </div>
        ) : (
          <div className="bg-white dark:bg-slate-900 rounded-[2.5rem] shadow-xl border border-slate-100 dark:border-slate-800 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800">
                    <th className="text-left px-6 py-4 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Student</th>
                    <th className="text-left px-6 py-4 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Roll No</th>
                    <th className="text-left px-6 py-4 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Method</th>
                    <th className="text-left px-6 py-4 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((record, idx) => (
                    <tr key={record.id || idx} className="border-b border-slate-50 dark:border-slate-800 hover:bg-slate-50/50 dark:bg-slate-900/60 dark:hover:bg-slate-800/60 transition-colors">
                      <td className="px-6 py-4 text-sm font-bold text-slate-900 dark:text-white">{record.studentName || record.name}</td>
                      <td className="px-6 py-4 text-sm text-slate-600 dark:text-slate-300">{record.rollNo || record.rollNumber}</td>
                      <td className="px-6 py-4">
                        <span className={`px-3 py-1 rounded-full text-xs font-bold ${methodBadgeClasses(record.method)}`}>{record.method}</span>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-500 dark:text-slate-400">
                        {record.timestamp?.toDate?.().toLocaleString() || record.timestamp || 'N/A'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
