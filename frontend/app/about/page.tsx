'use client';

import Image from 'next/image';
import { Target, Users, ShieldCheck, Database, Server, Cpu } from 'lucide-react';
import { motion } from 'motion/react';

const team = [
  { name: 'Pratham Wankhade', role: 'Team Lead & AI/ML Engineer', image: "/assets/boy.png" },
  { name: 'Pranav Ladole', role: 'Backend Developer (Database & Logic)', image: "/assets/student.png" },
  { name: 'Suraj Borkute', role: 'Frontend Developer (UI)', image: "/assets/man-avatar.png" },
  { name: 'Yadnesh Umredkar', role: 'UI/UX Designer', image: "/assets/young-boy.png" },
  { name: 'Harsh Banode', role: 'Backend Support / System Implementation', image: "/assets/boy (1).png" }
];

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <section className="relative bg-slate-900 text-white py-24 lg:py-32 rounded-b-[3rem] lg:rounded-b-[4rem] overflow-hidden">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-indigo-500/30 rounded-full blur-3xl mix-blend-screen pointer-events-none"></div>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <h1 className="text-5xl md:text-7xl font-display font-bold mb-6 tracking-tight">About FaceSnap</h1>
            <p className="text-xl text-slate-300 max-w-3xl mx-auto leading-relaxed">
              We are building the future of secure, frictionless identity verification for educational institutions worldwide using FaceNet & YOLO CNN ML.
            </p>
          </motion.div>
        </div>
      </section>

      <section className="py-24 bg-slate-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <motion.div initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}>
              <h2 className="text-4xl font-bold text-slate-900 mb-6">Our Story</h2>
              <div className="space-y-6 text-lg text-slate-600 leading-relaxed">
                <p>FaceSnap was born out of a simple observation: traditional attendance tracking in large university classrooms is inefficient, prone to errors, and takes valuable time away from teaching.</p>
                <p>By leveraging edge-computing and advanced facial recognition models like FaceNet and YOLO CNNs, we built a system that can identify dozens of students simultaneously.</p>
                <p>Today, FaceSnap is a comprehensive identity verification platform designed with privacy, speed, and accuracy at its core.</p>
              </div>
            </motion.div>
            <motion.div initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} className="grid grid-cols-2 gap-4">
              <div className="bg-white rounded-[2rem] p-8 flex flex-col justify-center items-center text-center shadow-lg shadow-slate-200/50 border border-slate-100 hover:-translate-y-1 transition-transform">
                <div className="w-14 h-14 rounded-2xl bg-blue-50 flex items-center justify-center mb-4"><Target className="w-7 h-7 text-blue-600" /></div>
                <h3 className="font-bold text-slate-900 text-xl mb-2">Mission</h3>
                <p className="text-slate-500 text-sm">To eliminate friction in educational administration.</p>
              </div>
              <div className="bg-white rounded-[2rem] p-8 flex flex-col justify-center items-center text-center shadow-lg shadow-slate-200/50 border border-slate-100 hover:-translate-y-1 transition-transform">
                <div className="w-14 h-14 rounded-2xl bg-emerald-50 flex items-center justify-center mb-4"><ShieldCheck className="w-7 h-7 text-emerald-600" /></div>
                <h3 className="font-bold text-slate-900 text-xl mb-2">Vision</h3>
                <p className="text-slate-500 text-sm">A secure, seamless campus experience for every student.</p>
              </div>
              <div className="bg-white rounded-[2rem] p-8 flex flex-col justify-center items-center text-center shadow-lg shadow-slate-200/50 border border-slate-100 col-span-2 hover:-translate-y-1 transition-transform">
                <div className="w-14 h-14 rounded-2xl bg-amber-50 flex items-center justify-center mb-4"><Users className="w-7 h-7 text-amber-600" /></div>
                <h3 className="font-bold text-slate-900 text-xl mb-2">Community</h3>
                <p className="text-slate-500 text-sm">Built for educators, administrators, and students alike.</p>
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
              <h3 className="text-2xl font-bold mb-4">FaceNet & YOLO CNNs</h3>
              <p className="text-indigo-100 leading-relaxed">Facial detection and descriptor extraction using WebGL-accelerated TensorFlow.js and advanced CNN architectures.</p>
            </div>
            <div className="bg-white/10 backdrop-blur-lg rounded-[2rem] p-8 border border-white/20 hover:bg-white/20 transition-colors">
              <div className="w-14 h-14 rounded-2xl bg-white/20 flex items-center justify-center mb-6"><Database className="w-7 h-7 text-white" /></div>
              <h3 className="text-2xl font-bold mb-4">Vector Matching</h3>
              <p className="text-indigo-100 leading-relaxed">128-dimensional facial descriptors stored securely. Euclidean distance calculation for instant matching.</p>
            </div>
            <div className="bg-white/10 backdrop-blur-lg rounded-[2rem] p-8 border border-white/20 hover:bg-white/20 transition-colors">
              <div className="w-14 h-14 rounded-2xl bg-white/20 flex items-center justify-center mb-6"><Server className="w-7 h-7 text-white" /></div>
              <h3 className="text-2xl font-bold mb-4">Scalable Infrastructure</h3>
              <p className="text-indigo-100 leading-relaxed">Built on Next.js and Firebase, designed to handle thousands of concurrent verifications.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-24 bg-slate-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-slate-900 mb-6">Our Team</h2>
            <p className="text-xl text-slate-600 max-w-2xl mx-auto">The engineers and designers building the future of campus security.</p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8 justify-center">
            {team.map((member, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.1 }}
                className="bg-white rounded-[2rem] shadow-lg shadow-slate-200/50 border border-slate-100 p-8 text-center hover:-translate-y-2 transition-transform duration-300"
              >
                <div className="relative w-32 h-32 mx-auto mb-6 overflow-hidden rounded-[2rem] shadow-inner bg-slate-100">
                  <Image src={member.image} alt={member.name} fill sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw" className="object-cover" />
                </div>
                <h3 className="text-xl font-bold text-slate-900 mb-2">{member.name}</h3>
                <p className="text-indigo-600 font-bold text-sm uppercase tracking-wider">{member.role}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
