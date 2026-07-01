'use client';

import Link from 'next/link';
import Image from 'next/image';
import type { User } from 'firebase/auth';
import { ArrowRight, ShieldCheck, Zap, UserCheck, UserPlus, Users, Scan, Clock, Database, Lock, Loader2 } from 'lucide-react';
import { useAuth } from '@/components/AuthProvider';
import { motion } from 'motion/react';

export default function Home() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex-1 min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 bg-white p-8 rounded-3xl shadow-lg border border-slate-100">
          <Loader2 className="w-10 h-10 text-indigo-600 animate-spin" />
          <p className="text-slate-500 font-semibold">Loading...</p>
        </div>
      </div>
    );
  }

  if (user) {
    return <LoggedInDashboard user={user} />;
  }

  return <LoggedOutHero />;
}

function LoggedInDashboard({ user }: { user: User }) {
  return (
    <div className="flex-1 bg-slate-50/50 py-12 px-4 sm:px-6 lg:px-8 min-h-screen">
      <div className="max-w-7xl mx-auto">
        <div className="mb-12 gpu">
          <h1 className="text-4xl md:text-5xl font-display font-bold text-slate-900 mb-4 tracking-tight">
            Welcome back, <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-blue-600">{user.displayName?.split(' ')[0] || 'Student'}</span>.
          </h1>
          <p className="text-slate-600 text-lg max-w-2xl">
            Access your identity verification tools and manage classroom attendance from your centralized dashboard.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6 mb-12">
          <DashboardCard
            href="/register"
            icon={<UserPlus className="w-7 h-7 text-indigo-600" />}
            title="Register Identity"
            description="Enroll your facial data into the secure FaceSnap database using CNN ML."
            iconBg="bg-indigo-100"
            delay={0.1}
          />
          <DashboardCard
            href="/student"
            icon={<Scan className="w-7 h-7 text-emerald-600" />}
            title="Verify Identity"
            description="Perform a live scan to verify your identity instantly with FaceNet."
            iconBg="bg-emerald-100"
            delay={0.2}
          />
          <DashboardCard
            href="/classroom"
            icon={<Users className="w-7 h-7 text-blue-600" />}
            title="Batch Attendance"
            description="Process multiple students at once using YOLO-based doorway tracking."
            iconBg="bg-blue-100"
            delay={0.3}
          />
        </div>
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
        className="p-8 bg-white rounded-[2rem] shadow-lg shadow-slate-200/50 border border-slate-100 transition-all duration-300 hover:shadow-xl hover:border-indigo-200 cursor-pointer h-full flex flex-col group gpu"
      >
        <div className={`w-14 h-14 rounded-2xl ${iconBg} flex items-center justify-center mb-6 transition-transform duration-300 group-hover:scale-110`}>
          {icon}
        </div>
        <h3 className="text-2xl font-bold text-slate-900 mb-3">{title}</h3>
        <p className="text-slate-600 leading-relaxed flex-1">{description}</p>
        <div className="mt-6 flex items-center text-indigo-600 font-bold text-sm">
          Get Started
          <ArrowRight className="w-4 h-4 ml-2 transition-transform duration-300 group-hover:translate-x-1" />
        </div>
      </motion.div>
    </Link>
  );
}

function LoggedOutHero() {
  return (
    <div className="flex-1 flex flex-col bg-slate-50">
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
                Stunning <br/>
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-blue-400">Identity</span> <br/>
                Verification.
              </h1>
              <p className="text-xl text-slate-300 mb-10 leading-relaxed max-w-lg">
                With FaceSnap, educational institutions can organize attendance, manage shifting priorities, and verify identities instantly using advanced AI.
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

      <section className="py-20 bg-slate-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-8 divide-x divide-slate-200">
            <div className="text-center px-2 sm:px-4">
              <p className="text-4xl md:text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-blue-600 mb-2">99%</p>
              <p className="text-sm text-slate-500 font-bold uppercase tracking-wider">Accuracy Rate</p>
            </div>
            <div className="text-center px-2 sm:px-4">
              <p className="text-4xl md:text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-blue-600 mb-2">&lt;1s</p>
              <p className="text-sm text-slate-500 font-bold uppercase tracking-wider">Processing Time</p>
            </div>
            <div className="text-center px-2 sm:px-4">
              <p className="text-4xl md:text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-blue-600 mb-2">30+</p>
              <p className="text-sm text-slate-500 font-bold uppercase tracking-wider">Faces per Frame</p>
            </div>
            <div className="text-center px-2 sm:px-4">
              <p className="text-4xl md:text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-blue-600 mb-2">24/7</p>
              <p className="text-sm text-slate-500 font-bold uppercase tracking-wider">Cloud Sync</p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-24 bg-white rounded-[3rem] lg:rounded-[4rem] shadow-sm relative z-10 -mt-8 content-vis-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-20">
            <h2 className="text-4xl md:text-5xl font-display font-bold text-slate-900 mb-6 tracking-tight">Powerful Features</h2>
            <p className="text-xl text-slate-600 max-w-2xl mx-auto">
              Everything you need to manage attendance and verify identities securely using advanced CNN ML.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="p-10 rounded-[2.5rem] bg-slate-50 border border-slate-100 hover:shadow-xl hover:shadow-indigo-500/10 hover:border-indigo-100 transition-all duration-300 group">
              <div className="w-16 h-16 rounded-2xl bg-blue-100 text-blue-600 flex items-center justify-center mb-8 transition-transform group-hover:scale-110">
                <UserCheck className="w-8 h-8" />
              </div>
              <h3 className="text-2xl font-bold text-slate-900 mb-4">Batch Processing</h3>
              <p className="text-slate-600 leading-relaxed">Simultaneously verify up to 30 faces per frame using YOLO-inspired detection, ideal for large classrooms.</p>
            </div>
            <div className="p-10 rounded-[2.5rem] bg-slate-50 border border-slate-100 hover:shadow-xl hover:shadow-emerald-500/10 hover:border-emerald-100 transition-all duration-300 group">
              <div className="w-16 h-16 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center mb-8 transition-transform group-hover:scale-110">
                <ShieldCheck className="w-8 h-8" />
              </div>
              <h3 className="text-2xl font-bold text-slate-900 mb-4">Anti-Spoofing</h3>
              <p className="text-slate-600 leading-relaxed">Advanced anti-spoofing measures including liveness tests to avoid photo/video manipulation.</p>
            </div>
            <div className="p-10 rounded-[2.5rem] bg-slate-50 border border-slate-100 hover:shadow-xl hover:shadow-amber-500/10 hover:border-amber-100 transition-all duration-300 group">
              <div className="w-16 h-16 rounded-2xl bg-amber-100 text-amber-600 flex items-center justify-center mb-8 transition-transform group-hover:scale-110">
                <Zap className="w-8 h-8" />
              </div>
              <h3 className="text-2xl font-bold text-slate-900 mb-4">Lightning Fast</h3>
              <p className="text-slate-600 leading-relaxed">Automatically configures detection parameters under various lighting conditions.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-24 bg-slate-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div>
              <h2 className="text-4xl md:text-5xl font-display font-bold text-slate-900 mb-8 tracking-tight">How FaceSnap Works</h2>
              <div className="space-y-8">
                <div className="flex gap-6 group">
                  <div className="w-14 h-14 rounded-2xl bg-white shadow-md border border-slate-100 text-indigo-600 flex items-center justify-center font-bold text-xl flex-shrink-0 transition-transform group-hover:scale-110">1</div>
                  <div>
                    <h4 className="text-xl font-bold text-slate-900 mb-2">Register Profile</h4>
                    <p className="text-slate-600">Students create an account and capture a clear image of their face. The system extracts unique facial descriptors using FaceNet.</p>
                  </div>
                </div>
                <div className="flex gap-6 group">
                  <div className="w-14 h-14 rounded-2xl bg-white shadow-md border border-slate-100 text-indigo-600 flex items-center justify-center font-bold text-xl flex-shrink-0 transition-transform group-hover:scale-110">2</div>
                  <div>
                    <h4 className="text-xl font-bold text-slate-900 mb-2">Live Scanning</h4>
                    <p className="text-slate-600">During class, a camera scans the room or doorway. The AI matches live faces against the registered database.</p>
                  </div>
                </div>
                <div className="flex gap-6 group">
                  <div className="w-14 h-14 rounded-2xl bg-white shadow-md border border-slate-100 text-indigo-600 flex items-center justify-center font-bold text-xl flex-shrink-0 transition-transform group-hover:scale-110">3</div>
                  <div>
                    <h4 className="text-xl font-bold text-slate-900 mb-2">Automated Attendance</h4>
                    <p className="text-slate-600">Attendance is automatically logged in the secure cloud database.</p>
                  </div>
                </div>
              </div>
            </div>
            <div className="relative h-[500px] bg-white rounded-[3rem] shadow-xl border border-slate-100 p-8 flex flex-col justify-center overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-50 rounded-full blur-3xl -mr-20 -mt-20"></div>
              <div className="absolute bottom-0 left-0 w-64 h-64 bg-blue-50 rounded-full blur-3xl -ml-20 -mb-20"></div>
              <div className="space-y-6 relative z-10">
                <div className="flex items-center gap-5 p-5 bg-white/80 backdrop-blur-sm rounded-2xl border border-slate-100 shadow-sm hover:shadow-md transition-shadow">
                  <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center">
                    <Database className="w-6 h-6 text-blue-600" />
                  </div>
                  <div>
                    <p className="font-bold text-slate-900">Secure Storage</p>
                    <p className="text-sm text-slate-500">Firebase Firestore Integration</p>
                  </div>
                </div>
                <div className="flex items-center gap-5 p-5 bg-white/80 backdrop-blur-sm rounded-2xl border border-slate-100 shadow-sm hover:shadow-md transition-shadow">
                  <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center">
                    <Clock className="w-6 h-6 text-emerald-600" />
                  </div>
                  <div>
                    <p className="font-bold text-slate-900">Real-time Processing</p>
                    <p className="text-sm text-slate-500">Sub-second latency</p>
                  </div>
                </div>
                <div className="flex items-center gap-5 p-5 bg-white/80 backdrop-blur-sm rounded-2xl border border-slate-100 shadow-sm hover:shadow-md transition-shadow">
                  <div className="w-12 h-12 rounded-xl bg-amber-50 flex items-center justify-center">
                    <Lock className="w-6 h-6 text-amber-600" />
                  </div>
                  <div>
                    <p className="font-bold text-slate-900">Privacy First</p>
                    <p className="text-sm text-slate-500">Encrypted descriptors</p>
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
