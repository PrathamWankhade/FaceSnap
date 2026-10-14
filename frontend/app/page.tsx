'use client';

import Link from 'next/link';
import Image from 'next/image';
import type { User } from 'firebase/auth';
import { useEffect, useState } from 'react';
import { ArrowRight, ShieldCheck, Zap, UserCheck, UserPlus, Users, Scan, Clock, Database, Lock, Loader2, ClipboardList, Camera, Activity, RefreshCw, Fingerprint, MonitorPlay } from 'lucide-react';
import { useAuth } from '@/components/AuthProvider';
import { motion } from 'motion/react';
import { getBackendUrl } from '@/lib/utils';
import { authHeaders } from '@/lib/attendance';

export default function Home() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex-1 min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 bg-white dark:bg-slate-900 p-8 rounded-3xl shadow-lg border border-slate-100 dark:border-slate-800">
          <Loader2 className="w-10 h-10 text-indigo-600 animate-spin" />
          <p className="text-slate-500 dark:text-slate-400 font-semibold">Loading...</p>
        </div>
      </div>
    );
  }

  if (user) {
    return <LoggedInDashboard user={user} />;
  }

  return <LoggedOutHero />;
}

interface BackendHealth {
  ok: boolean;
  face_model_ready: boolean;
  vector_db_ready: boolean;
  students_in_db: number;
  camera: { enabled: boolean; running: boolean; opened: boolean; last_error: string | null };
}

function SystemStatus() {
  const [state, setState] = useState<'loading' | 'ok' | 'error'>('loading');
  const [health, setHealth] = useState<BackendHealth | null>(null);

  const load = async () => {
    setState('loading');
    try {
      const headers = await authHeaders();
      const res = await fetch(getBackendUrl('/api/health'), { headers });
      if (!res.ok) throw new Error(`Health check failed (${res.status})`);
      setHealth(await res.json());
      setState('ok');
    } catch {
      setHealth(null);
      setState('error');
    }
  };

  useEffect(() => {
    let cancelled = false;
    authHeaders()
      .then((headers) => fetch(getBackendUrl('/api/health'), { headers }))
      .then((res) => {
        if (!res.ok) throw new Error(`Health check failed (${res.status})`);
        return res.json() as Promise<BackendHealth>;
      })
      .then((data) => {
        if (cancelled) return;
        setHealth(data);
        setState('ok');
      })
      .catch(() => {
        if (cancelled) return;
        setHealth(null);
        setState('error');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const items = health
    ? [
        {
          label: 'Recognition engine',
          value: health.face_model_ready ? 'Ready' : 'Down',
          good: health.face_model_ready,
        },
        {
          label: 'Enrolled embeddings',
          value: health.vector_db_ready ? String(health.students_in_db) : 'Unavailable',
          good: health.vector_db_ready,
        },
        {
          label: 'Camera',
          value: !health.camera.enabled ? 'Disabled' : health.camera.running ? 'Running' : 'Stopped',
          good: health.camera.enabled && health.camera.running,
        },
      ]
    : [];

  return (
    <div className="bg-white dark:bg-slate-900 rounded-[2rem] shadow-lg shadow-slate-200/50 dark:shadow-none border border-slate-100 dark:border-slate-800 p-8">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <Activity className="w-5 h-5 text-indigo-600 dark:text-indigo-400" /> System status
        </h3>
        {state === 'error' && (
          <button
            onClick={load}
            className="flex items-center gap-2 text-sm font-bold text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/60 px-4 py-2 rounded-full transition-colors"
          >
            <RefreshCw className="w-4 h-4" /> Retry
          </button>
        )}
      </div>
      {state === 'loading' ? (
        <div className="grid sm:grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => (
            <div key={i} className="skeleton-pulse h-20 rounded-2xl" />
          ))}
        </div>
      ) : state === 'error' ? (
        <p className="text-sm text-rose-600 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/50 border border-rose-100 dark:border-rose-900 rounded-2xl px-4 py-3">
          Backend unreachable. Camera and recognition status are unknown — no attendance can be processed right now.
        </p>
      ) : (
        <div className="grid sm:grid-cols-3 gap-4">
          {items.map((item) => (
            <div key={item.label} className="bg-slate-50 dark:bg-slate-800/70 border border-slate-100 dark:border-slate-700/60 rounded-2xl p-4">
              <p className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-1">{item.label}</p>
              <p className="flex items-center gap-2 font-bold text-slate-900 dark:text-white">
                <span className={`w-2.5 h-2.5 rounded-full ${item.good ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                {item.value}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function LoggedInDashboard({ user }: { user: User }) {
  const { role } = useAuth();
  const isStaff = role === 'admin';

  return (
    <div className="flex-1 bg-slate-50/50 dark:bg-slate-950 py-12 px-4 sm:px-6 lg:px-8 min-h-screen page-fade">
      <div className="max-w-7xl mx-auto">
        <div className="mb-10 gpu">
          <h1 className="text-4xl md:text-5xl font-display font-bold text-slate-900 dark:text-white mb-4 tracking-tight">
            Welcome back, <span className="text-indigo-600 dark:text-indigo-400">{user.displayName?.split(' ')[0] || 'Student'}</span>.
          </h1>
          <p className="text-slate-600 dark:text-slate-300 text-lg max-w-2xl">
            Verify your identity, review your attendance, and — if you are staff — run classroom and camera operations.
          </p>
        </div>

        <h2 className="text-sm font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-4">Student portal</h2>
        <div className="grid md:grid-cols-3 gap-6 mb-10">
          <DashboardCard
            href="/register"
            icon={<UserPlus className="w-7 h-7 text-indigo-600 dark:text-indigo-400" />}
            title="Register Identity"
            description="Enroll your face with the InsightFace ArcFace pipeline for attendance matching."
            iconBg="bg-indigo-100 dark:bg-indigo-950/70"
            delay={0.1}
          />
          <DashboardCard
            href="/student"
            icon={<Scan className="w-7 h-7 text-emerald-600 dark:text-emerald-400" />}
            title="Verify Identity"
            description="Complete a live scan with liveness anti-spoofing to verify your identity."
            iconBg="bg-emerald-100 dark:bg-emerald-950/70"
            delay={0.2}
          />
          <DashboardCard
            href="/attendance"
            icon={<ClipboardList className="w-7 h-7 text-blue-600 dark:text-blue-400" />}
            title="My Attendance"
            description="Review your recorded attendance history across all capture methods."
            iconBg="bg-blue-100 dark:bg-blue-950/70"
            delay={0.3}
          />
        </div>

        {isStaff && (
          <>
            <h2 className="text-sm font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-4">Attendance operations</h2>
            <div className="grid md:grid-cols-2 gap-6 mb-10">
              <DashboardCard
                href="/classroom"
                icon={<Users className="w-7 h-7 text-blue-600 dark:text-blue-400" />}
                title="Batch Attendance"
                description="Match live doorway faces or process a group photo against enrolled students."
                iconBg="bg-blue-100 dark:bg-blue-950/70"
                delay={0.1}
              />
              <DashboardCard
                href="/cctv"
                icon={<Camera className="w-7 h-7 text-violet-600 dark:text-violet-400" />}
                title="CCTV Monitoring"
                description="Monitor camera streams with backend face matching and review detections."
                iconBg="bg-violet-100 dark:bg-violet-950/70"
                delay={0.2}
              />
            </div>
          </>
        )}

        <h2 className="text-sm font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-4">System status</h2>
        <SystemStatus />
      </div>
    </div>
  );
}

interface DashboardCardProps {
  href: string;
  icon: React.ReactNode;
  title: string;
  description: string;
  iconBg: string;
  delay: number;
}

function DashboardCard({ href, icon, title, description, iconBg, delay }: DashboardCardProps) {
  return (
    <Link href={href}>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay, duration: 0.4 }}
        whileHover={{ y: -5 }}
        className="p-8 bg-white dark:bg-slate-900 rounded-[2rem] shadow-lg shadow-slate-200/50 dark:shadow-none border border-slate-100 dark:border-slate-800 transition-all duration-300 hover:shadow-xl hover:border-indigo-200 dark:hover:border-indigo-800 cursor-pointer h-full flex flex-col group gpu"
      >
        <div className={`w-14 h-14 rounded-2xl ${iconBg} flex items-center justify-center mb-6 transition-transform duration-300 group-hover:scale-110`}>
          {icon}
        </div>
        <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-3">{title}</h3>
        <p className="text-slate-600 dark:text-slate-300 leading-relaxed flex-1">{description}</p>
        <div className="mt-6 flex items-center text-indigo-600 dark:text-indigo-400 font-bold text-sm">
          Get Started
          <ArrowRight className="w-4 h-4 ml-2 transition-transform duration-300 group-hover:translate-x-1" />
        </div>
      </motion.div>
    </Link>
  );
}

const CAPABILITIES = [
  { icon: Fingerprint, title: 'ArcFace recognition', text: '512-dimensional embeddings matched by cosine distance.' },
  { icon: ShieldCheck, title: 'Liveness anti-spoofing', text: 'Multi-frame checks resist photo and replay attacks.' },
  { icon: MonitorPlay, title: 'Batch & CCTV modes', text: 'Doorway, group-photo, and camera-stream capture.' },
  { icon: Database, title: 'Auditable records', text: 'Canonical attendance events with method and session.' },
];

function LoggedOutHero() {
  return (
    <div className="flex-1 flex flex-col bg-slate-50 dark:bg-slate-950">
      <section className="relative overflow-hidden bg-slate-900 py-24 lg:py-32 text-white rounded-b-[3rem] lg:rounded-b-[4rem] gpu">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-indigo-500/30 rounded-full blur-3xl mix-blend-screen pointer-events-none"></div>
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-blue-500/30 rounded-full blur-3xl mix-blend-screen pointer-events-none"></div>
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6 }}
            >
              <h1 className="text-5xl md:text-6xl lg:text-7xl font-display font-bold mb-8 leading-[1.1] tracking-tight">
                Trusted <br/>
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-blue-400">Attendance</span> <br/>
                Verification.
              </h1>
              <p className="text-xl text-slate-300 mb-10 leading-relaxed max-w-lg">
                FaceSnap helps educational institutions verify identities and record attendance with face matching, liveness checks, and auditable records.
              </p>
              <div className="flex flex-wrap items-center gap-4">
                <Link
                  href="/register"
                  className="group px-8 py-4 bg-white text-slate-900 rounded-full font-bold hover:bg-indigo-50 transition-all flex items-center gap-3 shadow-xl shadow-white/10 hover:shadow-white/20 hover:-translate-y-0.5"
                >
                  <span>Get Started</span>
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </Link>
              </div>
            </motion.div>
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="relative h-[600px] hidden lg:block"
            >
              <div className="relative w-full h-full overflow-hidden rounded-[3rem] border border-white/10 shadow-2xl">
                <Image
                  src="https://images.unsplash.com/photo-1523240795612-9a054b0db644?q=80&w=1000&auto=format&fit=crop"
                  alt="Students in classroom"
                  fill
                  priority
                  sizes="(max-width: 1024px) 100vw, 50vw"
                  className="object-cover opacity-90"
                  referrerPolicy="no-referrer"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-slate-900/80 to-transparent"></div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      <section className="py-20 bg-slate-50 dark:bg-slate-950">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {CAPABILITIES.map((c) => (
              <div key={c.title} className="bg-white dark:bg-slate-900 rounded-[2rem] border border-slate-100 dark:border-slate-800 p-6 shadow-sm">
                <c.icon className="w-7 h-7 text-indigo-600 dark:text-indigo-400 mb-4" />
                <p className="font-bold text-slate-900 dark:text-white mb-1">{c.title}</p>
                <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed">{c.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-24 bg-white dark:bg-slate-900 rounded-[3rem] lg:rounded-[4rem] shadow-sm relative z-10 -mt-8 content-vis-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-20">
            <h2 className="text-4xl md:text-5xl font-display font-bold text-slate-900 dark:text-white mb-6 tracking-tight">Powerful Features</h2>
            <p className="text-xl text-slate-600 dark:text-slate-300 max-w-2xl mx-auto">
              Everything you need to manage attendance and verify identities with the InsightFace ArcFace pipeline.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="p-10 rounded-[2.5rem] bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-700/60 hover:shadow-xl hover:shadow-indigo-500/10 hover:border-indigo-100 dark:hover:border-indigo-800 transition-all duration-300 group">
              <div className="w-16 h-16 rounded-2xl bg-blue-100 dark:bg-blue-950/70 text-blue-600 dark:text-blue-400 flex items-center justify-center mb-8 transition-transform group-hover:scale-110">
                <UserCheck className="w-8 h-8" />
              </div>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">Batch Processing</h3>
              <p className="text-slate-600 dark:text-slate-300 leading-relaxed">Verify multiple faces per frame with dedicated face detection, ideal for large classrooms.</p>
            </div>
            <div className="p-10 rounded-[2.5rem] bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-700/60 hover:shadow-xl hover:shadow-emerald-500/10 hover:border-emerald-100 dark:hover:border-emerald-800 transition-all duration-300 group">
              <div className="w-16 h-16 rounded-2xl bg-emerald-100 dark:bg-emerald-950/70 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-8 transition-transform group-hover:scale-110">
                <ShieldCheck className="w-8 h-8" />
              </div>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">Anti-Spoofing</h3>
              <p className="text-slate-600 dark:text-slate-300 leading-relaxed">Multi-frame liveness analysis helps resist photo and video-replay attacks.</p>
            </div>
            <div className="p-10 rounded-[2.5rem] bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-700/60 hover:shadow-xl hover:shadow-amber-500/10 hover:border-amber-100 dark:hover:border-amber-800 transition-all duration-300 group">
              <div className="w-16 h-16 rounded-2xl bg-amber-100 dark:bg-amber-950/70 text-amber-600 dark:text-amber-400 flex items-center justify-center mb-8 transition-transform group-hover:scale-110">
                <Zap className="w-8 h-8" />
              </div>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">Real-time Matching</h3>
              <p className="text-slate-600 dark:text-slate-300 leading-relaxed">Cached embeddings and vector search keep live recognition responsive.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-24 bg-slate-50 dark:bg-slate-950">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div>
              <h2 className="text-4xl md:text-5xl font-display font-bold text-slate-900 dark:text-white mb-8 tracking-tight">How FaceSnap Works</h2>
              <div className="space-y-8">
                <div className="flex gap-6 group">
                  <div className="w-14 h-14 rounded-2xl bg-white dark:bg-slate-900 shadow-md border border-slate-100 dark:border-slate-800 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-bold text-xl flex-shrink-0 transition-transform group-hover:scale-110">1</div>
                  <div>
                    <h4 className="text-xl font-bold text-slate-900 dark:text-white mb-2">Register Profile</h4>
                    <p className="text-slate-600 dark:text-slate-300">Students create an account and capture a clear image of their face. The system extracts an ArcFace embedding for future matching.</p>
                  </div>
                </div>
                <div className="flex gap-6 group">
                  <div className="w-14 h-14 rounded-2xl bg-white dark:bg-slate-900 shadow-md border border-slate-100 dark:border-slate-800 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-bold text-xl flex-shrink-0 transition-transform group-hover:scale-110">2</div>
                  <div>
                    <h4 className="text-xl font-bold text-slate-900 dark:text-white mb-2">Live Scanning</h4>
                    <p className="text-slate-600 dark:text-slate-300">During class, a camera scans the room or doorway, checks liveness, and matches live faces against enrolled students.</p>
                  </div>
                </div>
                <div className="flex gap-6 group">
                  <div className="w-14 h-14 rounded-2xl bg-white dark:bg-slate-900 shadow-md border border-slate-100 dark:border-slate-800 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-bold text-xl flex-shrink-0 transition-transform group-hover:scale-110">3</div>
                  <div>
                    <h4 className="text-xl font-bold text-slate-900 dark:text-white mb-2">Verified Attendance</h4>
                    <p className="text-slate-600 dark:text-slate-300">Only verified matches create attendance events — each recorded once per session with its capture method.</p>
                  </div>
                </div>
              </div>
            </div>
            <div className="relative h-[500px] bg-white dark:bg-slate-900 rounded-[3rem] shadow-xl border border-slate-100 dark:border-slate-800 p-8 flex flex-col justify-center overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-50 dark:bg-indigo-950/40 rounded-full blur-3xl -mr-20 -mt-20"></div>
              <div className="absolute bottom-0 left-0 w-64 h-64 bg-blue-50 dark:bg-blue-950/40 rounded-full blur-3xl -ml-20 -mb-20"></div>
              <div className="space-y-6 relative z-10">
                <div className="flex items-center gap-5 p-5 bg-white/80 dark:bg-slate-800/80 backdrop-blur-sm rounded-2xl border border-slate-100 dark:border-slate-700 shadow-sm hover:shadow-md transition-shadow">
                  <div className="w-12 h-12 rounded-xl bg-blue-50 dark:bg-blue-950/70 flex items-center justify-center">
                    <Database className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div>
                    <p className="font-bold text-slate-900 dark:text-white">Secure Storage</p>
                    <p className="text-sm text-slate-500 dark:text-slate-400">Firebase Firestore Integration</p>
                  </div>
                </div>
                <div className="flex items-center gap-5 p-5 bg-white/80 dark:bg-slate-800/80 backdrop-blur-sm rounded-2xl border border-slate-100 dark:border-slate-700 shadow-sm hover:shadow-md transition-shadow">
                  <div className="w-12 h-12 rounded-xl bg-emerald-50 dark:bg-emerald-950/70 flex items-center justify-center">
                    <Clock className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
                  </div>
                  <div>
                    <p className="font-bold text-slate-900 dark:text-white">Real-time Processing</p>
                    <p className="text-sm text-slate-500 dark:text-slate-400">Live detection with review states</p>
                  </div>
                </div>
                <div className="flex items-center gap-5 p-5 bg-white/80 dark:bg-slate-800/80 backdrop-blur-sm rounded-2xl border border-slate-100 dark:border-slate-700 shadow-sm hover:shadow-md transition-shadow">
                  <div className="w-12 h-12 rounded-xl bg-amber-50 dark:bg-amber-950/70 flex items-center justify-center">
                    <Lock className="w-6 h-6 text-amber-600 dark:text-amber-400" />
                  </div>
                  <div>
                    <p className="font-bold text-slate-900 dark:text-white">Privacy First</p>
                    <p className="text-sm text-slate-500 dark:text-slate-400">Consent, retention, and deletion controls</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
