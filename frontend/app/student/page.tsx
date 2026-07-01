'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';
import Webcam from 'react-webcam';
import { ShieldCheck, User as UserIcon, Camera, RefreshCw, CheckCircle2, XCircle, Loader2, LogIn, Scan, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/components/AuthProvider';
import { db } from '@/lib/firebase';
import { collection, query, where, getDocs, addDoc, deleteDoc, doc } from 'firebase/firestore';
import { handleFirestoreError, OperationType } from '@/lib/firestore-error';
import type { StudentData, VerifyResponse } from '@/lib/types';
import Image from 'next/image';
import { motion } from 'motion/react';

export default function StudentPage() {
  const { user, loading, signIn } = useAuth();
  const [phase, setPhase] = useState<1 | 2>(1);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verificationResult, setVerificationResult] = useState<'success' | 'failed' | null>(null);
  const [studentData, setStudentData] = useState<StudentData | null>(null);
  const [isLoadingData, setIsLoadingData] = useState(true);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const webcamRef = useRef<Webcam>(null);

  useEffect(() => {
    const fetchStudentData = async () => {
      if (!user) return;
      setIsLoadingData(true);
      try {
        const q = query(collection(db, 'students'), where('uid', '==', user.uid));
        const querySnapshot = await getDocs(q);
        if (!querySnapshot.empty) {
          const docData = querySnapshot.docs[0];
          setStudentData({ id: docData.id, ...docData.data() } as StudentData);
        } else {
          setStudentData(null);
        }
      } catch (error) {
        console.error("Error fetching student data:", error);
        toast.error("Failed to load your profile.");
        handleFirestoreError(error, OperationType.GET, 'students');
      } finally {
        setIsLoadingData(false);
      }
    };

    fetchStudentData();
  }, [user]);

  const handleDeleteProfile = async () => {
    if (!studentData?.id) return;
    setIsDeleting(true);
    try {
      await deleteDoc(doc(db, 'students', studentData.id));
      toast.success("Profile deleted successfully.");
      setStudentData(null);
      setShowDeleteModal(false);
    } catch (error) {
      console.error("Error deleting profile:", error);
      toast.error("Failed to delete profile.");
      handleFirestoreError(error, OperationType.DELETE, `students/${studentData.id}`);
    } finally {
      setIsDeleting(false);
    }
  };

  const captureAndVerify = useCallback(async () => {
    if (!webcamRef.current || !studentData) {
      toast.error("Camera not ready or student data not found.");
      return;
    }

    const imageSrc = webcamRef.current.getScreenshot();
    if (!imageSrc) {
      toast.error("Failed to capture image.");
      return;
    }

    setIsVerifying(true);
    setVerificationResult(null);

    try {
      const base64LiveImage = imageSrc.split(',')[1];
      const base64RegisteredImage = studentData.faceImageBase64.split(',')[1];

      const response = await fetch('http://localhost:8000/api/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          registered_image_base64: base64RegisteredImage,
          live_image_base64: base64LiveImage
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Verification request failed");
      }

      const result: VerifyResponse = await response.json();

      if (result.match) {
        setVerificationResult('success');
        toast.success(`Identity Verified! (${result.confidence.toFixed(1)}% confidence)`);

        try {
          await addDoc(collection(db, 'attendance'), {
            studentUid: user?.uid,
            name: studentData.name,
            rollNumber: studentData.rollNumber,
            department: studentData.department,
            year: studentData.year,
            semester: studentData.semester,
            timestamp: new Date().toISOString(),
            method: 'individual_live'
          });
        } catch (fsError) {
          console.error("Firestore error:", fsError);
          handleFirestoreError(fsError, OperationType.CREATE, 'attendance');
        }
      } else {
        setVerificationResult('failed');
        toast.error(`Verification Failed. ${result.reason}`);
      }
    } catch (error) {
      console.error("Verification error:", error);
      toast.error("An error occurred during verification. Is the backend running?");
      setVerificationResult('failed');
    } finally {
      setIsVerifying(false);
    }
  }, [studentData, user]);

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
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-white p-10 rounded-[2rem] shadow-xl shadow-slate-200/50 border border-slate-100 max-w-md w-full text-center"
        >
          <div className="w-20 h-20 bg-indigo-50 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-inner">
            <ShieldCheck className="w-10 h-10 text-indigo-600" />
          </div>
          <h2 className="text-3xl font-display font-bold text-slate-900 mb-4 tracking-tight">Authentication Required</h2>
          <p className="text-slate-600 mb-8 leading-relaxed">
            Please sign in with your institutional account to access the student verification portal.
          </p>
          <button
            onClick={signIn}
            className="w-full py-4 px-6 bg-gradient-to-r from-indigo-600 to-blue-600 text-white rounded-full font-bold hover:from-indigo-700 hover:to-blue-700 transition-all shadow-md shadow-indigo-500/20 hover:shadow-lg hover:shadow-indigo-500/30 hover:-translate-y-0.5 flex items-center justify-center gap-3"
          >
            <LogIn className="w-5 h-5" />
            Sign In to Continue
          </button>
        </motion.div>
      </div>
    );
  }

  if (isLoadingData) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 bg-white p-8 rounded-3xl shadow-lg border border-slate-100">
          <Loader2 className="w-10 h-10 text-indigo-600 animate-spin" />
          <p className="text-slate-500 font-bold">Loading your profile...</p>
        </div>
      </div>
    );
  }

  if (!studentData) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-white p-10 rounded-[2rem] shadow-xl shadow-slate-200/50 border border-slate-100 max-w-md w-full text-center"
        >
          <div className="w-20 h-20 bg-amber-50 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-inner">
            <UserIcon className="w-10 h-10 text-amber-600" />
          </div>
          <h2 className="text-3xl font-display font-bold text-slate-900 mb-4 tracking-tight">Profile Not Found</h2>
          <p className="text-slate-600 mb-8 leading-relaxed">
            We couldn&apos;t find a registered facial profile for your account. Please complete the registration process first.
          </p>
          <a
            href="/register"
            className="block w-full py-4 px-6 bg-gradient-to-r from-indigo-600 to-blue-600 text-white rounded-full font-bold hover:from-indigo-700 hover:to-blue-700 transition-all shadow-md shadow-indigo-500/20 hover:shadow-lg hover:shadow-indigo-500/30 hover:-translate-y-0.5"
          >
            Go to Registration
          </a>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-12"
        >
          <div className="flex items-center justify-center gap-2 mb-6">
            <Camera className="w-8 h-8 text-indigo-600" />
          </div>
          <h1 className="text-4xl md:text-5xl font-display font-bold text-slate-900 tracking-tight mb-4">
            Identity Verification
          </h1>
          <p className="text-lg text-slate-600 max-w-2xl mx-auto">
            Confirm your identity securely using AI-powered facial recognition.
          </p>
        </motion.div>

        <div className="flex p-1.5 bg-slate-200/50 backdrop-blur-sm rounded-full mb-10 max-w-md mx-auto shadow-inner">
          <button
            onClick={() => setPhase(1)}
            className={`flex-1 py-3 px-6 text-sm font-bold rounded-full transition-all duration-300 ${phase === 1 ? 'bg-white text-indigo-700 shadow-md' : 'text-slate-500 hover:text-slate-900'}`}
          >
            Personal Info
          </button>
          <button
            onClick={() => setPhase(2)}
            className={`flex-1 py-3 px-6 text-sm font-bold rounded-full transition-all duration-300 ${phase === 2 ? 'bg-white text-indigo-700 shadow-md' : 'text-slate-500 hover:text-slate-900'}`}
          >
            Live Scan
          </button>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-[2.5rem] shadow-xl shadow-slate-200/50 border border-slate-100 overflow-hidden"
        >
          {phase === 1 ? (
            <div className="p-8 md:p-12">
              <div className="flex flex-col md:flex-row gap-10 items-center md:items-start">
                <div className="w-48 h-48 relative rounded-3xl overflow-hidden border-4 border-slate-100 flex-shrink-0 bg-slate-100 shadow-lg">
                  <Image
                    src={studentData.faceImageBase64}
                    alt="Registered Face"
                    fill
                    sizes="192px"
                    className="object-cover"
                    unoptimized
                  />
                </div>

                <div className="flex-1 w-full">
                  <div className="flex justify-between items-center border-b border-slate-100 pb-6 mb-6">
                    <h3 className="text-2xl font-bold text-slate-900">Student Profile</h3>
                    <button
                      onClick={() => setShowDeleteModal(true)}
                      className="text-rose-600 hover:text-rose-800 bg-rose-50 hover:bg-rose-100 px-4 py-2 rounded-full flex items-center gap-2 text-sm font-bold transition-colors"
                    >
                      <Trash2 className="w-4 h-4" /> Delete Profile
                    </button>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-y-8 gap-x-8">
                    <div>
                      <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Full Name</p>
                      <p className="text-lg font-bold text-slate-900">{studentData.name}</p>
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Roll Number</p>
                      <p className="text-lg font-bold text-slate-900">{studentData.rollNumber}</p>
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Department</p>
                      <p className="text-lg font-bold text-slate-900">{studentData.department}</p>
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Academic Year</p>
                      <p className="text-lg font-bold text-slate-900">Year {studentData.year} &bull; Sem {studentData.semester}</p>
                    </div>
                  </div>

                  <div className="mt-10 pt-8 border-t border-slate-100 flex justify-end">
                    <button
                      onClick={() => setPhase(2)}
                      className="px-8 py-4 bg-gradient-to-r from-indigo-600 to-blue-600 text-white rounded-full font-bold hover:from-indigo-700 hover:to-blue-700 transition-all shadow-md shadow-indigo-500/20 hover:shadow-lg hover:shadow-indigo-500/30 hover:-translate-y-0.5 flex items-center gap-2"
                    >
                      Proceed to Scan <Scan className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8 md:p-12">
              <div className="max-w-2xl mx-auto">
                <div className="relative bg-slate-900 aspect-video mb-8 rounded-3xl overflow-hidden shadow-2xl border-4 border-slate-100">
                  <Webcam
                    audio={false}
                    ref={webcamRef}
                    screenshotFormat="image/jpeg"
                    videoConstraints={{ facingMode: "user" }}
                    className="w-full h-full object-cover"
                  />

                  {isVerifying && (
                    <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm flex flex-col items-center justify-center z-10">
                      <Loader2 className="w-12 h-12 text-white animate-spin mb-4" />
                      <p className="text-white font-bold text-lg tracking-wide">Analyzing Facial Features...</p>
                    </div>
                  )}

                  {verificationResult && !isVerifying && (
                    <div
                      className={`absolute inset-0 flex flex-col items-center justify-center z-20 backdrop-blur-md ${
                        verificationResult === 'success' ? 'bg-emerald-500/90' : 'bg-rose-500/90'
                      }`}
                    >
                      {verificationResult === 'success' ? (
                        <>
                          <CheckCircle2 className="w-20 h-20 text-white mb-4" />
                          <h3 className="text-3xl font-bold text-white mb-2">Verified</h3>
                          <p className="text-emerald-100 font-bold">Identity confirmed successfully.</p>
                        </>
                      ) : (
                        <>
                          <XCircle className="w-20 h-20 text-white mb-4" />
                          <h3 className="text-3xl font-bold text-white mb-2">Failed</h3>
                          <p className="text-rose-100 font-bold">Face does not match registered profile.</p>
                        </>
                      )}
                    </div>
                  )}
                </div>

                <div className="flex flex-col sm:flex-row gap-4 justify-center">
                  <button
                    onClick={() => setPhase(1)}
                    className="px-8 py-4 bg-slate-100 text-slate-700 rounded-full font-bold hover:bg-slate-200 transition-all shadow-sm hover:-translate-y-0.5"
                    disabled={isVerifying}
                  >
                    Back to Profile
                  </button>
                  <button
                    onClick={captureAndVerify}
                    disabled={isVerifying}
                    className={`px-8 py-4 rounded-full font-bold flex items-center justify-center gap-3 shadow-md transition-all hover:-translate-y-0.5 ${
                      isVerifying
                        ? 'bg-indigo-400 text-white cursor-not-allowed'
                        : 'bg-gradient-to-r from-indigo-600 to-blue-600 text-white hover:from-indigo-700 hover:to-blue-700 shadow-indigo-500/20 hover:shadow-indigo-500/30'
                    }`}
                  >
                    {isVerifying ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin" />
                        Verifying...
                      </>
                    ) : (
                      <>
                        <Scan className="w-5 h-5" />
                        Verify Identity
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}
        </motion.div>
      </div>

      {showDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-white p-8 rounded-[2rem] max-w-md w-full shadow-2xl border border-slate-100"
          >
            <div className="w-16 h-16 bg-rose-100 rounded-2xl flex items-center justify-center mb-6">
              <Trash2 className="w-8 h-8 text-rose-600" />
            </div>
            <h3 className="text-2xl font-bold text-slate-900 mb-4">Delete Profile?</h3>
            <p className="text-slate-600 mb-8 leading-relaxed">This action cannot be undone. Your facial data and registration details will be permanently removed.</p>
            <div className="flex gap-4 justify-end">
              <button
                onClick={() => setShowDeleteModal(false)}
                className="px-6 py-3 bg-slate-100 text-slate-700 rounded-full font-bold hover:bg-slate-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteProfile}
                disabled={isDeleting}
                className="px-6 py-3 bg-rose-600 text-white rounded-full font-bold hover:bg-rose-700 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {isDeleting ? <><Loader2 className="w-4 h-4 animate-spin" /> Deleting...</> : 'Delete Permanently'}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}
