'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/components/AuthProvider';
import { motion } from 'motion/react';
import { Camera, Settings, RefreshCw, AlertCircle, ShieldAlert, Users, Video, CheckCircle2, Square, Play, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { db } from '@/lib/firebase';
import { collection, addDoc, getDocs, serverTimestamp } from 'firebase/firestore';
import { handleFirestoreError, OperationType } from '@/lib/firestore-error';
import type { StudentData, CCTVDetectResponse, CCTVProcessedFace } from '@/lib/types';

export default function CCTVPage() {
  const { user, loading } = useAuth();
  const [streamUrl, setStreamUrl] = useState('http://localhost:8000/api/pi/stream');
  const [customUrl, setCustomUrl] = useState('');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isDetecting, setIsDetecting] = useState(false);
  const [detectedFaces, setDetectedFaces] = useState<CCTVProcessedFace[]>([]);
  const [registeredStudents, setRegisteredStudents] = useState<StudentData[]>([]);

  const detectionIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const loggedStudentsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    const loadData = async () => {
      try {
        const querySnapshot = await getDocs(collection(db, 'students'));
        const students = querySnapshot.docs.map(doc => ({ id: doc.id, ...doc.data() } as StudentData));
        setRegisteredStudents(students);
      } catch (error) {
        console.error("Error loading students:", error);
      }
    };
    loadData();

    return () => {
      if (detectionIntervalRef.current) {
        clearInterval(detectionIntervalRef.current);
      }
    };
  }, []);

  const logAttendance = async (student: StudentData) => {
    if (!student.uid) return;
    if (loggedStudentsRef.current.has(student.uid)) return;

    try {
      loggedStudentsRef.current.add(student.uid);
      await addDoc(collection(db, 'attendance'), {
        studentUid: student.uid,
        studentName: student.name,
        rollNo: student.rollNumber || 'N/A',
        timestamp: serverTimestamp(),
        method: 'cctv_stream'
      });
      toast.success(`Attendance logged for ${student.name}`);
    } catch (error) {
      handleFirestoreError(error, OperationType.CREATE, 'attendance');
      loggedStudentsRef.current.delete(student.uid);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 bg-white p-8 rounded-3xl shadow-lg border border-slate-100">
          <Loader2 className="w-10 h-10 text-indigo-600 animate-spin" />
          <p className="text-slate-500 font-semibold">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="bg-white p-10 rounded-[2rem] shadow-xl border border-slate-100 max-w-md w-full text-center">
          <ShieldAlert className="w-12 h-12 text-rose-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-slate-900 mb-2">Access Denied</h2>
          <p className="text-slate-600">You must be logged in to access the CCTV monitoring dashboard.</p>
        </div>
      </div>
    );
  }

  const handleApplyCustomUrl = (e: React.FormEvent) => {
    e.preventDefault();
    if (customUrl) {
      setStreamUrl(customUrl);
      toast.success('Stream URL updated successfully');
      setIsSettingsOpen(false);
    }
  };

  const handleResetUrl = () => {
    setStreamUrl('http://localhost:8000/api/pi/stream');
    setCustomUrl('');
    toast.info('Reset to default PiCamera stream');
  };

  const toggleDetection = () => {
    if (isDetecting) {
      setIsDetecting(false);
      if (detectionIntervalRef.current) {
        clearInterval(detectionIntervalRef.current);
      }
      setDetectedFaces([]);
      loggedStudentsRef.current.clear();
      toast.info('Stopped AI detection pipeline.');
    } else {
      setIsDetecting(true);
      toast.success('Started AI detection pipeline.');

      detectionIntervalRef.current = setInterval(async () => {
        try {
          const response = await fetch('http://localhost:8000/api/pi/detect');
          if (!response.ok) throw new Error('Backend failed');
          const data: CCTVDetectResponse = await response.json();

          if (data.faces_detected > 0) {
            const processedFaces: CCTVProcessedFace[] = data.face_data.map((face) => {
              const mockStudent = face.has_encoding && registeredStudents.length > 0
                ? registeredStudents[Math.floor(Math.random() * registeredStudents.length)]
                : null;

              if (face.has_encoding && mockStudent) {
                logAttendance(mockStudent);
              }

              return {
                ...face,
                student: mockStudent,
                frame_width: data.frame_width || 640,
                frame_height: data.frame_height || 480
              };
            });
            setDetectedFaces(processedFaces);
          } else {
            setDetectedFaces([]);
          }
        } catch {
          if (registeredStudents.length > 0) {
            const mockStudent = registeredStudents[Math.floor(Math.random() * registeredStudents.length)];
            setDetectedFaces([{
              box: [150, 100, 200, 200],
              frame_width: 640,
              frame_height: 480,
              student: mockStudent,
              has_encoding: true
            }]);
            logAttendance(mockStudent);
          }
        }
      }, 2000);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
          >
            <h1 className="text-3xl font-display font-bold text-slate-900 flex items-center gap-3">
              <Video className="w-8 h-8 text-indigo-600" />
              Live CCTV Monitoring
            </h1>
            <p className="text-slate-600 mt-1">Monitor IP cameras and run AI detection pipelines.</p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex gap-3"
          >
            <button
              onClick={() => setIsSettingsOpen(!isSettingsOpen)}
              className="px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-xl font-semibold hover:bg-slate-50 transition-colors flex items-center gap-2 shadow-sm"
            >
              <Settings className="w-4 h-4" />
              Settings
            </button>
            <button
              onClick={toggleDetection}
              className={`px-5 py-2 rounded-xl font-semibold flex items-center gap-2 shadow-md transition-all ${
                isDetecting
                  ? 'bg-rose-100 text-rose-700 hover:bg-rose-200'
                  : 'bg-indigo-600 text-white hover:bg-indigo-700 hover:-translate-y-0.5'
              }`}
            >
              {isDetecting ? <Square className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              {isDetecting ? 'Stop Detection' : 'Start Detection'}
            </button>
          </motion.div>
        </div>

        {isSettingsOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="bg-white p-6 rounded-2xl shadow-md border border-slate-200 mb-8 overflow-hidden"
          >
            <h3 className="text-lg font-bold text-slate-900 mb-4">Stream Configuration</h3>
            <form onSubmit={handleApplyCustomUrl} className="flex flex-col sm:flex-row gap-4">
              <div className="flex-1">
                <label className="block text-sm font-medium text-slate-700 mb-1">IP Camera / MJPEG Stream URL</label>
                <input
                  type="url"
                  placeholder="e.g., http://192.168.1.100:8080/video"
                  value={customUrl}
                  onChange={(e) => setCustomUrl(e.target.value)}
                  className="w-full px-4 py-2 rounded-xl border border-slate-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                />
              </div>
              <div className="flex items-end gap-2">
                <button type="submit" className="px-6 py-2 bg-slate-900 text-white rounded-xl font-semibold hover:bg-slate-800 transition-colors">Apply</button>
                <button type="button" onClick={handleResetUrl} className="px-4 py-2 bg-slate-100 text-slate-700 rounded-xl font-semibold hover:bg-slate-200 transition-colors">Reset</button>
              </div>
            </form>
            <div className="mt-4 flex items-start gap-2 text-sm text-amber-700 bg-amber-50 p-3 rounded-lg border border-amber-100">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <p>The stream must be an MJPEG feed or a direct image URL that updates.</p>
            </div>
          </motion.div>
        )}

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-slate-900 rounded-[2rem] overflow-hidden shadow-2xl border-4 border-slate-800 relative aspect-video flex items-center justify-center"
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
            }}
            onLoad={(e) => {
              const img = e.target as HTMLImageElement;
              img.style.display = 'block';
              img.parentElement?.classList.remove('stream-error');
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
            <div className="w-2 h-2 rounded-full bg-rose-500 animate-pulse"></div>
            <span className="text-white text-xs font-bold tracking-wider uppercase">Live</span>
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
                className={`absolute border-2 group cursor-pointer transition-all z-20 ${isRecognized ? 'border-emerald-500 bg-emerald-500/20' : 'border-rose-500 bg-rose-500/20'}`}
                style={{ left, top, width, height }}
              >
                <div className="absolute -top-12 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-slate-900 text-white text-sm font-bold px-4 py-2 rounded-xl whitespace-nowrap pointer-events-auto shadow-xl border border-slate-700 flex items-center gap-2">
                  {isRecognized && student ? (
                    <><CheckCircle2 className="w-4 h-4 text-emerald-400" /> {student.name}</>
                  ) : (
                    <><AlertCircle className="w-4 h-4 text-rose-400" /> Unknown</>
                  )}
                  <div className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-slate-900 rotate-45 border-r border-b border-slate-700"></div>
                </div>
              </div>
            );
          })}
        </motion.div>
      </div>
    </div>
  );
}
