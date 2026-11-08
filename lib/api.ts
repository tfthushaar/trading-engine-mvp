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
  if (s.mode !== "own" || !s.key) return {};
  const h: Record<string, string> = { "X-LLM-Provider": s.provider, "X-LLM-Key": s.key };
  if (s.model) h["X-LLM-Model"] = s.model;
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

/* ---- Cached GET hook: dedupes concurrent requests, keeps data while revalidating ---------- */
type Entry = { data?: any; error?: ApiError; at: number; promise?: Promise<any> };
const cache = new Map<string, Entry>();

export function useApi<T = any>(path: string | null, opts?: { refreshMs?: number; staleMs?: number }) {
  const staleMs = opts?.staleMs ?? 30_000;
  const [, force] = useState(0);
  const mounted = useRef(true);
  const entry = path ? cache.get(path) : undefined;

  const load = useCallback(
    async (p: string, forceReload = false) => {
      const e = cache.get(p);
      if (!forceReload && e?.promise) return e.promise;
      if (!forceReload && e?.data !== undefined && Date.now() - e.at < staleMs) return e.data;
      const promise = api<T>(p)
        .then((data) => {
          cache.set(p, { data, at: Date.now() });
          return data;
        })
        .catch((error: ApiError) => {
          cache.set(p, { data: cache.get(p)?.data, error, at: Date.now() });
        })
        .finally(() => mounted.current && force((x) => x + 1));
      cache.set(p, { ...(e ?? { at: 0 }), promise });
      force((x) => x + 1);
      return promise;
    },
    [staleMs],
  );

  useEffect(() => {
    mounted.current = true;
    if (path) load(path);
    if (!path || !opts?.refreshMs) return () => void (mounted.current = false);
    const id = setInterval(() => load(path, true), opts.refreshMs);
    return () => {
      mounted.current = false;
      clearInterval(id);
    };
  }, [path, load, opts?.refreshMs]);

  return {
    data: entry?.data as T | undefined,
    error: entry?.error,
    loading: !!entry?.promise && entry?.data === undefined,
    refreshing: !!entry?.promise,
    reload: () => path && load(path, true),
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
