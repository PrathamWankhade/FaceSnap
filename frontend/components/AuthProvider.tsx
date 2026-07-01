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
  signingIn: boolean;
  signIn: () => Promise<void>;
  logOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  signingIn: false,
  signIn: async () => {},
  logOut: async () => {},
});

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [signingIn, setSigningIn] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (!auth) {
      setLoading(false);
      return;
    }

    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);

      if (currentUser && db) {
        const userRef = doc(db, 'users', currentUser.uid);

        getDoc(userRef).then((userSnap) => {
          if (!userSnap.exists()) {
            setDoc(userRef, {
              uid: currentUser.uid,
              email: currentUser.email,
              displayName: currentUser.displayName,
              role: 'student',
              createdAt: new Date().toISOString(),
            }).catch(() => {});
          }
        }).catch(() => {});
      }

      setLoading(false);
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
    } catch (error: any) {
      if (error.code === 'auth/popup-closed-by-user') return;
      if (error.code === 'auth/cancelled-popup-request') return;
      toast.error(error.message || 'Failed to sign in.');
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
    } catch (error: any) {
      toast.error(error.message || 'Failed to sign out.');
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, signingIn, signIn, logOut }}>
      {children}
    </AuthContext.Provider>
  );
}
