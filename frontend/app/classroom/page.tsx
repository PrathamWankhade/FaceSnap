'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';
import Webcam from 'react-webcam';
import { Camera, Users, Upload, CheckCircle2, AlertCircle, RefreshCw, Loader2, Play, Square, Scan, LogIn } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/components/AuthProvider';
import { db } from '@/lib/firebase';
import { collection, addDoc, getDocs } from 'firebase/firestore';
import { handleFirestoreError, OperationType } from '@/lib/firestore-error';
import type { StudentData, DetectWebcamResponse, WebcamUIDetection, SyncStudentData } from '@/lib/types';
import { getBackendUrl } from '@/lib/utils';
import { authHeaders, buildAttendanceRecord } from '@/lib/attendance';
import { motion } from 'motion/react';

export default function ClassroomPage() {
  const { user, loading } = useAuth();
  const [mode, setMode] = useState<'live' | 'upload'>('live');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isLiveStreamActive, setIsLiveStreamActive] = useState(false);
  const [detectedFaces, setDetectedFaces] = useState<WebcamUIDetection[]>([]);
  const [registeredStudents, setRegisteredStudents] = useState<StudentData[]>([]);
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const [modelsLoaded, setModelsLoaded] = useState(false);

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
        const querySnapshot = await getDocs(collection(db, 'students'));
        const students = querySnapshot.docs.map(doc => ({ id: doc.id, ...doc.data() } as StudentData));
        setRegisteredStudents(students);

        if (students.length > 0) {
          const syncData: SyncStudentData[] = students.map(s => ({
            uid: s.uid,
            name: s.name,
            roll_no: s.rollNumber || 'N/A',
            image_base64: s.faceImageBase64
          })).filter(s => s.image_base64);

          try {
            const headers = await authHeaders();
            const syncRes = await fetch(getBackendUrl('/api/sync'), {
              method: 'POST',
              headers,
              body: JSON.stringify({ students: syncData })
            });
            if (!syncRes.ok) {
              throw new Error(`Sync failed (${syncRes.status})`);
            }
            setModelsLoaded(true);
          } catch {
            console.error("Backend sync failed");
            toast.error("Failed to sync facial data with backend.");
          }
        } else {
          setModelsLoaded(true);
        }
      } catch (error) {
        console.error("Error loading data:", error);
        toast.error("Failed to initialize system.");
      }
    };

    loadData();

    return () => {
      if (detectionIntervalRef.current) {
        clearInterval(detectionIntervalRef.current);
      }
    };
  }, []);

  const logAttendance = async (student: { uid: string; name: string; rollNo?: string; rollNumber?: string }) => {
    if (!student.uid) return;
    if (loggedStudentsRef.current.has(student.uid)) return;

    try {
      loggedStudentsRef.current.add(student.uid);
      const full = registeredStudents.find((s) => s.uid === student.uid);
      const payload = await buildAttendanceRecord(
        {
          uid: student.uid,
          name: student.name,
          rollNumber: student.rollNo || student.rollNumber || full?.rollNumber || 'N/A',
          department: full?.department || 'N/A',
          year: full?.year || 'N/A',
          semester: full?.semester || 'N/A',
        },
        'doorway_batch'
      );
      await addDoc(collection(db, 'attendance'), payload);
      toast.success(`Attendance logged for ${student.name}`);
    } catch (error) {
      handleFirestoreError(error, OperationType.CREATE, 'attendance');
      loggedStudentsRef.current.delete(student.uid);
    }
  };

  const handleVideoOnPlay = useCallback(() => {
    if (!modelsLoaded || !webcamRef.current?.video || !canvasRef.current) return;

    const video = webcamRef.current.video;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    if (video.videoWidth > 0 && video.videoHeight > 0) {
      const parent = canvas.parentElement;
      if (parent) {
        parent.style.aspectRatio = `${video.videoWidth} / ${video.videoHeight}`;
      }
    }

    detectionIntervalRef.current = setInterval(async () => {
      if (!isLiveStreamActive) return;
      if (inFlightRef.current) return;
      inFlightRef.current = true;

      const imageSrc = webcamRef.current?.getScreenshot();
      if (!imageSrc) { inFlightRef.current = false; return; }

      try {
        const headers = await authHeaders();
        const response = await fetch(getBackendUrl('/api/detect_webcam'), {
          method: 'POST',
          headers,
          body: JSON.stringify({ image_base64: imageSrc })
        });

        if (!response.ok) throw new Error("Detection failed");

        const data: DetectWebcamResponse = await response.json();
        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
        }

        const currentDetections: WebcamUIDetection[] = [];
        const newBoxes = new Map<number, { x: number; y: number; w: number; h: number }>();
        const alpha = 0.4;

        if (data.faces_detected > 0) {
          for (let i = 0; i < data.face_data.length; i++) {
            const face = data.face_data[i];
            const [rawX, rawY, rawW, rawH] = face.box;
            const student = face.match;
            const prev = prevBoxesRef.current.get(i);

            const x = prev ? Math.round(prev.x + alpha * (rawX - prev.x)) : rawX;
            const y = prev ? Math.round(prev.y + alpha * (rawY - prev.y)) : rawY;
            const w = prev ? Math.round(prev.w + alpha * (rawW - prev.w)) : rawW;
            const h = prev ? Math.round(prev.h + alpha * (rawH - prev.h)) : rawH;

            newBoxes.set(i, { x, y, w, h });

            currentDetections.push({
              box: { x, y, width: w, height: h },
              isRecognized: !!student,
              student
            });

            if (student) {
              logAttendance(student);
            }

            if (ctx) {
              ctx.shadowColor = student ? 'rgba(16, 185, 129, 0.5)' : 'rgba(239, 68, 68, 0.5)';
              ctx.shadowBlur = 12;
              ctx.strokeStyle = student ? '#10b981' : '#ef4444';
              ctx.lineWidth = 3;
              ctx.strokeRect(x, y, w, h);
              ctx.shadowBlur = 0;

              const label = student ? student.name : 'Unknown';
              ctx.font = 'bold 14px system-ui, sans-serif';
              const textWidth = ctx.measureText(label).width;
              const labelH = 28;
              const labelY = y - labelH > 0 ? y - labelH : y + h;

              ctx.fillStyle = student ? '#10b981' : '#ef4444';
              ctx.beginPath();
              ctx.roundRect(x, labelY, textWidth + 16, labelH, 6);
              ctx.fill();

              ctx.fillStyle = '#ffffff';
              ctx.fillText(label, x + 8, labelY + 19);
            }
          }
        }

        prevBoxesRef.current = newBoxes;
        setDetectedFaces(currentDetections);
      } catch {
        console.error("Detection error");
      } finally {
        inFlightRef.current = false;
      }
    }, 1000);
  }, [modelsLoaded, isLiveStreamActive]);

  const toggleLiveStream = () => {
    if (isLiveStreamActive) {
      setIsLiveStreamActive(false);
      if (detectionIntervalRef.current) {
        clearInterval(detectionIntervalRef.current);
      }
      setDetectedFaces([]);
      loggedStudentsRef.current.clear();
      const canvas = canvasRef.current;
      if (canvas) {
        canvas.getContext('2d')?.clearRect(0, 0, canvas.width, canvas.height);
      }
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
      };
      reader.readAsDataURL(file);
    }
  };

  const processUploadedImage = async () => {
    if (!uploadedImage) return;
    setIsProcessing(true);

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
      let logged = 0;
      for (const m of unique.values()) {
        const before = loggedStudentsRef.current.size;
        await logAttendance(m);
        if (loggedStudentsRef.current.size > before) logged += 1;
      }
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
        <div className="bg-white p-10 rounded-[2rem] shadow-xl shadow-slate-200/50 border border-slate-100 max-w-md w-full text-center">
          <AlertCircle className="w-16 h-16 text-amber-500 mx-auto mb-6" />
          <h2 className="text-2xl font-bold text-slate-900 mb-4">Access Denied</h2>
          <p className="text-slate-600">Please sign in to access the Classroom Attendance portal.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-12"
        >
          <h1 className="text-4xl md:text-5xl font-display font-bold text-slate-900 tracking-tight mb-4">
            Classroom Attendance
          </h1>
          <p className="text-lg text-slate-600 max-w-2xl mx-auto">
            Monitor doorways in real-time or process group photos for automated batch attendance.
          </p>
        </motion.div>

        <div className="flex p-1.5 bg-slate-200/50 backdrop-blur-sm rounded-full mb-10 max-w-md mx-auto shadow-inner">
          <button
            onClick={() => setMode('live')}
            className={`flex-1 py-3 px-6 text-sm font-bold rounded-full transition-all duration-300 flex items-center justify-center gap-2 ${mode === 'live' ? 'bg-white text-indigo-700 shadow-md' : 'text-slate-500 hover:text-slate-900'}`}
          >
            <Camera className="w-4 h-4" /> Doorway (Live)
          </button>
          <button
            onClick={() => setMode('upload')}
            className={`flex-1 py-3 px-6 text-sm font-bold rounded-full transition-all duration-300 flex items-center justify-center gap-2 ${mode === 'upload' ? 'bg-white text-indigo-700 shadow-md' : 'text-slate-500 hover:text-slate-900'}`}
          >
            <Upload className="w-4 h-4" /> Group Photo
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="lg:col-span-2 bg-white rounded-[2.5rem] shadow-xl shadow-slate-200/50 border border-slate-100 overflow-hidden"
          >
            {mode === 'live' ? (
              <div className="p-8">
                <div className="flex justify-between items-center mb-6">
                  <h2 className="text-2xl font-bold text-slate-900">Live Camera Feed</h2>
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-2 text-sm font-bold text-slate-600">
                      <span className={`w-3 h-3 rounded-full ${isLiveStreamActive ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`}></span>
                      {isLiveStreamActive ? 'Active' : 'Inactive'}
                    </span>
                    <button
                      onClick={toggleLiveStream}
                      className={`px-4 py-2 rounded-full font-bold text-sm flex items-center gap-2 transition-colors ${
                        isLiveStreamActive
                          ? 'bg-rose-100 text-rose-700 hover:bg-rose-200'
                          : 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
                      }`}
                    >
                      {isLiveStreamActive ? <><Square className="w-4 h-4" /> Stop</> : <><Play className="w-4 h-4" /> Start</>}
                    </button>
                  </div>
                </div>

                <div className="relative bg-slate-900 aspect-video rounded-3xl overflow-hidden shadow-inner border-4 border-slate-100">
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
                    className="absolute inset-0 w-full h-full"
                    onPlay={handleVideoOnPlay}
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
                <h2 className="text-2xl font-bold text-slate-900 mb-6">Upload Group Photo</h2>

                {!uploadedImage ? (
                  <div
                    className="border-4 border-dashed border-slate-200 rounded-3xl p-12 text-center hover:border-indigo-400 hover:bg-indigo-50 transition-all cursor-pointer group"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <div className="w-20 h-20 bg-indigo-100 rounded-full flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform">
                      <Upload className="w-10 h-10 text-indigo-600" />
                    </div>
                    <h3 className="text-xl font-bold text-slate-900 mb-2">Click to upload image</h3>
                    <p className="text-slate-500">Supports JPG, PNG (Max 10MB)</p>
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
                    <div className="relative aspect-video rounded-3xl overflow-hidden shadow-inner border-4 border-slate-100 bg-slate-900">
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
                        onClick={() => setUploadedImage(null)}
                        disabled={isProcessing}
                        className="px-6 py-3 bg-slate-100 text-slate-700 rounded-full font-bold hover:bg-slate-200 transition-colors disabled:opacity-50"
                      >
                        Choose Another
                      </button>
                      <button
                        onClick={processUploadedImage}
                        disabled={isProcessing}
                        className="px-8 py-3 bg-gradient-to-r from-indigo-600 to-blue-600 text-white rounded-full font-bold hover:from-indigo-700 hover:to-blue-700 transition-all shadow-md flex items-center gap-2 disabled:opacity-50"
                      >
                        {isProcessing ? <><Loader2 className="w-5 h-5 animate-spin" /> Processing</> : <><Scan className="w-5 h-5" /> Process Image</>}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="bg-white rounded-[2.5rem] shadow-xl shadow-slate-200/50 border border-slate-100 p-8 flex flex-col"
          >
            <h3 className="text-xl font-bold text-slate-900 mb-6 flex items-center gap-2">
              <Users className="w-5 h-5 text-indigo-600" /> Detection Status
            </h3>

            <div className="flex-1">
              {mode === 'live' ? (
                <div className="space-y-6">
                  <div className="bg-slate-50 p-5 rounded-2xl border border-slate-100">
                    <p className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-2">Faces Detected</p>
                    <p className="text-4xl font-display font-bold text-slate-900">{detectedFaces.length}</p>
                  </div>

                  <div>
                    <p className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-4">Recent Recognitions</p>
                    {detectedFaces.filter(f => f.isRecognized).length > 0 ? (
                      <ul className="space-y-3">
                        {detectedFaces.filter(f => f.isRecognized).map((face, idx) => {
                          const matchedStudent = face.student;
                          return (
                            <li key={idx} className="flex items-center gap-3 bg-emerald-50 p-3 rounded-xl border border-emerald-100">
                              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                              <span className="font-bold text-emerald-900">{matchedStudent?.name || 'Unknown'}</span>
                            </li>
                          );
                        })}
                      </ul>
                    ) : (
                      <p className="text-slate-400 text-sm italic">No recognized faces currently in view.</p>
                    )}
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <p className="text-slate-600 text-sm leading-relaxed">
                    Upload a clear group photo. The system will use YOLO and FaceNet models to detect all faces and mark attendance for recognized students automatically.
                  </p>
                  <div className="bg-amber-50 p-4 rounded-xl border border-amber-100 flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                    <p className="text-xs text-amber-800 font-medium">For best results, ensure the photo is well-lit and faces are clearly visible.</p>
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
