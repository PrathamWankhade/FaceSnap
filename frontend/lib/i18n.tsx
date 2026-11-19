'use client';

import React, { createContext, useContext, useState } from 'react';

export type Locale = 'en' | 'hi';

const STORAGE_KEY = 'facesnap.locale';

const dictionaries: Record<Locale, Record<string, string>> = {
  en: {
    'nav.home': 'Home',
    'nav.about': 'About Us',
    'nav.contact': 'Contact',
    'nav.register': 'Register',
    'nav.verify': 'Verify',
    'nav.records': 'Records',
    'nav.batch': 'Batch',
    'nav.cctv': 'CCTV',
    'nav.analytics': 'Analytics',
    'nav.signIn': 'Sign In',
    'nav.signOut': 'Sign Out',
    'common.loading': 'Loading...',
    'home.title': 'Intelligent Student Verification',
    'home.subtitle': 'AI-powered facial recognition for campus attendance.',
  },
  hi: {
    'nav.home': 'होम',
    'nav.about': 'हमारे बारे में',
    'nav.contact': 'संपर्क',
    'nav.register': 'पंजीकरण',
    'nav.verify': 'सत्यापन',
    'nav.records': 'रिकॉर्ड',
    'nav.batch': 'बैच',
    'nav.cctv': 'सीसीटीवी',
    'nav.analytics': 'विश्लेषण',
    'nav.signIn': 'साइन इन',
    'nav.signOut': 'साइन आउट',
    'common.loading': 'लोड हो रहा है...',
    'home.title': 'बुद्धिमान छात्र सत्यापन',
    'home.subtitle': 'कैम्पस उपस्थिति के लिए एआई चेहरा पहचान।',
  },
};

interface LocaleContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string) => string;
}

const LocaleContext = createContext<LocaleContextValue>({
  locale: 'en',
  setLocale: () => {},
  t: (key) => key,
});

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => {
    if (typeof window === 'undefined') return 'en';
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored === 'en' || stored === 'hi') return stored;
    } catch {
      // ignore
    }
    return 'en';
  });

  const setLocale = (next: Locale) => {
    setLocaleState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore
    }
  };

  const t = (key: string) => dictionaries[locale][key] ?? key;

  return (
    <LocaleContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </LocaleContext.Provider>
  );
}

export function useLocale() {
  return useContext(LocaleContext);
}

export function useT() {
  return useContext(LocaleContext).t;
}
