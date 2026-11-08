"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { DEFAULT_LLM, getStored, KEYS, type LLMSettings } from "./store";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function llmHeaders(): Record<string, string> {
  const s = getStored<LLMSettings>(KEYS.llm, DEFAULT_LLM);
  // Header values must be printable ASCII, or fetch throws and every request on the site fails
  if (s.mode !== "own" || !/^[\x21-\x7e]+$/.test(s.key)) return {};
  const h: Record<string, string> = { "X-LLM-Provider": s.provider, "X-LLM-Key": s.key };
  if (/^[\x21-\x7e]+$/.test(s.model)) h["X-LLM-Model"] = s.model;
  return h;
}

export async function api<T = any>(path: string, init?: { method?: string; body?: unknown; signal?: AbortSignal }): Promise<T> {
  const res = await fetch(path, {
    method: init?.method ?? (init?.body ? "POST" : "GET"),
    headers: { "Content-Type": "application/json", ...llmHeaders() },
    body: init?.body ? JSON.stringify(init.body) : undefined,
    signal: init?.signal,
  });
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) throw new ApiError(data?.detail || `Request failed (${res.status})`, res.status);
  return data as T;
}

/* ---- Cached GET hook: one request per key, shared by every component that reads it ------- */
type Entry = { data?: any; error?: ApiError; at: number; promise?: Promise<any> };
const cache = new Map<string, Entry>();
const subscribers = new Map<string, Set<() => void>>();
const MAX_ENTRIES = 200;

function notify(path: string) {
  subscribers.get(path)?.forEach((fn) => fn());
}

function request(path: string, staleMs: number, force = false) {
  const e = cache.get(path);
  if (e?.promise) return; // never run two requests for one key: the older could overwrite the newer
  if (!force && e?.data !== undefined && Date.now() - e.at < staleMs) return;
  const promise = api(path)
    .then((data) => cache.set(path, { data, at: Date.now() }))
    .catch((error: ApiError) => cache.set(path, { data: cache.get(path)?.data, error, at: Date.now() }))
    .finally(() => notify(path));
  cache.set(path, { ...(e ?? { at: 0 }), promise });
  if (cache.size > MAX_ENTRIES) {
    const oldest = cache.keys().next().value;
    if (oldest && oldest !== path && !subscribers.get(oldest)?.size) cache.delete(oldest);
  }
  notify(path);
}

export function useApi<T = any>(path: string | null, opts?: { refreshMs?: number; staleMs?: number }) {
  const staleMs = opts?.staleMs ?? 30_000;
  const refreshMs = opts?.refreshMs;
  const [, rerender] = useState(0);

  useEffect(() => {
    if (!path) return;
    const update = () => rerender((x) => x + 1);
    if (!subscribers.has(path)) subscribers.set(path, new Set());
    subscribers.get(path)!.add(update);
    request(path, staleMs);
    const id = refreshMs ? setInterval(() => document.visibilityState === "visible" && request(path, staleMs, true), refreshMs) : undefined;
    return () => {
      subscribers.get(path)?.delete(update);
      if (id) clearInterval(id);
    };
  }, [path, staleMs, refreshMs]);

  const entry = path ? cache.get(path) : undefined;
  return {
    data: entry?.data as T | undefined,
    error: entry?.error,
    loading: !!path && entry?.data === undefined && !entry?.error,
    refreshing: !!entry?.promise,
    reload: () => {
      if (path) request(path, staleMs, true);
    },
  };
}

/* ---- Imperative request with state (for POST actions) ------------------------------------ */
export function useAction<T = any, A = any>(fn: (args: A, signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<{ data?: T; error?: string; running: boolean; startedAt?: number }>({ running: false });
  const ctrl = useRef<AbortController | null>(null);
  const run = useCallback(
    async (args: A) => {
      ctrl.current?.abort();
      const c = new AbortController();
      ctrl.current = c;
      setState((s) => ({ data: s.data, running: true, startedAt: Date.now() }));
      try {
        const data = await fn(args, c.signal);
        if (!c.signal.aborted) setState({ data, running: false });
        return data;
      } catch (e: any) {
        if (!c.signal.aborted) setState((s) => ({ data: s.data, error: e?.message || "Request failed", running: false }));
      }
    },
    [fn],
  );
  return { ...state, run, cancel: () => ctrl.current?.abort(), reset: () => setState({ running: false }) };
}
