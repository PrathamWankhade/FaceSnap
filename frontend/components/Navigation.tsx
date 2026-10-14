'use client';

import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { useAuth } from './AuthProvider';
import ThemeToggle from './ThemeToggle';
import { LogIn, LogOut, User as UserIcon, Home, UserPlus, GraduationCap, Camera, Info, Phone, Users, Menu, X, ScanFace, Loader2, ClipboardList } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

export default function Navigation() {
  const pathname = usePathname();
  const { user, loading, signingIn, signIn, logOut, role, roleLoading } = useAuth();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const publicNavItems = [
    { name: 'Home', path: '/', icon: Home },
    { name: 'About Us', path: '/about', icon: Info },
    { name: 'Contact', path: '/contact', icon: Phone },
  ];

  // Camera operations are for staff; the backend still enforces authorization.
  const studentNavItems = [
    { name: 'Home', path: '/', icon: Home },
    { name: 'Register', path: '/register', icon: UserPlus },
    { name: 'Verify', path: '/student', icon: GraduationCap },
    { name: 'Records', path: '/attendance', icon: ClipboardList },
  ];

  const staffNavItems = [
    ...studentNavItems,
    { name: 'Batch', path: '/classroom', icon: Users },
    { name: 'CCTV', path: '/cctv', icon: Camera },
  ];

  const navItems = !user ? publicNavItems : role === 'admin' && !roleLoading ? staffNavItems : studentNavItems;

  return (
    <nav className="sticky top-0 z-50 w-full bg-white/80 backdrop-blur-xl border-b border-slate-200/50 shadow-sm gpu dark:bg-slate-950/80 dark:border-slate-800/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-20 items-center">
          
          {/* Logo */}
          <div className="flex items-center gap-4 lg:gap-8">
            <Link href="/" className="flex items-center gap-3 group">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center text-white shadow-lg shadow-indigo-500/30 transition-transform group-hover:scale-105">
                <ScanFace className="w-6 h-6 text-white" />
              </div>
              <span className="font-display font-bold text-xl sm:text-2xl tracking-tight text-slate-900 dark:text-white"> FaceSnap</span>
            </Link>
            
            {/* Desktop Nav */}
            <div className="hidden md:flex items-center gap-1 ml-4 bg-slate-100/50 p-1 rounded-full border border-slate-200/50 dark:bg-slate-800/60 dark:border-slate-700/60">
              {navItems.map((item) => {
                const isActive = pathname === item.path;
                return (
                  <Link
                    key={item.path}
                    href={item.path}
                    className={`relative px-4 py-2 rounded-full text-sm font-semibold transition-all duration-300 ${
                      isActive ? 'text-indigo-700 bg-white shadow-sm dark:text-indigo-300 dark:bg-slate-900' : 'text-slate-500 hover:text-slate-900 hover:bg-slate-200/50 dark:text-slate-400 dark:hover:text-white dark:hover:bg-slate-700/60'
                    }`}
                  >
                    {item.name}
                  </Link>
                );
              })}
            </div>
          </div>

          {/* Right Side Actions */}
          <div className="flex items-center gap-2 sm:gap-4">
            <ThemeToggle compact />
            {user ? (
              <div className="flex items-center gap-2 sm:gap-4">
                <div className="hidden sm:flex items-center gap-3 px-4 py-2 rounded-full bg-white border border-slate-200 shadow-sm dark:bg-slate-900 dark:border-slate-700">
                  {user.photoURL ? (
                    <div className="relative w-7 h-7 rounded-full overflow-hidden shadow-sm">
                      <Image src={user.photoURL} alt="Profile" fill sizes="28px" className="object-cover" referrerPolicy="no-referrer" />
                    </div>
                  ) : (
                    <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center dark:bg-indigo-950">
                      <UserIcon className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-300" />
                    </div>
                  )}
                  <span className="font-semibold text-sm text-slate-700 truncate max-w-[120px] lg:max-w-[200px] dark:text-slate-200">{user.displayName || user.email}</span>
                  {role === 'admin' && (
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">Admin</span>
                  )}
                </div>
                <button
                  onClick={logOut}
                  className="hidden sm:flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 hover:text-slate-900 transition-all dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 dark:hover:text-white"
                >
                  <LogOut className="w-4 h-4" />
                  Sign Out
                </button>
              </div>
            ) : loading ? (
              <div className="hidden sm:flex items-center gap-2 px-6 py-2.5 rounded-full text-sm font-semibold text-slate-400 bg-slate-100 dark:bg-slate-800 dark:text-slate-500">
                <Loader2 className="w-4 h-4 animate-spin" />
              </div>
            ) : (
              <button
                onClick={signIn}
                disabled={signingIn}
                className="hidden sm:flex items-center gap-2 px-6 py-2.5 rounded-full text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 transition-all shadow-md shadow-indigo-500/20 hover:shadow-indigo-500/40 hover:-translate-y-0.5 disabled:opacity-60"
              >
                {signingIn ? <><Loader2 className="w-4 h-4 animate-spin" /> Signing in...</> : 'Sign In'}
              </button>
            )}
            
            {/* Mobile menu button */}
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="md:hidden p-2 rounded-full text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white"
            >
              {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden border-t border-slate-200 bg-white/95 backdrop-blur-xl overflow-hidden dark:border-slate-800 dark:bg-slate-950/95"
          >
            <div className="px-4 py-4 flex flex-col gap-2">
              {user && (
                <div className="flex sm:hidden items-center gap-3 px-4 py-3 mb-2 rounded-2xl bg-slate-50 border border-slate-100 dark:bg-slate-900 dark:border-slate-800">
                  {user.photoURL ? (
                    <div className="relative w-8 h-8 rounded-full overflow-hidden">
                      <Image src={user.photoURL} alt="Profile" fill sizes="32px" className="object-cover" referrerPolicy="no-referrer" />
                    </div>
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center dark:bg-indigo-950">
                      <UserIcon className="w-4 h-4 text-indigo-600 dark:text-indigo-300" />
                    </div>
                  )}
                  <span className="font-semibold text-sm text-slate-900 truncate dark:text-white">{user.displayName || user.email}</span>
                  {role === 'admin' && (
                    <span className="ml-auto text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">Admin</span>
                  )}
                </div>
              )}
              
              {navItems.map((item) => {
                const isActive = pathname === item.path;
                const Icon = item.icon;
                return (
                  <Link
                    key={item.path}
                    href={item.path}
                    onClick={() => setIsMobileMenuOpen(false)}
                    className={`flex items-center gap-3 px-4 py-3 rounded-2xl text-sm font-semibold transition-all ${
                      isActive ? 'text-indigo-700 bg-indigo-50 dark:text-indigo-300 dark:bg-indigo-950/60' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50 dark:text-slate-400 dark:hover:text-white dark:hover:bg-slate-800'
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                    {item.name}
                  </Link>
                );
              })}
              
              <div className="mt-2 pt-2 border-t border-slate-100 sm:hidden dark:border-slate-800">
                {user ? (
                  <button
                    onClick={() => {
                      logOut();
                      setIsMobileMenuOpen(false);
                    }}
                    className="flex w-full items-center gap-3 px-4 py-3 rounded-2xl text-sm font-semibold text-rose-600 bg-rose-50 hover:bg-rose-100 transition-colors dark:text-rose-300 dark:bg-rose-950/50 dark:hover:bg-rose-950"
                  >
                    <LogOut className="w-5 h-5" />
                    Sign Out
                  </button>
                ) : (
                  <button
                    onClick={() => {
                      signIn();
                      setIsMobileMenuOpen(false);
                    }}
                    disabled={signingIn}
                    className="flex w-full items-center gap-3 px-4 py-3 rounded-2xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 transition-colors disabled:opacity-60"
                  >
                    {signingIn ? <><Loader2 className="w-5 h-5 animate-spin" /> Signing in...</> : <><LogIn className="w-5 h-5" /> Sign In</>}
                  </button>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}
