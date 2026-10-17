'use client';

import { Target, Users, ShieldCheck, Database, Server, Cpu } from 'lucide-react';
import { motion } from 'motion/react';

const team = [
  { name: 'Pratham Wankhade', role: 'Team Lead & AI/ML Engineer', initials: 'PW' },
  { name: 'Pranav Ladole', role: 'Backend Developer (Database & Logic)', initials: 'PL' },
  { name: 'Suraj Borkute', role: 'Frontend Developer (UI)', initials: 'SB' },
  { name: 'Yadnesh Umredkar', role: 'UI/UX Designer', initials: 'YU' },
  { name: 'Harsh Banode', role: 'Backend Support / System Implementation', initials: 'HB' }
];

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <section className="relative bg-slate-900 text-white py-24 lg:py-32 rounded-b-[3rem] lg:rounded-b-[4rem] overflow-hidden">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-indigo-500/30 rounded-full blur-3xl mix-blend-screen pointer-events-none"></div>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <h1 className="text-5xl md:text-7xl font-display font-bold mb-6 tracking-tight">About FaceSnap</h1>
            <p className="text-xl text-slate-300 max-w-3xl mx-auto leading-relaxed">
              We are building the future of secure, frictionless identity verification for educational institutions worldwide using InsightFace ArcFace embeddings, ONNX Runtime inference, and Qdrant vector search.
            </p>
          </motion.div>
        </div>
      </section>

      <section className="py-24 bg-slate-50 dark:bg-slate-950">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <motion.div initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}>
              <h2 className="text-4xl font-bold text-slate-900 dark:text-white mb-6">Our Story</h2>
              <div className="space-y-6 text-lg text-slate-600 dark:text-slate-300 leading-relaxed">
                <p>FaceSnap was born out of a simple observation: traditional attendance tracking in large university classrooms is inefficient, prone to errors, and takes valuable time away from teaching.</p>
                <p>By leveraging edge-computing and advanced facial recognition with InsightFace ArcFace embeddings served via ONNX Runtime, we built a system that can identify dozens of students simultaneously.</p>
                <p>Today, FaceSnap is a comprehensive identity verification platform designed with privacy, speed, and accuracy at its core.</p>
              </div>
            </motion.div>
            <motion.div initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} className="grid grid-cols-2 gap-4">
              <div className="bg-white dark:bg-slate-900 rounded-[2rem] p-8 flex flex-col justify-center items-center text-center shadow-lg shadow-slate-200/50 border border-slate-100 dark:border-slate-800 hover:-translate-y-1 transition-transform">
                <div className="w-14 h-14 rounded-2xl bg-blue-50 dark:bg-blue-950/50 flex items-center justify-center mb-4"><Target className="w-7 h-7 text-blue-600" /></div>
                <h3 className="font-bold text-slate-900 dark:text-white text-xl mb-2">Mission</h3>
                <p className="text-slate-500 dark:text-slate-400 text-sm">To eliminate friction in educational administration.</p>
              </div>
              <div className="bg-white dark:bg-slate-900 rounded-[2rem] p-8 flex flex-col justify-center items-center text-center shadow-lg shadow-slate-200/50 border border-slate-100 dark:border-slate-800 hover:-translate-y-1 transition-transform">
                <div className="w-14 h-14 rounded-2xl bg-emerald-50 dark:bg-emerald-950/50 flex items-center justify-center mb-4"><ShieldCheck className="w-7 h-7 text-emerald-600" /></div>
                <h3 className="font-bold text-slate-900 dark:text-white text-xl mb-2">Vision</h3>
                <p className="text-slate-500 dark:text-slate-400 text-sm">A secure, seamless campus experience for every student.</p>
              </div>
              <div className="bg-white dark:bg-slate-900 rounded-[2rem] p-8 flex flex-col justify-center items-center text-center shadow-lg shadow-slate-200/50 border border-slate-100 dark:border-slate-800 col-span-2 hover:-translate-y-1 transition-transform">
                <div className="w-14 h-14 rounded-2xl bg-amber-50 dark:bg-amber-950/50 flex items-center justify-center mb-4"><Users className="w-7 h-7 text-amber-600" /></div>
                <h3 className="font-bold text-slate-900 dark:text-white text-xl mb-2">Community</h3>
                <p className="text-slate-500 dark:text-slate-400 text-sm">Built for educators, administrators, and students alike.</p>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      <section className="py-24 bg-gradient-to-br from-indigo-600 to-blue-700 text-white rounded-[3rem] lg:rounded-[4rem] mx-4 sm:mx-6 lg:mx-8 shadow-2xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-6">The Technology Behind FaceSnap</h2>
            <p className="text-xl text-indigo-100 max-w-3xl mx-auto">We utilize state-of-the-art machine learning models optimized for real-time performance.</p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-white/10 backdrop-blur-lg rounded-[2rem] p-8 border border-white/20 hover:bg-white/20 transition-colors">
              <div className="w-14 h-14 rounded-2xl bg-white/20 flex items-center justify-center mb-6"><Cpu className="w-7 h-7 text-white" /></div>
              <h3 className="text-2xl font-bold mb-4">InsightFace ArcFace</h3>
              <p className="text-indigo-100 leading-relaxed">Face detection plus 512-dim ArcFace embeddings running on ONNX Runtime, with liveness anti-spoofing.</p>
            </div>
            <div className="bg-white/10 backdrop-blur-lg rounded-[2rem] p-8 border border-white/20 hover:bg-white/20 transition-colors">
              <div className="w-14 h-14 rounded-2xl bg-white/20 flex items-center justify-center mb-6"><Database className="w-7 h-7 text-white" /></div>
              <h3 className="text-2xl font-bold mb-4">Vector Matching</h3>
              <p className="text-indigo-100 leading-relaxed">512-dimensional facial embeddings stored securely. Cosine-distance matching via Qdrant vector search for instant identification.</p>
            </div>
            <div className="bg-white/10 backdrop-blur-lg rounded-[2rem] p-8 border border-white/20 hover:bg-white/20 transition-colors">
              <div className="w-14 h-14 rounded-2xl bg-white/20 flex items-center justify-center mb-6"><Server className="w-7 h-7 text-white" /></div>
              <h3 className="text-2xl font-bold mb-4">Scalable Infrastructure</h3>
              <p className="text-indigo-100 leading-relaxed">Built on Next.js and Firebase, designed for reliable classroom-scale attendance — dozens of students per session.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-24 bg-slate-50 dark:bg-slate-950">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-slate-900 dark:text-white mb-6">Our Team</h2>
            <p className="text-xl text-slate-600 dark:text-slate-300 max-w-2xl mx-auto">The engineers and designers building the future of campus security.</p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8 justify-center">
            {team.map((member, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.1 }}
                className="bg-white dark:bg-slate-900 rounded-[2rem] shadow-lg shadow-slate-200/50 border border-slate-100 dark:border-slate-800 p-8 text-center hover:-translate-y-2 transition-transform duration-300"
              >
                <div className="relative w-32 h-32 mx-auto mb-6 overflow-hidden rounded-[2rem] shadow-inner bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center">
                  <span className="font-display text-4xl font-bold text-white">{member.initials}</span>
                </div>
                <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-2">{member.name}</h3>
                <p className="text-indigo-600 font-bold text-sm uppercase tracking-wider">{member.role}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
