import type { Metadata, Viewport } from 'next';
import { Inter, Space_Grotesk } from 'next/font/google';
import './globals.css';
import { AuthProvider } from '@/components/AuthProvider';
import { ThemeProvider } from '@/components/ThemeProvider';
import Navigation from '@/components/Navigation';
import Footer from '@/components/Footer';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { MotionConfig } from 'motion/react';
import ChatbotWrapper from '@/components/ChatbotWrapper';
import { Toaster } from 'sonner';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans', display: 'swap' });
const spaceGrotesk = Space_Grotesk({ subsets: ['latin'], variable: '--font-display', display: 'swap' });

export const metadata: Metadata = {
  title: 'FaceSnap | Intelligent Student Verification',
  description: 'An exceptionally intelligent user interface for student registration and verification.',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#0f172a',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${spaceGrotesk.variable}`}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className="font-sans antialiased text-slate-900 bg-slate-50 min-h-screen flex flex-col dark:bg-slate-950 dark:text-slate-100" suppressHydrationWarning>
        <ErrorBoundary>
          <ThemeProvider>
          <AuthProvider>
            <a
              href="#main-content"
              className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-[60] focus:rounded-full focus:bg-indigo-600 focus:px-5 focus:py-3 focus:text-sm focus:font-bold focus:text-white focus:shadow-lg"
            >
              Skip to main content
            </a>
            <Navigation />
            <MotionConfig reducedMotion="user">
              <Navigation />
              <main id="main-content" tabIndex={-1} className="flex-1 flex flex-col">
                {children}
              </main>
              <Footer />
              <ChatbotWrapper />
              <Toaster position="top-center" richColors theme="system" />
            </MotionConfig>
          </AuthProvider>
          </ThemeProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}
