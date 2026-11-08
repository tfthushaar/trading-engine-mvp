"use client";
import { useSyncExternalStore } from "react";

/* Tiny persistent stores on localStorage with cross-component (and cross-tab) subscriptions.
   Everything here stays in the visitor's browser: there are no accounts. */

type Listener = () => void;
const listeners = new Map<string, Set<Listener>>();
const memory = new Map<string, unknown>();

function read<T>(key: string, fallback: T): T {
  if (memory.has(key)) return memory.get(key) as T;
  let value = fallback;
  try {
    const raw = typeof window !== "undefined" ? window.localStorage.getItem(key) : null;
    if (raw != null) value = JSON.parse(raw) as T;
  } catch {
    /* storage unavailable or corrupt: use the fallback */
  }
  memory.set(key, value);
  return value;
}

export function write<T>(key: string, value: T) {
  memory.set(key, value);
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* private mode / quota: keep the in-memory value */
  }
  listeners.get(key)?.forEach((l) => l());
}

if (typeof window !== "undefined") {
  window.addEventListener("storage", (e) => {
    if (!e.key || !listeners.has(e.key)) return;
    memory.delete(e.key);
    listeners.get(e.key)?.forEach((l) => l());
  });
}

export function useStored<T>(key: string, fallback: T): [T, (v: T | ((prev: T) => T)) => void] {
  const value = useSyncExternalStore(
    (cb) => {
      if (!listeners.has(key)) listeners.set(key, new Set());
      listeners.get(key)!.add(cb);
      return () => listeners.get(key)!.delete(cb);
    },
    () => read(key, fallback),
    () => fallback,
  );
  const set = (v: T | ((prev: T) => T)) => {
    const next = typeof v === "function" ? (v as (p: T) => T)(read(key, fallback)) : v;
    write(key, next);
  };
  return [value, set];
}

export function getStored<T>(key: string, fallback: T): T {
  return read(key, fallback);
}

/* ---- Keys and shapes ---------------------------------------------------------------------- */
export type Theme = "system" | "light" | "dark";
export interface LLMSettings {
  mode: "shared" | "own";
  provider: "groq" | "gemini" | "anthropic";
  key: string;
  model: string;
}
export interface Prefs {
  chartRange: string;
  chartInterval: string | null;
  chartType: "candles" | "line" | "area";
  indicators: string[];
}

export const KEYS = {
  theme: "te.theme",
  llm: "te.llm",
  watchlists: "te.watchlists",
  prefs: "te.prefs",
  experiments: "te.experiments",
  chats: "te.chats",
  recent: "te.recent",
  notifications: "te.notifications",
  portfolio: "te.portfolio",
  journal: "te.journal",
  learn: "te.learn",
} as const;

export const DEFAULT_LLM: LLMSettings = { mode: "shared", provider: "groq", key: "", model: "" };
export const DEFAULT_PREFS: Prefs = { chartRange: "6mo", chartInterval: null, chartType: "candles", indicators: ["sma50", "volume", "model"] };

export interface Watchlists {
  active: string;
  lists: Record<string, string[]>;
}
export const DEFAULT_WATCHLISTS: Watchlists = {
  active: "Core",
  lists: { Core: ["SPY", "QQQ", "AAPL", "NVDA", "MSFT", "AMZN"], "Mega tech": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "AVGO", "TSLA"] },
};

export function useWatchlist() {
  const [wl, setWl] = useStored<Watchlists>(KEYS.watchlists, DEFAULT_WATCHLISTS);
  const active = wl.lists[wl.active] ? wl.active : Object.keys(wl.lists)[0] ?? "Core";
  const list = wl.lists[active] ?? [];
  const update = (fn: (w: Watchlists) => Watchlists) => setWl((prev) => fn({ active: prev.active, lists: { ...prev.lists } }));
  return {
    active,
    names: Object.keys(wl.lists),
    list,
    all: Array.from(new Set(Object.values(wl.lists).flat())),
    has: (s: string) => list.includes(s.toUpperCase()),
    toggle: (s: string) => {
      const u = s.toUpperCase();
      update((w) => {
        const cur = w.lists[active] ?? [];
        w.lists[active] = cur.includes(u) ? cur.filter((x) => x !== u) : [...cur, u].slice(0, 40);
        return w;
      });
    },
    add: (s: string) => {
      const u = s.trim().toUpperCase();
      if (!u) return;
      update((w) => {
        const cur = w.lists[active] ?? [];
        if (!cur.includes(u)) w.lists[active] = [...cur, u].slice(0, 40);
        return w;
      });
    },
    setActive: (name: string) => update((w) => ({ ...w, active: name })),
    create: (name: string, symbols: string[] = []) =>
      update((w) => {
        const n = name.trim().slice(0, 30) || "Untitled";
        if (!w.lists[n]) w.lists[n] = Array.from(new Set(symbols.map((s) => s.toUpperCase()))).slice(0, 40); // never overwrite a list
        return { ...w, active: n };
      }),
    remove: (name: string) =>
      update((w) => {
        delete w.lists[name];
        if (!Object.keys(w.lists).length) w.lists.Core = [];
        return { ...w, active: Object.keys(w.lists)[0] };
      }),
    setList: (symbols: string[]) =>
      update((w) => {
        w.lists[active] = symbols;
        return w;
      }),
  };
}

export interface Notification {
  id: string;
  symbol: string;
  type: string;
  severity: "high" | "medium" | "low";
  title: string;
  narration: string;
  date: string;
  received: number;
  read: boolean;
}

export function pushRecent(symbol: string) {
  const u = symbol.toUpperCase();
  const prev = read<string[]>(KEYS.recent, []);
  write(KEYS.recent, [u, ...prev.filter((x) => x !== u)].slice(0, 8));
}
