'use client';

import React, { useState, useRef, useCallback } from 'react';
import Webcam from 'react-webcam';
import { Camera, CheckCircle2, RefreshCw, AlertCircle, LogIn, UserPlus, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/components/AuthProvider';
import { db } from '@/lib/firebase';
import { collection, addDoc, query, where, getDocs } from 'firebase/firestore';
import { motion } from 'motion/react';

export default function RegisterPage() {
  const { user, loading, signIn } = useAuth();
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    name: '',
    rollNumber: '',
    department: '',
    year: '',
    semester: ''
  });
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const webcamRef = useRef<Webcam>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const capture = useCallback(() => {
    if (webcamRef.current) {
      const imageSrc = webcamRef.current.getScreenshot();
      setImageSrc(imageSrc);
    }
  }, [webcamRef]);

  const retake = () => {
    setImageSrc(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) {
      toast.error("You must be logged in to register.");
      return;
    }
    if (!imageSrc) {
      toast.error("Please capture your face image.");
      return;
    }
    if (!formData.name || !formData.rollNumber || !formData.department || !formData.year || !formData.semester) {
      toast.error("Please fill in all fields.");
      return;
    }

    setIsSubmitting(true);
    try {
      const q = query(collection(db, 'students'), where('uid', '==', user.uid));
      const querySnapshot = await getDocs(q);

      if (!querySnapshot.empty) {
        toast.error("You have already registered a facial profile.");
        setIsSubmitting(false);
        return;
      }

      await addDoc(collection(db, 'students'), {
        uid: user.uid,
        email: user.email,
        name: formData.name,
        rollNumber: formData.rollNumber,
        department: formData.department,
        year: formData.year,
        semester: formData.semester,
        faceImageBase64: imageSrc,
        registeredAt: new Date().toISOString()
      });

      toast.success("Registration successful!");
      setStep(3);
    } catch (error) {
      console.error("Registration error:", error);
      toast.error("Failed to register. Please try again.");
    } finally {
      setIsSubmitting(false);
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
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-white p-10 rounded-[2rem] shadow-xl shadow-slate-200/50 border border-slate-100 max-w-md w-full text-center"
        >
          <div className="w-20 h-20 bg-indigo-50 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-inner">
            <UserPlus className="w-10 h-10 text-indigo-600" />
          </div>
          <h2 className="text-3xl font-display font-bold text-slate-900 mb-4 tracking-tight">Authentication Required</h2>
          <p className="text-slate-600 mb-8 leading-relaxed">
            Please sign in with your institutional account to register your facial profile.
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

  return (
    <div className="min-h-screen bg-slate-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-12"
        >
          <h1 className="text-4xl md:text-5xl font-display font-bold text-slate-900 tracking-tight mb-4">
            Identity Registration
          </h1>
          <p className="text-lg text-slate-600 max-w-2xl mx-auto">
            Enroll your facial data securely into the institutional database using advanced CNN architectures.
          </p>
        </motion.div>

        <div className="mb-12 max-w-md mx-auto">
          <div className="flex justify-between items-center relative">
            <div className="absolute left-0 top-1/2 -translate-y-1/2 w-full h-1.5 bg-slate-200 rounded-full z-0"></div>
            <div
              className="absolute left-0 top-1/2 -translate-y-1/2 h-1.5 bg-indigo-600 rounded-full z-0 transition-all duration-500 shadow-[0_0_10px_rgba(79,70,229,0.5)]"
              style={{ width: step === 1 ? '0%' : step === 2 ? '50%' : '100%' }}
            />

            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className={`relative z-10 w-12 h-12 rounded-full flex items-center justify-center font-bold text-sm transition-all duration-500 shadow-md ${
                  step >= i ? 'bg-indigo-600 text-white shadow-indigo-500/30' : 'bg-white text-slate-400 border-2 border-slate-200'
                }`}
              >
                {step > i ? <CheckCircle2 className="w-6 h-6" /> : i}
              </div>
            ))}
          </div>
          <div className="flex justify-between mt-4 text-xs font-bold text-slate-400 uppercase tracking-wider">
            <span>Details</span>
            <span>Capture</span>
            <span>Complete</span>
          </div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-[2.5rem] shadow-xl shadow-slate-200/50 border border-slate-100 overflow-hidden"
        >
          {step === 1 && (
            <div className="p-8 md:p-12">
              <h2 className="text-2xl font-bold text-slate-900 mb-6">Student Information</h2>
              <form onSubmit={(e) => { e.preventDefault(); setStep(2); }} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-slate-700 ml-1">Full Name</label>
                    <input
                      required
                      name="name"
                      value={formData.name}
                      onChange={handleInputChange}
                      className="w-full px-5 py-4 rounded-2xl border border-slate-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none transition-all bg-slate-50 focus:bg-white shadow-sm"
                      placeholder="John Doe"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-slate-700 ml-1">Roll Number</label>
                    <input
                      required
                      name="rollNumber"
                      value={formData.rollNumber}
                      onChange={handleInputChange}
                      className="w-full px-5 py-4 rounded-2xl border border-slate-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none transition-all bg-slate-50 focus:bg-white shadow-sm"
                      placeholder="e.g. CS2024-001"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-bold text-slate-700 ml-1">Department</label>
                  <select
                    required
                    name="department"
                    value={formData.department}
                    onChange={handleInputChange}
                    className="w-full px-5 py-4 rounded-2xl border border-slate-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none transition-all bg-slate-50 focus:bg-white shadow-sm appearance-none"
                  >
                    <option value="">Select Department</option>
                    <option value="Computer Science">Computer Science</option>
                    <option value="Information Technology">Information Technology</option>
                    <option value="Electronics">Electronics</option>
                    <option value="Mechanical">Mechanical</option>
                  </select>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-slate-700 ml-1">Year</label>
                    <select
                      required
                      name="year"
                      value={formData.year}
                      onChange={handleInputChange}
                      className="w-full px-5 py-4 rounded-2xl border border-slate-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none transition-all bg-slate-50 focus:bg-white shadow-sm appearance-none"
                    >
                      <option value="">Select Year</option>
                      <option value="1">1st Year</option>
                      <option value="2">2nd Year</option>
                      <option value="3">3rd Year</option>
                      <option value="4">4th Year</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-slate-700 ml-1">Semester</label>
                    <select
                      required
                      name="semester"
                      value={formData.semester}
                      onChange={handleInputChange}
                      className="w-full px-5 py-4 rounded-2xl border border-slate-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none transition-all bg-slate-50 focus:bg-white shadow-sm appearance-none"
                    >
                      <option value="">Select Semester</option>
                      <option value="1">1st Semester</option>
                      <option value="2">2nd Semester</option>
                      <option value="3">3rd Semester</option>
                      <option value="4">4th Semester</option>
                      <option value="5">5th Semester</option>
                      <option value="6">6th Semester</option>
                      <option value="7">7th Semester</option>
                      <option value="8">8th Semester</option>
                    </select>
                  </div>
                </div>

                <div className="pt-8 flex justify-end">
                  <button
                    type="submit"
                    className="px-8 py-4 bg-gradient-to-r from-indigo-600 to-blue-600 text-white rounded-full font-bold hover:from-indigo-700 hover:to-blue-700 transition-all shadow-md shadow-indigo-500/20 hover:shadow-lg hover:shadow-indigo-500/30 hover:-translate-y-0.5"
                  >
                    Continue to Capture
                  </button>
                </div>
              </form>
            </div>
          )}

          {step === 2 && (
            <div className="p-8 md:p-12">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-slate-900">Facial Capture</h2>
                <button onClick={() => setStep(1)} className="text-sm font-bold text-indigo-600 hover:text-indigo-800 transition-colors bg-indigo-50 px-4 py-2 rounded-full">
                  Edit Details
                </button>
              </div>

              <div className="bg-amber-50 p-5 rounded-2xl mb-8 border border-amber-100 shadow-inner">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-amber-800 leading-relaxed">
                    Ensure you are in a well-lit area. Look directly at the camera and keep your face within the frame.
                  </p>
                </div>
              </div>

              <div className="relative bg-slate-900 aspect-video mb-8 rounded-3xl overflow-hidden shadow-2xl max-w-2xl mx-auto border-4 border-slate-100">
                {!imageSrc ? (
                  <>
                    <Webcam
                      audio={false}
                      ref={webcamRef}
                      screenshotFormat="image/jpeg"
                      videoConstraints={{ facingMode: "user" }}
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
                      <div className="w-48 h-64 border-2 border-white/50 border-dashed rounded-full" />
                    </div>
                  </>
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={imageSrc} alt="Captured" className="w-full h-full object-cover" />
                )}
              </div>

              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                {!imageSrc ? (
                  <button
                    onClick={capture}
                    className="px-8 py-4 bg-slate-900 text-white rounded-full font-bold hover:bg-slate-800 transition-all flex items-center justify-center gap-3 shadow-lg hover:-translate-y-0.5"
                  >
                    <Camera className="w-5 h-5" />
                    Capture Photo
                  </button>
                ) : (
                  <>
                    <button
                      onClick={retake}
                      className="px-8 py-4 bg-slate-100 text-slate-700 rounded-full font-bold hover:bg-slate-200 transition-all flex items-center justify-center gap-2 shadow-sm hover:-translate-y-0.5"
                      disabled={isSubmitting}
                    >
                      <RefreshCw className="w-4 h-4" />
                      Retake
                    </button>
                    <button
                      onClick={handleSubmit}
                      disabled={isSubmitting}
                      className={`px-8 py-4 rounded-full font-bold flex items-center justify-center gap-3 shadow-md transition-all hover:-translate-y-0.5 ${
                        isSubmitting
                          ? 'bg-indigo-400 text-white cursor-not-allowed'
                          : 'bg-gradient-to-r from-indigo-600 to-blue-600 text-white hover:from-indigo-700 hover:to-blue-700 shadow-indigo-500/20 hover:shadow-indigo-500/30'
                      }`}
                    >
                      {isSubmitting ? 'Registering...' : 'Complete Registration'}
                    </button>
                  </>
                )}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="p-12 text-center">
              <div className="w-24 h-24 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-6 shadow-inner">
                <CheckCircle2 className="w-12 h-12 text-emerald-600" />
              </div>
              <h2 className="text-3xl font-display font-bold text-slate-900 mb-4">Registration Complete!</h2>
              <p className="text-slate-600 mb-8 max-w-md mx-auto leading-relaxed">
                Your facial profile has been securely enrolled. You can now use FaceSnap for seamless identity verification.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <a
                  href="/student"
                  className="px-8 py-4 bg-gradient-to-r from-indigo-600 to-blue-600 text-white rounded-full font-bold hover:from-indigo-700 hover:to-blue-700 transition-all shadow-md shadow-indigo-500/20 hover:-translate-y-0.5 inline-block"
                >
                  Go to Verification
                </a>
                <a
                  href="/"
                  className="px-8 py-4 bg-slate-100 text-slate-700 rounded-full font-bold hover:bg-slate-200 transition-all shadow-sm hover:-translate-y-0.5 inline-block"
                >
                  Return Home
                </a>
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
