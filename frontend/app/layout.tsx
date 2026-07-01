import type { Metadata, Viewport } from 'next';
import { Inter, Space_Grotesk } from 'next/font/google';
import './globals.css';
import { AuthProvider } from '@/components/AuthProvider';
import Navigation from '@/components/Navigation';
import Footer from '@/components/Footer';
import { ErrorBoundary } from '@/components/ErrorBoundary';
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
      <body className="font-sans antialiased text-gray-900 bg-gray-50 min-h-screen flex flex-col" suppressHydrationWarning>
        <ErrorBoundary>
          <AuthProvider>
            <Navigation />
            <main className="flex-1 flex flex-col">
              {children}
            </main>
            <Footer />
            <ChatbotWrapper />
            <Toaster position="top-center" richColors theme="light" />
          </AuthProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}
