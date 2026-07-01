'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      let errorMessage = this.state.error?.message || 'An unexpected error occurred.';
      try {
        const parsed = JSON.parse(errorMessage);
        if (parsed.error) {
          errorMessage = parsed.error;
        }
      } catch (e) {
        // Not JSON, use as is
      }

      return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] p-8 text-center relative overflow-hidden bg-slate-50">
          <div className="absolute top-0 right-0 w-full h-full overflow-hidden pointer-events-none z-0">
            <div className="absolute top-[-20%] right-[-10%] w-[50%] h-[60%] rounded-full bg-rose-100 blur-[120px] opacity-60" />
            <div className="absolute bottom-[-20%] left-[-10%] w-[50%] h-[60%] rounded-full bg-indigo-100 blur-[120px] opacity-60" />
          </div>
          
          <div 
            className="bg-white p-10 rounded-[40px] max-w-md w-full shadow-2xl shadow-indigo-900/10 border border-indigo-50 relative z-10 animate-in fade-in zoom-in duration-500 spring-bounce"
            style={{ animationTimingFunction: 'cubic-bezier(0.175, 0.885, 0.32, 1.275)' }}
          >
            <div className="w-20 h-20 bg-rose-50 rounded-3xl flex items-center justify-center mx-auto mb-6 text-rose-600 shadow-inner">
              <AlertCircle className="w-10 h-10" />
            </div>
            <h2 className="text-3xl font-display font-bold text-indigo-950 mb-3 uppercase tracking-tight">Oops! Something went wrong</h2>
            <p className="text-slate-600 mb-8 leading-relaxed">{errorMessage}</p>
            <button
              className="w-full flex items-center justify-center gap-3 px-8 py-4 bg-indigo-600 text-white font-bold text-lg rounded-2xl hover:bg-indigo-500 transition-all active:scale-95 shadow-[0_0_30px_-5px_rgba(79,70,229,0.4)]"
              onClick={() => this.setState({ hasError: false, error: null })}
            >
              <RefreshCw className="w-5 h-5" />
              Try again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
