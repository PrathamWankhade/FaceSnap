import { Loader2 } from 'lucide-react';

export default function Loading() {
  return (
    <div className="flex-1 bg-slate-50 min-h-screen flex items-center justify-center">
      <div className="flex flex-col items-center gap-4 bg-white p-8 rounded-3xl shadow-lg border border-slate-100">
        <Loader2 className="w-10 h-10 text-indigo-600 animate-spin" />
        <p className="text-slate-500 font-semibold">Loading...</p>
      </div>
    </div>
  );
}
