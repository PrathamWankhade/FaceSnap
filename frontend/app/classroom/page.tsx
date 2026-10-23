'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';
import Webcam from 'react-webcam';
import Link from 'next/link';
import { Camera, Users, Upload, CheckCircle2, AlertCircle, Loader2, Play, Square, Scan, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/components/AuthProvider';
import { api, ApiError } from '@/lib/api';
import type { StudentData, DetectWebcamResponse, FaceMatch, WebcamUIDetection } from '@/lib/types';
import { getBackendUrl } from '@/lib/utils';
import { authHeaders, markAttendance } from '@/lib/attendance';
import { fitFrame } from '@/lib/overlay';
import { motion } from 'motion/react';

export default function ClassroomPage() {
  const { user, loading, role } = useAuth();
  const [mode, setMode] = useState<'live' | 'upload'>('live');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isLiveStreamActive, setIsLiveStreamActive] = useState(false);
  const [detectedFaces, setDetectedFaces] = useState<WebcamUIDetection[]>([]);
  const [registeredStudents, setRegisteredStudents] = useState<StudentData[]>([]);
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const [modelsLoaded, setModelsLoaded] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [syncedCount, setSyncedCount] = useState<number | null>(null);
  const [uploadResults, setUploadResults] = useState<{ logged: string[]; unrecognized: number; faces: number } | null>(null);

  const webcamRef = useRef<Webcam>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const detectionIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const loggedStudentsRef = useRef<Set<string>>(new Set());
  const inFlightRef = useRef(false);
  const prevBoxesRef = useRef<Map<number, { x: number; y: number; w: number; h: number }>>(new Map());

  useEffect(() => {
    const loadData = async () => {
      try {
        const [studentsRes, health] = await Promise.all([
          api.get<{ students: StudentData[] }>('/api/students'),
          fetch(getBackendUrl('/api/health'), { headers: await authHeaders() })
            .then((res) => (res.ok ? res.json() : null))
            .catch(() => null),
        ]);
        setRegisteredStudents(studentsRes.students);

        if (health) {
          const ready = !!health.face_model_ready && !!health.vector_db_ready;
          setModelsLoaded(ready);
          setSyncedCount(typeof health.embeddings_indexed === 'number' ? health.embeddings_indexed : null);
          setSyncError(
            ready
              ? null
              : 'Recognition engine or vector index is offline — live matching is unavailable. Check the backend and reload.'
          );
        } else {
          setSyncError('Recognition engine unreachable — live matching is unavailable. Check that the backend is running, then reload.');
        }
      } catch (error) {
        console.error('Error loading data:', error);
        toast.error('Failed to initialize system.');
        setSyncError(
          error instanceof ApiError ? error.message : 'Could not load enrolled students from the backend.'
        );
      }
    };

    loadData();

    return () => {
      if (detectionIntervalRef.current) {
        clearInterval(detectionIntervalRef.current);
      }
    };
  }, []);

  const logAttendance = useCallback(async (student: { uid: string; name: string; rollNo?: string; rollNumber?: string }) => {
    if (!student.uid) return;
    if (loggedStudentsRef.current.has(student.uid)) return;

    try {
      loggedStudentsRef.current.add(student.uid);
      await markAttendance({ studentUid: student.uid, method: 'doorway_batch' });
      toast.success(`Attendance logged for ${student.name}`);
    } catch (error) {
      console.error('Attendance error:', error);
      toast.error(error instanceof Error ? error.message : 'Could not record attendance.');
      loggedStudentsRef.current.delete(student.uid);
    }
  }, []);

  const clearOverlay = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }, []);

  /**
   * Draw in CSS pixels using the same `object-fit: contain` transform the
   * browser applies to the <video>. Sizing the canvas bitmap to the camera
   * resolution and letting CSS stretch it (the previous behaviour) made boxes
   * drift off the face whenever the camera was not exactly 16:9.
   */
  const drawOverlay = useCallback((
    boxes: Array<{ box: [number, number, number, number]; student: FaceMatch | null }>,
    frameWidth: number,
    frameHeight: number
  ) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const pixelWidth = Math.round(rect.width * dpr);
    const pixelHeight = Math.round(rect.height * dpr);
    if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
      canvas.width = pixelWidth;
      canvas.height = pixelHeight;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);

    const { scale, offsetX, offsetY } = fitFrame(frameWidth, frameHeight, rect.width, rect.height, 'contain');

    boxes.forEach(({ box, student }) => {
      const [x, y, w, h] = box;
      const strokeX = offsetX + x * scale;
      const strokeY = offsetY + y * scale;
      const strokeW = w * scale;
      const strokeH = h * scale;

      ctx.shadowColor = student ? 'rgba(16, 185, 129, 0.5)' : 'rgba(245, 158, 11, 0.5)';
      ctx.shadowBlur = 12;
      ctx.strokeStyle = student ? '#10b981' : '#f59e0b';
      ctx.lineWidth = 3;
      ctx.strokeRect(strokeX, strokeY, strokeW, strokeH);
      ctx.shadowBlur = 0;

      const label = student ? student.name : 'Unknown · review';
      ctx.font = 'bold 14px system-ui, sans-serif';
      const textWidth = ctx.measureText(label).width;
      const labelH = 28;
      const labelY = strokeY - labelH > 0 ? strokeY - labelH : strokeY + strokeH;

      ctx.fillStyle = student ? '#10b981' : '#f59e0b';
      ctx.beginPath();
      ctx.roundRect(strokeX, labelY, textWidth + 16, labelH, 6);
      ctx.fill();

      ctx.fillStyle = '#ffffff';
      ctx.fillText(label, strokeX + 8, labelY + 19);
    });
  }, []);

  const runDetection = useCallback(async () => {
    if (inFlightRef.current) return;

    const imageSrc = webcamRef.current?.getScreenshot();
    if (!imageSrc) return;

    inFlightRef.current = true;
    try {
      const headers = await authHeaders();
      const response = await fetch(getBackendUrl('/api/detect_webcam'), {
        method: 'POST',
        headers,
        body: JSON.stringify({ image_base64: imageSrc })
      });

      if (!response.ok) throw new Error(`Detection failed (${response.status})`);

      const data: DetectWebcamResponse = await response.json();
      const currentDetections: WebcamUIDetection[] = [];
      const newBoxes = new Map<number, { x: number; y: number; w: number; h: number }>();
      const overlayBoxes: Array<{ box: [number, number, number, number]; student: FaceMatch | null }> = [];
      const alpha = 0.4;

      data.face_data.forEach((face, i) => {
        const [rawX, rawY, rawW, rawH] = face.box;
        const prev = prevBoxesRef.current.get(i);

        const x = prev ? Math.round(prev.x + alpha * (rawX - prev.x)) : rawX;
        const y = prev ? Math.round(prev.y + alpha * (rawY - prev.y)) : rawY;
        const w = prev ? Math.round(prev.w + alpha * (rawW - prev.w)) : rawW;
        const h = prev ? Math.round(prev.h + alpha * (rawH - prev.h)) : rawH;

        newBoxes.set(i, { x, y, w, h });
        currentDetections.push({
          box: { x, y, width: w, height: h },
          isRecognized: !!face.match,
          student: face.match
        });
        overlayBoxes.push({ box: [x, y, w, h], student: face.match });

        if (face.match) {
          void logAttendance(face.match);
        }
      });

      prevBoxesRef.current = newBoxes;
      setDetectedFaces(currentDetections);
      drawOverlay(overlayBoxes, data.frame_width, data.frame_height);
    } catch {
      prevBoxesRef.current.clear();
      clearOverlay();
      setDetectedFaces([]);
    } finally {
      inFlightRef.current = false;
    }
  }, [clearOverlay, drawOverlay, logAttendance]);

  // Start/stop the polling loop from state, not from the <video> onPlay event.
  // onPlay fires once, often before models finish loading, so the old loop
  // could silently never start (or run with a stale "inactive" flag).
  useEffect(() => {
    if (!isLiveStreamActive || !modelsLoaded) return;

    void runDetection();
    const id = setInterval(() => { void runDetection(); }, 1000);
    detectionIntervalRef.current = id;

    return () => {
      clearInterval(id);
      detectionIntervalRef.current = null;
    };
  }, [isLiveStreamActive, modelsLoaded, runDetection]);

  const toggleLiveStream = () => {
    if (isLiveStreamActive) {
      setIsLiveStreamActive(false);
      setDetectedFaces([]);
      loggedStudentsRef.current.clear();
      prevBoxesRef.current.clear();
      clearOverlay();
    } else {
      setIsLiveStreamActive(true);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setUploadedImage(reader.result as string);
        setUploadResults(null);
      };
      reader.readAsDataURL(file);
    }
  };

  const processUploadedImage = async () => {
    if (!uploadedImage) return;
    setIsProcessing(true);
    setUploadResults(null);

    try {
      // Real recognition: send the group photo to the backend and log each matched student once.
      const headers = await authHeaders();
      const response = await fetch(getBackendUrl('/api/detect_webcam'), {
        method: 'POST',
        headers,
        body: JSON.stringify({ image_base64: uploadedImage }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail || `Recognition failed (${response.status})`);
      }
      const data: DetectWebcamResponse = await response.json();
      const matches = (data.face_data || []).map((f) => f.match).filter((m) => !!m);
      const unique = new Map(matches.map((m) => [m!.uid, m!]));
      const loggedNames: string[] = [];
      let logged = 0;
      for (const m of unique.values()) {
        const before = loggedStudentsRef.current.size;
        await logAttendance(m);
        if (loggedStudentsRef.current.size > before) {
          logged += 1;
          loggedNames.push(m.name);
        }
      }
      setUploadResults({ logged: loggedNames, unrecognized: data.faces_detected - unique.size, faces: data.faces_detected });
      if (data.faces_detected === 0) {
        toast.info('No faces detected in the uploaded photo.');
      } else if (logged === 0) {
        toast.warning(`${data.faces_detected} face(s) detected, no recognized students.`);
      } else {
        toast.success(`Group photo processed: ${logged} attendance record(s) from ${data.faces_detected} face(s).`);
      }
    } catch (e) {
      console.error("Processing error", e);
      toast.error(e instanceof Error ? e.message : "Failed to process group photo.");
    } finally {
      setIsProcessing(false);
    }
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
        <div className="bg-white dark:bg-slate-900 p-10 rounded-[2rem] shadow-xl shadow-slate-200/50 dark:shadow-none border border-slate-100 dark:border-slate-800 max-w-md w-full text-center">
          <AlertCircle className="w-16 h-16 text-amber-500 mx-auto mb-6" />
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">Access Denied</h2>
          <p className="text-slate-600 dark:text-slate-300">Please sign in to access the Classroom Attendance portal.</p>
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
          <p className="text-slate-600 dark:text-slate-300">Batch attendance is available to staff accounts. Students can use Verify and Records.</p>
        </div>
      </div>
    );
  }

  const recognizedFaces = detectedFaces.filter(f => f.isRecognized);
  const unknownFaces = detectedFaces.filter(f => !f.isRecognized);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 py-12 px-4 sm:px-6 lg:px-8 page-fade">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <h1 className="text-4xl md:text-5xl font-display font-bold text-slate-900 dark:text-white tracking-tight mb-4">
            Classroom Attendance
          </h1>
          <p className="text-lg text-slate-600 dark:text-slate-300 max-w-2xl mx-auto">
            Monitor doorways in real-time or process group photos for batch attendance.
          </p>
        </motion.div>

        {/* Recognition status toolbar */}
        <div className="grid sm:grid-cols-3 gap-4 mb-8 max-w-4xl mx-auto">
          <div className="bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 rounded-2xl px-4 py-3 shadow-sm flex items-center gap-3">
            <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${modelsLoaded ? 'bg-emerald-500' : syncError ? 'bg-rose-500' : 'bg-amber-500 animate-pulse'}`} />
            <div>
              <p className="text-[11px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">Recognition engine</p>
              <p className="font-bold text-slate-900 dark:text-white text-sm">{modelsLoaded ? 'Ready' : syncError ? 'Unavailable' : 'Syncing…'}</p>
            </div>
          </div>
          <div className="bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 rounded-2xl px-4 py-3 shadow-sm flex items-center gap-3">
            <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${syncedCount ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-600'}`} />
            <div>
              <p className="text-[11px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">Synced embeddings</p>
              <p className="font-bold text-slate-900 dark:text-white text-sm">{syncedCount === null ? '—' : syncedCount}</p>
            </div>
          </div>
          <div className="bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 rounded-2xl px-4 py-3 shadow-sm flex items-center gap-3">
            <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${mode === 'live' && isLiveStreamActive ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300 dark:bg-slate-600'}`} />
            <div>
              <p className="text-[11px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">Live detection</p>
              <p className="font-bold text-slate-900 dark:text-white text-sm">{mode === 'live' && isLiveStreamActive ? 'Running' : 'Stopped'}</p>
            </div>
          </div>
        </div>
        {syncError && (
          <div className="max-w-4xl mx-auto mb-8 flex items-start gap-2 text-sm text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/50 p-3 rounded-xl border border-rose-100 dark:border-rose-900">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <p>{syncError}</p>
          </div>
        )}
        {!syncError && registeredStudents.length === 0 && (
          <div className="max-w-4xl mx-auto mb-8 flex items-start gap-2 text-sm text-amber-800 dark:text-amber-200 bg-amber-50 dark:bg-amber-950/50 p-3 rounded-xl border border-amber-100 dark:border-amber-900">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <p>
              No students are enrolled yet, so every detected face will show as &ldquo;Unknown&rdquo;.{' '}
              <Link href="/register" className="font-bold underline underline-offset-2">
                Register a face
              </Link>{' '}
              to enable matching.
            </p>
          </div>
        )}

        <div className="flex p-1.5 bg-slate-200/50 dark:bg-slate-800/60 backdrop-blur-sm rounded-full mb-10 max-w-md mx-auto shadow-inner">
          <button
            onClick={() => setMode('live')}
            className={`flex-1 py-3 px-6 text-sm font-bold rounded-full transition-all duration-300 flex items-center justify-center gap-2 ${mode === 'live' ? 'bg-white dark:bg-slate-900 text-indigo-700 dark:text-indigo-300 shadow-md' : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'}`}
          >
            <Camera className="w-4 h-4" /> Doorway (Live)
          </button>
          <button
            onClick={() => setMode('upload')}
            className={`flex-1 py-3 px-6 text-sm font-bold rounded-full transition-all duration-300 flex items-center justify-center gap-2 ${mode === 'upload' ? 'bg-white dark:bg-slate-900 text-indigo-700 dark:text-indigo-300 shadow-md' : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'}`}
          >
            <Upload className="w-4 h-4" /> Group Photo
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="lg:col-span-2 bg-white dark:bg-slate-900 rounded-[2.5rem] shadow-xl shadow-slate-200/50 dark:shadow-none border border-slate-100 dark:border-slate-800 overflow-hidden"
          >
            {mode === 'live' ? (
              <div className="p-8">
                <div className="flex justify-between items-center mb-6">
                  <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Live Camera Feed</h2>
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-2 text-sm font-bold text-slate-600 dark:text-slate-300">
                      <span className={`w-3 h-3 rounded-full ${isLiveStreamActive ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300 dark:bg-slate-600'}`}></span>
                      {isLiveStreamActive ? 'Active' : 'Inactive'}
                    </span>
                    <button
                      onClick={toggleLiveStream}
                      className={`px-4 py-2 rounded-full font-bold text-sm flex items-center gap-2 transition-colors ${
                        isLiveStreamActive
                          ? 'bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 hover:bg-rose-200 dark:hover:bg-rose-950'
                          : 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-200 dark:hover:bg-emerald-950'
                      }`}
                    >
                      {isLiveStreamActive ? <><Square className="w-4 h-4" /> Stop</> : <><Play className="w-4 h-4" /> Start</>}
                    </button>
                  </div>
                </div>

                <div className="relative bg-slate-900 aspect-video rounded-3xl overflow-hidden shadow-inner border-4 border-slate-100 dark:border-slate-800">
                  {!modelsLoaded && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center z-30 bg-slate-900/80 backdrop-blur-sm">
                      <Loader2 className="w-10 h-10 text-indigo-500 animate-spin mb-4" />
                      <p className="text-white font-bold">Loading AI Models...</p>
                    </div>
                  )}
                  <Webcam
                    audio={false}
                    ref={webcamRef}
                    screenshotFormat="image/jpeg"
                    videoConstraints={{ facingMode: "user" }}
                    className="absolute inset-0 w-full h-full object-contain"
                  />
                  <canvas
                    ref={canvasRef}
                    className="absolute inset-0 w-full h-full pointer-events-none z-20"
                  />

                  {!isLiveStreamActive && modelsLoaded && (
                    <div className="absolute inset-0 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm z-10">
                      <p className="text-white font-bold text-lg">Click Start to begin live detection</p>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-8">
                <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-6">Upload Group Photo</h2>

                {!uploadedImage ? (
                  <div
                    className="border-4 border-dashed border-slate-200 dark:border-slate-700 rounded-3xl p-12 text-center hover:border-indigo-400 dark:hover:border-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 transition-all cursor-pointer group"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <div className="w-20 h-20 bg-indigo-100 dark:bg-indigo-950/70 rounded-full flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform">
                      <Upload className="w-10 h-10 text-indigo-600 dark:text-indigo-400" />
                    </div>
                    <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-2">Click to upload image</h3>
                    <p className="text-slate-500 dark:text-slate-400">Supports JPG, PNG (Max 10MB)</p>
                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={handleFileUpload}
                      accept="image/*"
                      className="hidden"
                    />
                  </div>
                ) : (
                  <div className="space-y-6">
                    <div className="relative aspect-video rounded-3xl overflow-hidden shadow-inner border-4 border-slate-100 dark:border-slate-800 bg-slate-900">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={uploadedImage} alt="Uploaded Group" className="w-full h-full object-contain" />
                      {isProcessing && (
                        <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm flex flex-col items-center justify-center">
                          <Loader2 className="w-12 h-12 text-white animate-spin mb-4" />
                          <p className="text-white font-bold text-lg">Analyzing faces...</p>
                        </div>
                      )}
                    </div>
                    <div className="flex justify-center gap-4">
                      <button
                        onClick={() => { setUploadedImage(null); setUploadResults(null); }}
                        disabled={isProcessing}
                        className="px-6 py-3 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded-full font-bold hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors disabled:opacity-50"
                      >
                        Choose Another
                      </button>
                      <button
                        onClick={processUploadedImage}
                        disabled={isProcessing}
                        className="px-8 py-3 bg-indigo-600 text-white rounded-full font-bold hover:bg-indigo-700 transition-all shadow-md flex items-center gap-2 disabled:opacity-50"
                      >
                        {isProcessing ? <><Loader2 className="w-5 h-5 animate-spin" /> Processing</> : <><Scan className="w-5 h-5" /> Process Image</>}
                      </button>
                    </div>
                    {uploadResults && (
                      <div className="bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-700/60 rounded-2xl p-5">
                        <p className="text-sm font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">
                          Results · {uploadResults.faces} face(s) detected
                        </p>
                        {uploadResults.logged.length > 0 ? (
                          <ul className="space-y-2">
                            {uploadResults.logged.map((name) => (
                              <li key={name} className="flex items-center gap-3 bg-emerald-50 dark:bg-emerald-950/40 p-3 rounded-xl border border-emerald-100 dark:border-emerald-900">
                                <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
                                <span className="font-bold text-emerald-900 dark:text-emerald-200">{name}</span>
                                <span className="ml-auto text-xs font-bold text-emerald-700 dark:text-emerald-300">recorded</span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-slate-400 dark:text-slate-500 text-sm italic">No recognized students — nothing was recorded.</p>
                        )}
                        {uploadResults.unrecognized > 0 && (
                          <p className="mt-3 text-xs font-medium text-amber-700 dark:text-amber-300">
                            {uploadResults.unrecognized} face(s) need review — no verified match, nothing recorded.
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="bg-white dark:bg-slate-900 rounded-[2.5rem] shadow-xl shadow-slate-200/50 dark:shadow-none border border-slate-100 dark:border-slate-800 p-8 flex flex-col"
          >
            <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-6 flex items-center gap-2">
              <Users className="w-5 h-5 text-indigo-600 dark:text-indigo-400" /> Detection Status
            </h3>

            <div className="flex-1">
              {mode === 'live' ? (
                <div className="space-y-6">
                  <div className="grid grid-cols-3 gap-3">
                    <div className="bg-slate-50 dark:bg-slate-800/60 p-4 rounded-2xl border border-slate-100 dark:border-slate-700/60 text-center">
                      <p className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">Detected</p>
                      <p className="text-3xl font-display font-bold text-slate-900 dark:text-white">{detectedFaces.length}</p>
                    </div>
                    <div className="bg-emerald-50 dark:bg-emerald-950/40 p-4 rounded-2xl border border-emerald-100 dark:border-emerald-900 text-center">
                      <p className="text-[11px] font-bold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider mb-1">Verified</p>
                      <p className="text-3xl font-display font-bold text-emerald-700 dark:text-emerald-300">{recognizedFaces.length}</p>
                    </div>
                    <div className="bg-amber-50 dark:bg-amber-950/40 p-4 rounded-2xl border border-amber-100 dark:border-amber-900 text-center">
                      <p className="text-[11px] font-bold text-amber-600 dark:text-amber-400 uppercase tracking-wider mb-1">Review</p>
                      <p className="text-3xl font-display font-bold text-amber-700 dark:text-amber-300">{unknownFaces.length}</p>
                    </div>
                  </div>

                  <div>
                    <p className="text-sm font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-4">Verified · attendance recorded</p>
                    {recognizedFaces.length > 0 ? (
                      <ul className="space-y-3">
                        {recognizedFaces.map((face, idx) => {
                          const matchedStudent = face.student;
                          return (
                            <li key={idx} className="flex items-center gap-3 bg-emerald-50 dark:bg-emerald-950/40 p-3 rounded-xl border border-emerald-100 dark:border-emerald-900">
                              <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                              <span className="font-bold text-emerald-900 dark:text-emerald-200">{matchedStudent?.name || 'Unknown'}</span>
                            </li>
                          );
                        })}
                      </ul>
                    ) : (
                      <p className="text-slate-400 dark:text-slate-500 text-sm italic">No verified faces currently in view.</p>
                    )}
                  </div>

                  {unknownFaces.length > 0 && (
                    <div>
                      <p className="text-sm font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-4">Needs review · nothing recorded</p>
                      <ul className="space-y-3">
                        {unknownFaces.map((_, idx) => (
                          <li key={idx} className="flex items-center gap-3 bg-amber-50 dark:bg-amber-950/40 p-3 rounded-xl border border-amber-100 dark:border-amber-900">
                            <AlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-400" />
                            <span className="font-bold text-amber-900 dark:text-amber-200">Unknown face {detectedFaces.length > 1 ? `#${idx + 1}` : ''}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-4">
                  <p className="text-slate-600 dark:text-slate-300 text-sm leading-relaxed">
                    Upload a clear group photo. Face detection and ArcFace matching identify enrolled students; only verified matches are recorded, once each.
                  </p>
                  <div className="bg-amber-50 dark:bg-amber-950/40 p-4 rounded-xl border border-amber-100 dark:border-amber-900 flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                    <p className="text-xs text-amber-800 dark:text-amber-200 font-medium">For best results, ensure the photo is well-lit and faces are clearly visible. Unrecognized faces are listed for review, never auto-recorded.</p>
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
