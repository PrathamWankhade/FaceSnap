'use client';

import { initializeApp, getApps, FirebaseApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';
import { getFirestore, setLogLevel } from 'firebase/firestore';
import { getStorage } from 'firebase/storage';

const firebaseConfig = {
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  measurementId: process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID,
};

setLogLevel('error');

function getApp(): FirebaseApp | null {
  if (typeof window === 'undefined') return null;
  if (!firebaseConfig.apiKey) return null;
  try {
    if (!getApps().length) {
      return initializeApp(firebaseConfig);
    }
    return getApps()[0];
  } catch {
    return null;
  }
}

const app = getApp();

export const auth = app ? getAuth(app) : null!;
export const db = app ? getFirestore(app) : null!;
export const storage = app ? getStorage(app) : null!;
export const googleProvider = app ? new GoogleAuthProvider() : null!;

if (googleProvider) {
  googleProvider.setCustomParameters({
    prompt: 'select_account',
  });
}
