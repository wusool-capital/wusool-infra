"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { getCurrentWindow } from '@tauri-apps/api/window';

export type Theme = 'light' | 'dark';

const STORAGE_KEY = 'wusoolscribe-theme';

interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark');
  // tauri.conf.json's window `theme` only sets the initial native title
  // bar/traffic-lights appearance -- without this, the OS-drawn chrome
  // stays on that initial value forever and never follows the app's own
  // light/dark toggle. Swallow failures: this call only matters inside a
  // real Tauri window (e.g. not `next dev` in a plain browser tab).
  getCurrentWindow()
    .setTheme(theme)
    .catch((err) => console.error('Failed to sync native window theme:', err));
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Light mode is the default -- only an explicit prior choice in
  // localStorage overrides it.
  const [theme, setThemeState] = useState<Theme>('light');

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    const initial: Theme = stored === 'light' || stored === 'dark' ? stored : 'light';
    setThemeState(initial);
    applyTheme(initial);
  }, []);

  const setTheme = (next: Theme) => {
    setThemeState(next);
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  };

  const toggleTheme = () => setTheme(theme === 'dark' ? 'light' : 'dark');

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within a ThemeProvider');
  return ctx;
}
