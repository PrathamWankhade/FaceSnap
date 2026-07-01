'use client';

import Link from 'next/link';
import { Home, ArrowLeft } from 'lucide-react';
import { motion } from 'motion/react';

export default function NotFound() {
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full text-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: 'spring', bounce: 0.4 }}
        >
          <div className="w-24 h-24 bg-indigo-100 rounded-[2rem] flex items-center justify-center mx-auto mb-8 shadow-inner">
            <span className="text-5xl font-black text-indigo-600">404</span>
          </div>
          <h1 className="text-4xl font-display font-bold text-slate-900 mb-4 tracking-tight">
            Page not found
          </h1>
          <p className="text-lg text-slate-600 mb-10 leading-relaxed">
            The page you are looking for does not exist or has been moved.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/"
              className="px-8 py-4 bg-gradient-to-r from-indigo-600 to-blue-600 text-white rounded-full font-bold hover:from-indigo-700 hover:to-blue-700 transition-all shadow-md shadow-indigo-500/20 hover:shadow-lg hover:shadow-indigo-500/30 hover:-translate-y-0.5 inline-flex items-center justify-center gap-3"
            >
              <Home className="w-5 h-5" />
              Go Home
            </Link>
            <button
              onClick={() => window.history.back()}
              className="px-8 py-4 bg-slate-100 text-slate-700 rounded-full font-bold hover:bg-slate-200 transition-all shadow-sm hover:-translate-y-0.5 inline-flex items-center justify-center gap-3"
            >
              <ArrowLeft className="w-5 h-5" />
              Go Back
            </button>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
