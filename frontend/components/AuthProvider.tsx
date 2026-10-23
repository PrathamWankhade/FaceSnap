'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  User,
  onAuthStateChanged,
  signInWithPopup,
  signOut,
} from 'firebase/auth';
import { auth, googleProvider } from '../lib/firebase';
import { getBackendUrl } from '../lib/utils';
import { toast } from 'sonner';
import { useRouter } from 'next/navigation';

export type UserRole = 'admin' | 'student';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  profileLoading: boolean;
  profileError: string | null;
  role: UserRole | null;
  roleLoading: boolean;
  signingIn: boolean;
  signIn: () => Promise<void>;
  logOut: () => Promise<void>;
  retryProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  profileLoading: false,
  profileError: null,
  role: null,
  roleLoading: false,
  signingIn: false,
  signIn: async () => {},
  logOut: async () => {},
  retryProfile: async () => {},
});

export const useAuth = () => useContext(AuthContext);

/**
 * Resolve the authoritative role from the backend (relational users table).
 * Firebase remains the identity provider only.
 */
async function ensureUserProfile(currentUser: User): Promise<UserRole> {
  try {
    const token = await currentUser.getIdToken();
    const res = await fetch(getBackendUrl('/api/me'), {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const me = (await res.json()) as { role?: string };
      return me.role === 'admin' || me.role === 'operator' ? 'admin' : 'student';
    }
  } catch {
    // Backend unreachable: fail closed to the least-privileged role.
  }
  return 'student';
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [role, setRole] = useState<UserRole | null>(null);
  const [roleLoading, setRoleLoading] = useState(false);
  const [signingIn, setSigningIn] = useState(false);
  const router = useRouter();

  const loadProfile = async (currentUser: User) => {
    setProfileLoading(true);
    setRoleLoading(true);
    setProfileError(null);
    try {
      const resolvedRole = await ensureUserProfile(currentUser);
      setRole(resolvedRole);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to create user profile.';
      setProfileError(msg);
      console.error('Profile creation failed:', e);
    } finally {
      setProfileLoading(false);
      setRoleLoading(false);
    }
  };

  useEffect(() => {
    if (!auth) {
      // No Firebase config (e.g. unconfigured env): resolve on the next tick
      // so the UI never hangs on the loading state.
      const id = setTimeout(() => setLoading(false), 0);
      return () => clearTimeout(id);
    }

    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
      setLoading(false);
      if (currentUser) {
        void loadProfile(currentUser);
      } else {
        setProfileError(null);
        setProfileLoading(false);
        setRole(null);
        setRoleLoading(false);
      }
    });

    return () => unsubscribe();
  }, []);

  const signIn = async () => {
    if (signingIn || !auth || !googleProvider) return;
    setSigningIn(true);

    try {
      await signInWithPopup(auth, googleProvider);
      toast.success('Signed in successfully');
      router.push('/');
    } catch (error: unknown) {
      const code = (error as { code?: string }).code;
      if (code === 'auth/popup-closed-by-user') return;
      if (code === 'auth/cancelled-popup-request') return;
      toast.error(error instanceof Error ? error.message : 'Failed to sign in.');
    } finally {
      setSigningIn(false);
    }
  };

  const logOut = async () => {
    if (!auth) return;
    try {
      await signOut(auth);
      toast.success('Signed out successfully');
      router.push('/');
    } catch (error: unknown) {
      toast.error(error instanceof Error ? error.message : 'Failed to sign out.');
    }
  };

  const retryProfile = async () => {
    if (auth?.currentUser) await loadProfile(auth.currentUser);
  };

  return (
    <AuthContext.Provider value={{ user, loading, profileLoading, profileError, role, roleLoading, signingIn, signIn, logOut, retryProfile }}>
      {children}
    </AuthContext.Provider>
  );
}
