import Link from 'next/link';
import { Camera, Twitter, Linkedin, Github, Mail, ScanFace } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="bg-slate-900 text-slate-300 py-16 border-t border-slate-800 rounded-t-[2.5rem] mt-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12 md:gap-8 mb-16">
          
          {/* Brand Column */}
          <div className="col-span-1 md:col-span-1">
            <Link href="/" className="flex items-center gap-3 mb-6 group">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center text-white shadow-lg shadow-indigo-500/30 transition-transform group-hover:scale-105">
                <ScanFace className="w-6 h-6 text-white" />
              </div>
              <span className="font-display font-bold text-2xl tracking-tight text-white">
                FaceSnap
              </span>
            </Link>
            <p className="text-sm text-slate-400 leading-relaxed mb-8">
              Revolutionizing Attendance System
            </p>
            <div className="flex items-center gap-4">
              <a href="#" className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 hover:bg-indigo-600 hover:text-white transition-all hover:-translate-y-1">
                <Twitter className="w-4 h-4" />
              </a>
              <a href="#" className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 hover:bg-indigo-600 hover:text-white transition-all hover:-translate-y-1">
                <Linkedin className="w-4 h-4" />
              </a>
              <a href="#" className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 hover:bg-indigo-600 hover:text-white transition-all hover:-translate-y-1">
                <Github className="w-4 h-4" />
              </a>
            </div>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="text-white font-bold mb-6 uppercase tracking-widest text-sm">Platform</h3>
            <ul className="space-y-4">
              <li>
                <Link href="/" className="text-sm text-slate-400 hover:text-indigo-400 transition-colors">Home</Link>
              </li>
              <li>
                <Link href="/register" className="text-sm text-slate-400 hover:text-indigo-400 transition-colors">Student Registration</Link>
              </li>
              <li>
                <Link href="/student" className="text-sm text-slate-400 hover:text-indigo-400 transition-colors">Identity Verification</Link>
              </li>
              <li>
                <a href="#" className="text-sm text-slate-400 hover:text-indigo-400 transition-colors">How it Works</a>
              </li>
            </ul>
          </div>

          {/* Resources */}
          <div>
            <h3 className="text-white font-bold mb-6 uppercase tracking-widest text-sm">Resources</h3>
            <ul className="space-y-4">
              <li>
                <a href="#" className="text-sm text-slate-400 hover:text-indigo-400 transition-colors">Documentation</a>
              </li>
              <li>
                <a href="#" className="text-sm text-slate-400 hover:text-indigo-400 transition-colors">API Reference</a>
              </li>
              <li>
                <a href="#" className="text-sm text-slate-400 hover:text-indigo-400 transition-colors">Help Center</a>
              </li>
              <li>
                <a href="#" className="text-sm text-slate-400 hover:text-indigo-400 transition-colors">Community</a>
              </li>
            </ul>
          </div>

          {/* Contact */}
          <div>
            <h3 className="text-white font-bold mb-6 uppercase tracking-widest text-sm">Contact Us</h3>
            <ul className="space-y-5">
              <li>
                <a href="mailto:support@facesnap.edu" className="flex items-center gap-3 text-sm text-slate-400 hover:text-indigo-400 transition-colors">
                  <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-slate-300">
                    <Mail className="w-4 h-4" />
                  </div>
                  support@facesnap.edu
                </a>
              </li>
              <li className="text-sm text-slate-400 leading-relaxed pl-11">
                Mohagaon, Wardha Rd,<br />
                Nagpur, Maharashtra 441108
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="pt-8 border-t border-slate-800 flex flex-col md:flex-row justify-between items-center gap-6">
          <p className="text-sm text-slate-500">
            &copy; {new Date().getFullYear()} FaceSnap System. All rights reserved.
          </p>
          <div className="flex flex-wrap justify-center gap-x-8 gap-y-4">
            <a href="#" className="text-sm text-slate-500 hover:text-slate-300 transition-colors">Privacy Policy</a>
            <a href="#" className="text-sm text-slate-500 hover:text-slate-300 transition-colors">Terms of Service</a>
            <a href="#" className="text-sm text-slate-500 hover:text-slate-300 transition-colors">Cookie Settings</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
