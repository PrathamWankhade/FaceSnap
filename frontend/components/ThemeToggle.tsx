'use client';

import { Moon, Sun } from 'lucide-react';
import { motion } from 'motion/react';
import { useTheme } from './ThemeProvider';

/**
 * Icon/label visibility is driven by the `dark` class on <html> (CSS), not by
 * React state. Server HTML always renders the light variant, so hydration
 * never mismatches even when the stored/system preference is dark.
 */
export default function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { toggleTheme } = useTheme();

  return (
    <motion.button
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      onClick={toggleTheme}
      aria-label="Toggle color theme"
      title="Toggle color theme"
      className={
        compact
          ? 'p-2 rounded-full text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white'
          : 'flex items-center gap-2 px-4 py-2.5 rounded-full text-sm font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 hover:text-slate-900 transition-all dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 dark:hover:text-white'
      }
    >
      <Sun className="w-4 h-4 dark:hidden" />
      <Moon className="w-4 h-4 hidden dark:block" />
      {!compact && (
        <>
          {/* Text depends only on CSS state, never React state, so SSR matches. */}
          <span className="dark:hidden">Dark</span>
          <span className="hidden dark:inline">Light</span>
        </>
      )}
    </motion.button>
  );
}
