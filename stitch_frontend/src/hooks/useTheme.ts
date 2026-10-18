'use client';

import { useCallback, useSyncExternalStore } from 'react';

type Theme = 'dark' | 'light';
const STORAGE_KEY = 'binom-theme';
const THEME_EVENT = 'binom:theme-change';

function storedTheme(): Theme | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value === 'dark' || value === 'light' ? value : null;
  } catch {
    return null;
  }
}

export function getInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'light';
  const explicit = storedTheme();
  if (explicit) return explicit;
  const applied = document.documentElement.dataset.theme;
  if (applied === 'dark' || applied === 'light') return applied;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  window.dispatchEvent(new Event(THEME_EVENT));
}

function subscribe(onChange: () => void) {
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  if (!document.documentElement.dataset.theme) applyTheme(getInitialTheme());
  const onStorage = (event: StorageEvent) => {
    if (event.key !== STORAGE_KEY && event.key !== null) return;
    applyTheme(storedTheme() ?? (media.matches ? 'dark' : 'light'));
  };
  const onSystemChange = () => {
    if (!storedTheme()) applyTheme(media.matches ? 'dark' : 'light');
  };
  window.addEventListener(THEME_EVENT, onChange);
  window.addEventListener('storage', onStorage);
  media.addEventListener('change', onSystemChange);
  return () => {
    window.removeEventListener(THEME_EVENT, onChange);
    window.removeEventListener('storage', onStorage);
    media.removeEventListener('change', onSystemChange);
  };
}

const serverSnapshot = (): Theme => 'light';

export function useTheme() {
  const theme = useSyncExternalStore(subscribe, getInitialTheme, serverSnapshot);
  const toggle = useCallback(() => {
    const next = getInitialTheme() === 'dark' ? 'light' : 'dark';
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* Theme also works without storage. */
    }
    applyTheme(next);
  }, []);
  return { theme, toggle };
}
