'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  User,
  onAuthStateChanged,
  signInWithPopup,
  signOut,
} from 'firebase/auth';
import { auth, googleProvider, db } from '../lib/firebase';
import { doc, getDoc, setDoc } from 'firebase/firestore';
import { toast } from 'sonner';
import { useRouter } from 'next/navigation';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  profileLoading: boolean;
  profileError: string | null;
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
  signingIn: false,
  signIn: async () => {},
  logOut: async () => {},
  retryProfile: async () => {},
});

export const useAuth = () => useContext(AuthContext);

async function ensureUserProfile(currentUser: User): Promise<void> {
  if (!db) throw new Error('Database not initialized.');
  const userRef = doc(db, 'users', currentUser.uid);
  const userSnap = await getDoc(userRef);
  if (!userSnap.exists()) {
    await setDoc(userRef, {
      uid: currentUser.uid,
      email: currentUser.email,
      displayName: currentUser.displayName,
      role: 'student',
      createdAt: new Date().toISOString(),
    });
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(() => auth != null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [signingIn, setSigningIn] = useState(false);
  const router = useRouter();

  const loadProfile = async (currentUser: User) => {
    setProfileLoading(true);
    setProfileError(null);
    try {
      await ensureUserProfile(currentUser);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to create user profile.';
      setProfileError(msg);
      console.error('Profile creation failed:', e);
    } finally {
      setProfileLoading(false);
    }
  };

  useEffect(() => {
    if (!auth) {
      return;
    }

    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
      setLoading(false);
      if (currentUser) {
        void loadProfile(currentUser);
      } else {
        setProfileError(null);
        setProfileLoading(false);
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
    <AuthContext.Provider value={{ user, loading, profileLoading, profileError, signingIn, signIn, logOut, retryProfile }}>
      {children}
    </AuthContext.Provider>
  );
}
