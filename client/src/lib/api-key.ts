import { useSyncExternalStore } from "react";

// sessionStorage: the key dies with the tab, never persisting on shared machines.
const STORAGE_KEY = "wusool.web-api-key";
const listeners = new Set<() => void>();

function read(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function getApiKey(): string | null {
  return read();
}

export function setApiKey(key: string | null): void {
  try {
    if (key === null) sessionStorage.removeItem(STORAGE_KEY);
    else sessionStorage.setItem(STORAGE_KEY, key);
  } catch {
    // Storage blocked: the key just won't survive a reload.
  }
  listeners.forEach((notify) => {
    notify();
  });
}

function subscribe(notify: () => void): () => void {
  listeners.add(notify);
  return () => listeners.delete(notify);
}

export function useApiKey(): string | null {
  return useSyncExternalStore(subscribe, read, () => null);
}
