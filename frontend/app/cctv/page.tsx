'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '@/components/AuthProvider';
import { motion } from 'motion/react';
import { Camera, Settings, RefreshCw, AlertCircle, ShieldAlert, Users, Video, CheckCircle2, Square, Play, Loader2, Pause, Activity } from 'lucide-react';
import { toast } from 'sonner';
import { db } from '@/lib/firebase';
import { collection, addDoc, getDocs } from 'firebase/firestore';
import { handleFirestoreError, OperationType } from '@/lib/firestore-error';
import type { StudentData, CCTVDetectResponse, CCTVProcessedFace } from '@/lib/types';
import { getBackendUrl } from '@/lib/utils';
import { authHeaders, buildAttendanceRecord } from '@/lib/attendance';

type PipelineState = 'idle' | 'live' | 'paused';

export default function CCTVPage() {
  const { user, loading, role } = useAuth();
  const [streamUrl, setStreamUrl] = useState(getBackendUrl('/api/pi/stream'));
  const [customUrl, setCustomUrl] = useState('');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [pipeline, setPipeline] = useState<PipelineState>('idle');
  const [detectedFaces, setDetectedFaces] = useState<CCTVProcessedFace[]>([]);
  const [registeredStudents, setRegisteredStudents] = useState<StudentData[]>([]);
  const [loggedUids, setLoggedUids] = useState<string[]>([]);
  const [streamOk, setStreamOk] = useState(true);
  const [engineReady, setEngineReady] = useState<boolean | null>(null);
  const [enrolledCount, setEnrolledCount] = useState<number | null>(null);

  const detectionIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const loggedStudentsRef = useRef<Set<string>>(new Set());
  const inFlightRef = useRef(false);
  const registeredRef = useRef<StudentData[]>([]);
  const [cameraError, setCameraError] = useState<string | null>(null);

  useEffect(() => {
    registeredRef.current = registeredStudents;
  }, [registeredStudents]);

  useEffect(() => {
    const loadData = async () => {
      try {
        const querySnapshot = await getDocs(collection(db, 'students'));
        const students = querySnapshot.docs.map(doc => ({ id: doc.id, ...doc.data() } as StudentData));
        setRegisteredStudents(students);
      } catch (error) {
        console.error("Error loading students:", error);
      }
      try {
        const headers = await authHeaders();
        const res = await fetch(getBackendUrl('/api/health'), { headers });
        if (res.ok) {
          const h = await res.json();
          setEngineReady(!!h.face_model_ready && !!h.vector_db_ready);
          setEnrolledCount(typeof h.students_in_db === 'number' ? h.students_in_db : null);
        } else {
          setEngineReady(false);
        }
      } catch {
        setEngineReady(false);
      }
    };
    loadData();

    return () => {
      if (detectionIntervalRef.current) {
        clearInterval(detectionIntervalRef.current);
      }
    };
  }, []);

  const logAttendance = useCallback(async (student: StudentData) => {
    if (!student.uid) return;
    if (loggedStudentsRef.current.has(student.uid)) return;
    // Only call this with a backend-matched student (see detection handler).
    try {
      loggedStudentsRef.current.add(student.uid);
      const payload = await buildAttendanceRecord(
        {
          uid: student.uid,
          name: student.name,
          rollNumber: student.rollNumber || 'N/A',
          department: student.department || 'N/A',
          year: student.year || 'N/A',
          semester: student.semester || 'N/A',
        },
        'cctv_stream'
      );
      await addDoc(collection(db, 'attendance'), payload);
      setLoggedUids((prev) => (prev.includes(student.uid) ? prev : [...prev, student.uid]));
      toast.success(`Attendance recorded for ${student.name}`);
    } catch (error) {
      handleFirestoreError(error, OperationType.CREATE, 'attendance');
      loggedStudentsRef.current.delete(student.uid);
    }
  }, []);

  const pollOnce = useCallback(async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    try {
      const headers = await authHeaders();
      const response = await fetch(getBackendUrl('/api/pi/detect'), { headers });
      if (!response.ok) {
        const detail = await response.text().catch(() => '');
        setCameraError(`Detection unavailable (${response.status}). No attendance was recorded. ${detail}`.slice(0, 300));
        setDetectedFaces([]);
        return;
      }
      setCameraError(null);
      const data: CCTVDetectResponse = await response.json();

      if (data.faces_detected > 0) {
        const processedFaces: CCTVProcessedFace[] = (data.face_data || []).map((face) => {
          // Only a backend-provided match counts as an identity. Unknown faces are shown but never logged.
          const matchedUid: string | null = (face as unknown as { match?: { uid?: string } }).match?.uid ?? null;
          const recognized = matchedUid
            ? registeredRef.current.find((s) => s.uid === matchedUid) ?? null
            : null;

          if (recognized) {
            void logAttendance(recognized);
          }

          return {
            ...face,
            student: recognized,
            frame_width: data.frame_width || 640,
            frame_height: data.frame_height || 480
          };
        });
        setDetectedFaces(processedFaces);
      } else {
        setDetectedFaces([]);
      }
    } catch {
      // Camera/API failure: visible error, zero attendance records.
      setCameraError('Camera or recognition service unreachable. No attendance was recorded.');
      setDetectedFaces([]);
    } finally {
      inFlightRef.current = false;
    }
  }, [logAttendance]);

  const startDetection = () => {
    if (detectionIntervalRef.current) clearInterval(detectionIntervalRef.current);
    setPipeline('live');
    toast.success('Started AI detection pipeline.');
    detectionIntervalRef.current = setInterval(() => { void pollOnce(); }, 2000);
  };

  const pauseDetection = () => {
    if (detectionIntervalRef.current) clearInterval(detectionIntervalRef.current);
    detectionIntervalRef.current = null;
    setPipeline('paused');
    toast.info('Paused AI detection. Stream continues; no new recognition runs.');
  };

  const stopDetection = () => {
    if (detectionIntervalRef.current) clearInterval(detectionIntervalRef.current);
    detectionIntervalRef.current = null;
    setPipeline('idle');
    setDetectedFaces([]);
    loggedStudentsRef.current.clear();
    setLoggedUids([]);
    toast.info('Stopped AI detection pipeline.');
  };

  if (loading) {
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
        <div className="bg-white dark:bg-slate-900 p-10 rounded-[2rem] shadow-xl border border-slate-100 dark:border-slate-800 max-w-md w-full text-center">
          <ShieldAlert className="w-12 h-12 text-rose-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Access Denied</h2>
          <p className="text-slate-600 dark:text-slate-300">You must be logged in to access the CCTV monitoring dashboard.</p>
        </div>
      </div>
    );
  }

  if (role !== 'admin') {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-4">
        <div className="bg-white dark:bg-slate-900 p-10 rounded-[2rem] shadow-xl border border-slate-100 dark:border-slate-800 max-w-md w-full text-center">
          <ShieldAlert className="w-12 h-12 text-amber-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Staff Only</h2>
          <p className="text-slate-600 dark:text-slate-300">CCTV monitoring is available to staff accounts. Students can use Verify and Records.</p>
        </div>
      </div>
    );
  }

  const handleApplyCustomUrl = (e: React.FormEvent) => {
    e.preventDefault();
    if (customUrl) {
      setStreamUrl(customUrl);
      setStreamOk(true);
      toast.success('Stream URL updated successfully');
      setIsSettingsOpen(false);
    }
  };

  const handleResetUrl = () => {
    setStreamUrl(getBackendUrl('/api/pi/stream'));
    setCustomUrl('');
    setStreamOk(true);
    toast.info('Reset to default PiCamera stream');
  };

  const recognizedCount = detectedFaces.filter((f) => f.student).length;
  const unknownCount = detectedFaces.length - recognizedCount;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 py-8 px-4 sm:px-6 lg:px-8 page-fade">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
          >
            <h1 className="text-3xl font-display font-bold text-slate-900 dark:text-white flex items-center gap-3">
              <Video className="w-8 h-8 text-indigo-600 dark:text-indigo-400" />
              Live CCTV Monitoring
            </h1>
            <p className="text-slate-600 dark:text-slate-300 mt-1">Only backend-verified matches create attendance. Unknown faces go to review.</p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex flex-wrap gap-3"
          >
            <button
              onClick={() => setIsSettingsOpen(!isSettingsOpen)}
              className="px-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 rounded-xl font-semibold hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors flex items-center gap-2 shadow-sm"
            >
              <Settings className="w-4 h-4" />
              Stream
            </button>
            {pipeline === 'live' ? (
              <>
                <button
                  onClick={pauseDetection}
                  className="px-5 py-2 rounded-xl font-semibold flex items-center gap-2 shadow-md transition-all bg-amber-100 text-amber-800 hover:bg-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:hover:bg-amber-950"
                >
                  <Pause className="w-4 h-4" /> Pause
                </button>
                <button
                  onClick={stopDetection}
                  className="px-5 py-2 rounded-xl font-semibold flex items-center gap-2 shadow-md transition-all bg-rose-100 text-rose-700 hover:bg-rose-200 dark:bg-rose-950/60 dark:text-rose-300 dark:hover:bg-rose-950"
                >
                  <Square className="w-4 h-4" /> Stop
                </button>
              </>
            ) : (
              <button
                onClick={startDetection}
                className="px-5 py-2 rounded-xl font-semibold flex items-center gap-2 shadow-md transition-all bg-indigo-600 text-white hover:bg-indigo-700 hover:-translate-y-0.5"
              >
                <Play className="w-4 h-4" /> {pipeline === 'paused' ? 'Resume Detection' : 'Start Detection'}
              </button>
            )}
          </motion.div>
        </div>

        {/* Status toolbar: stream, engine, enrollment */}
        <div className="grid sm:grid-cols-3 gap-4 mb-6">
          <StatusChip
            label="Camera stream"
            value={streamOk ? 'Connected' : 'Unavailable'}
            good={streamOk}
          />
          <StatusChip
            label="Recognition engine"
            value={engineReady === null ? 'Checking…' : engineReady ? 'Ready' : 'Down'}
            good={engineReady === true}
          />
          <StatusChip
            label="Enrolled students"
            value={enrolledCount === null ? 'Unknown' : String(enrolledCount)}
            good={enrolledCount !== null && enrolledCount > 0}
          />
        </div>

        {isSettingsOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="bg-white dark:bg-slate-900 p-6 rounded-2xl shadow-md border border-slate-200 dark:border-slate-700 mb-6 overflow-hidden"
          >
            <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">Stream Configuration</h3>
            <form onSubmit={handleApplyCustomUrl} className="flex flex-col sm:flex-row gap-4">
              <div className="flex-1">
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">IP Camera / MJPEG Stream URL</label>
                <input
                  type="url"
                  placeholder="e.g., http://192.168.1.100:8080/video"
                  value={customUrl}
                  onChange={(e) => setCustomUrl(e.target.value)}
                  className="w-full px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                />
              </div>
              <div className="flex items-end gap-2">
                <button type="submit" className="px-6 py-2 bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 rounded-xl font-semibold hover:bg-slate-800 dark:hover:bg-white transition-colors">Apply</button>
                <button type="button" onClick={handleResetUrl} className="px-4 py-2 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded-xl font-semibold hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors">Reset</button>
              </div>
            </form>
            <div className="mt-4 flex items-start gap-2 text-sm text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/50 p-3 rounded-lg border border-amber-100 dark:border-amber-900">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <p>The stream must be an MJPEG feed or a direct image URL that updates. Changing it only changes the display — recognition always runs on the backend camera frame.</p>
            </div>
          </motion.div>
        )}

        {cameraError && (
          <div className="mb-4 flex items-start gap-2 text-sm text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/50 p-3 rounded-lg border border-rose-100 dark:border-rose-900">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <p>{cameraError}</p>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="lg:col-span-2 bg-slate-900 rounded-[2rem] overflow-hidden shadow-2xl border-4 border-slate-800 dark:border-slate-700 relative aspect-video flex items-center justify-center"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={streamUrl}
              alt="Live CCTV Stream"
              className="w-full h-full object-cover bg-black"
              onError={(e) => {
                const img = e.target as HTMLImageElement;
                img.style.display = 'none';
                img.parentElement?.classList.add('stream-error');
                setStreamOk(false);
              }}
              onLoad={(e) => {
                const img = e.target as HTMLImageElement;
                img.style.display = 'block';
                img.parentElement?.classList.remove('stream-error');
                setStreamOk(true);
              }}
            />

            <div className="absolute inset-0 hidden [.stream-error_&]:flex flex-col items-center justify-center text-slate-400">
              <Camera className="w-16 h-16 mb-4 opacity-50" />
              <p className="text-lg font-semibold">Stream Unavailable</p>
              <p className="text-sm opacity-75 mt-2 max-w-md text-center">
                Could not connect to the camera feed at <br/>
                <span className="font-mono text-xs bg-slate-800 px-2 py-1 rounded mt-2 inline-block">{streamUrl}</span>
              </p>
            </div>

            <div className="absolute top-4 left-4 flex items-center gap-2 px-3 py-1.5 bg-black/50 backdrop-blur-md rounded-lg border border-white/10 z-10">
              <div className={`w-2 h-2 rounded-full ${pipeline === 'live' ? 'bg-rose-500 animate-pulse' : pipeline === 'paused' ? 'bg-amber-400' : 'bg-slate-500'}`}></div>
              <span className="text-white text-xs font-bold tracking-wider uppercase">
                {pipeline === 'live' ? 'Live · detecting' : pipeline === 'paused' ? 'Paused' : 'Idle'}
              </span>
            </div>

            {detectedFaces.map((face, idx) => {
              const [x, y, w, h] = face.box;
              const left = `${(x / face.frame_width) * 100}%`;
              const top = `${(y / face.frame_height) * 100}%`;
              const width = `${(w / face.frame_width) * 100}%`;
              const height = `${(h / face.frame_height) * 100}%`;
              const student = face.student;
              const isRecognized = !!student;

              return (
                <div
                  key={idx}
                  className={`absolute border-2 group cursor-pointer transition-all z-20 ${isRecognized ? 'border-emerald-500 bg-emerald-500/20' : 'border-amber-500 bg-amber-500/20'}`}
                  style={{ left, top, width, height }}
                >
                  <div className="absolute -top-12 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-slate-900 text-white text-sm font-bold px-4 py-2 rounded-xl whitespace-nowrap pointer-events-auto shadow-xl border border-slate-700 flex items-center gap-2">
                    {isRecognized && student ? (
                      <><CheckCircle2 className="w-4 h-4 text-emerald-400" /> {student.name}</>
                    ) : (
                      <><AlertCircle className="w-4 h-4 text-amber-400" /> Unknown · needs review</>
                    )}
                    <div className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-slate-900 rotate-45 border-r border-b border-slate-700"></div>
                  </div>
                </div>
              );
            })}
          </motion.div>

          {/* Detection review panel */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="bg-white dark:bg-slate-900 rounded-[2rem] shadow-xl shadow-slate-200/50 dark:shadow-none border border-slate-100 dark:border-slate-800 p-6 flex flex-col"
          >
            <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-1 flex items-center gap-2">
              <Users className="w-5 h-5 text-indigo-600 dark:text-indigo-400" /> Detections
            </h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
              {pipeline === 'idle' ? 'Start detection to scan the stream.' : `${detectedFaces.length} face(s) · ${recognizedCount} verified · ${unknownCount} need review`}
            </p>
            <div className="flex-1 space-y-3 overflow-y-auto max-h-[420px]">
              {detectedFaces.length === 0 ? (
                <div className="text-center py-10 bg-slate-50 dark:bg-slate-800/60 rounded-2xl border border-slate-100 dark:border-slate-700/60">
                  <Activity className="w-8 h-8 text-slate-300 dark:text-slate-600 mx-auto mb-2" />
                  <p className="text-slate-400 dark:text-slate-500 text-sm italic">No faces in the current frame.</p>
                </div>
              ) : (
                detectedFaces.map((face, idx) => {
                  const student = face.student;
                  const match = (face as unknown as { match?: { distance?: number } }).match;
                  const logged = !!student && loggedUids.includes(student.uid);
                  return (
                    <div
                      key={idx}
                      className={`p-3 rounded-xl border flex items-center gap-3 ${
                        student
                          ? 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-100 dark:border-emerald-900'
                          : 'bg-amber-50 dark:bg-amber-950/40 border-amber-100 dark:border-amber-900'
                      }`}
                    >
                      {student ? (
                        <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
                      ) : (
                        <AlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0" />
                      )}
                      <div className="min-w-0">
                        <p className={`font-bold truncate ${student ? 'text-emerald-900 dark:text-emerald-200' : 'text-amber-900 dark:text-amber-200'}`}>
                          {student ? student.name : 'Unknown — needs review'}
                        </p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          {student
                            ? `${typeof match?.distance === 'number' ? `distance ${match.distance.toFixed(3)} · ` : ''}${logged ? 'attendance recorded' : 'recording attendance…'}`
                            : 'no verified match — nothing recorded'}
                        </p>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
            <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
              <RefreshCw className="w-4 h-4" />
              Detection does not equal attendance — only verified matches are recorded, once per session.
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}

function StatusChip({ label, value, good }: { label: string; value: string; good: boolean }) {
  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 rounded-2xl px-4 py-3 shadow-sm flex items-center gap-3">
      <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${good ? 'bg-emerald-500' : 'bg-amber-500'}`} />
      <div>
        <p className="text-[11px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">{label}</p>
        <p className="font-bold text-slate-900 dark:text-white text-sm">{value}</p>
      </div>
    </div>
  );
}
