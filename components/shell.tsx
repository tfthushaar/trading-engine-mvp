"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Bell, Moon, Search, Settings, Sun, Monitor, X, CornerDownLeft } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, useApi } from "@/lib/api";
import { ago } from "@/lib/format";
import { getStored, KEYS, pushRecent, useStored, useWatchlist, write, type Notification, type Theme } from "@/lib/store";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/markets", label: "Markets" },
  { href: "/signals", label: "Signals" },
  { href: "/lab", label: "Lab" },
  { href: "/strategies", label: "Strategies" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/journal", label: "Journal" },
  { href: "/analyst", label: "Analyst" },
  { href: "/learn", label: "Learn" },
];

export function ThemeSync() {
  const [theme] = useStored<Theme>(KEYS.theme, "system");
  useEffect(() => {
    const apply = () => {
      const dark = theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
      document.documentElement.dataset.theme = dark ? "dark" : "light";
      window.dispatchEvent(new Event("te-theme"));
    };
    apply();
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, [theme]);
  return null;
}

export function useResolvedTheme() {
  const [t, setT] = useState("light");
  useEffect(() => {
    const read = () => setT(document.documentElement.dataset.theme || "light");
    read();
    window.addEventListener("te-theme", read);
    return () => window.removeEventListener("te-theme", read);
  }, []);
  return t;
}

function ThemeButton() {
  const [theme, setTheme] = useStored<Theme>(KEYS.theme, "system");
  const next: Record<Theme, Theme> = { system: "light", light: "dark", dark: "system" };
  const Icon = theme === "light" ? Sun : theme === "dark" ? Moon : Monitor;
  return (
    <button className="btn-ghost inline-flex h-7 w-7 items-center justify-center rounded-md" title={`Theme: ${theme}`} onClick={() => setTheme(next[theme])}>
      <Icon size={15} />
    </button>
  );
}

/* ---- Notifications: poll watchlist alerts, keep a local inbox ----------------------------- */
function useAlertPoller() {
  const wl = useWatchlist();
  const symbols = wl.all.slice(0, 30).join(",");
  useEffect(() => {
    if (!symbols) return;
    let stop = false;
    const poll = async () => {
      if (document.visibilityState !== "visible") return;
      try {
        const res = await api<{ alerts: any[] }>(`/api/alerts?symbols=${encodeURIComponent(symbols)}&narrate=1`);
        if (stop) return;
        const inbox = getStored<Notification[]>(KEYS.notifications, []);
        const seen = new Set(inbox.map((n) => n.id));
        const fresh = res.alerts.filter((a) => !seen.has(a.id)).map((a) => ({ ...a, narration: a.narration || a.detail, received: Date.now(), read: false }));
        if (fresh.length) write(KEYS.notifications, [...fresh, ...inbox].slice(0, 150));
      } catch {
        /* offline or rate limited: try next cycle */
      }
    };
    const first = setTimeout(poll, 2500);
    const id = setInterval(poll, 180_000);
    return () => {
      stop = true;
      clearTimeout(first);
      clearInterval(id);
    };
  }, [symbols]);
}

function NotificationBell() {
  const [items, setItems] = useStored<Notification[]>(KEYS.notifications, []);
  const [open, setOpen] = useState(false);
  const unread = items.filter((n) => !n.read).length;
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => box.current && !box.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  return (
    <div className="relative" ref={box}>
      <button className="btn-ghost relative inline-flex h-7 w-7 items-center justify-center rounded-md" title="Alerts" onClick={() => setOpen((o) => !o)}>
        <Bell size={15} />
        {unread > 0 && <span className="num absolute -right-0.5 -top-0.5 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-inv px-1 text-[9px] font-semibold text-inv-fg">{unread > 99 ? "99" : unread}</span>}
      </button>
      {open && (
        <div className="card absolute right-0 top-9 z-50 w-[360px] max-w-[92vw] shadow-xl">
          <div className="card-head">
            <span className="card-title">Alerts</span>
            <div className="flex gap-1">
              <button className="btn btn-sm btn-ghost" onClick={() => setItems(items.map((n) => ({ ...n, read: true })))}>Mark all read</button>
              <button className="btn btn-sm btn-ghost" onClick={() => setItems([])}>Clear</button>
            </div>
          </div>
          <div className="max-h-[420px] overflow-y-auto">
            {items.length === 0 ? (
              <div className="muted px-3 py-6 text-center text-[12px]">No alerts yet. Alerts come from symbols in your watchlists: volume spikes, 52-week breakouts, large moves, RSI extremes, options flow and neural-model extremes.</div>
            ) : (
              items.slice(0, 60).map((n) => (
                <Link key={n.id} href={`/symbol/${n.symbol}`} onClick={() => { setItems(items.map((x) => (x.id === n.id ? { ...x, read: true } : x))); setOpen(false); }} className="block border-b border-line px-3 py-2 hover:bg-bg-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5 text-[12px] font-semibold">
                      {!n.read && <span className="h-1.5 w-1.5 rounded-full bg-fg" />}
                      {n.title}
                    </span>
                    <span className={`pill ${n.severity === "high" ? "pill-solid" : n.severity === "medium" ? "pill-outline" : "pill-soft"}`}>{n.severity}</span>
                  </div>
                  <p className="muted mt-0.5 text-[11.5px] leading-snug">{n.narration}</p>
                  <p className="faint mt-0.5 text-[10.5px]">{n.type.replace(/_/g, " ")} · {ago(new Date(n.received).toISOString())}</p>
                </Link>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ---- Command palette ------------------------------------------------------------------------ */
const PAGES = [
  ...NAV,
  { href: "/lab?tab=arena", label: "Arena: compare architectures" },
  { href: "/lab?tab=model", label: "Model card" },
  { href: "/strategies?tab=builder", label: "Rule builder and backtest" },
  { href: "/strategies?tab=evaluator", label: "Trade evaluator" },
  { href: "/settings", label: "Settings" },
];

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [sel, setSel] = useState(0);
  const recent = getStored<string[]>(KEYS.recent, []);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(q.trim()), 180);
    return () => clearTimeout(id);
  }, [q]);
  useEffect(() => {
    if (open) {
      setQ("");
      setSel(0);
    }
  }, [open]);
  const { data, loading } = useApi<any[]>(open && debounced ? `/api/market/search?q=${encodeURIComponent(debounced)}` : null, { staleMs: 3600_000 });
  const items = useMemo(() => {
    const out: { label: string; sub?: string; href: string }[] = [];
    const ql = q.trim().toLowerCase();
    if (ql && /^[a-z0-9.^=\-]{1,10}$/i.test(q.trim())) out.push({ label: q.trim().toUpperCase(), sub: "Open symbol", href: `/symbol/${encodeURIComponent(q.trim().toUpperCase())}` });
    for (const r of data ?? []) if (!out.some((o) => o.label === r.symbol)) out.push({ label: r.symbol, sub: `${r.name} · ${r.exchange ?? ""} · ${r.type ?? ""}`, href: `/symbol/${encodeURIComponent(r.symbol)}` });
    if (!ql) for (const s of recent) out.push({ label: s, sub: "Recent", href: `/symbol/${s}` });
    for (const p of PAGES) if (!ql || p.label.toLowerCase().includes(ql)) out.push({ label: p.label, sub: "Go to page", href: p.href });
    return out.slice(0, 12);
  }, [data, q, recent]);
  const go = useCallback(
    (href: string) => {
      const m = /^\/symbol\/(.+)$/.exec(href);
      if (m) pushRecent(decodeURIComponent(m[1]));
      onClose();
      router.push(href);
    },
    [onClose, router],
  );
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center bg-black/30 px-3 pt-[12vh]" onMouseDown={onClose}>
      <div className="card w-full max-w-[560px] overflow-hidden shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 border-b border-line px-3">
          <Search size={15} className="faint" />
          <input
            autoFocus
            className="h-11 flex-1 bg-transparent text-[14px] outline-none"
            placeholder="Search symbols, companies or pages"
            value={q}
            onChange={(e) => (setQ(e.target.value), setSel(0))}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") (e.preventDefault(), setSel((s) => Math.min(items.length - 1, s + 1)));
              if (e.key === "ArrowUp") (e.preventDefault(), setSel((s) => Math.max(0, s - 1)));
              if (e.key === "Enter" && items[sel]) go(items[sel].href);
              if (e.key === "Escape") onClose();
            }}
          />
          {loading && <span className="faint text-[11px]">Searching</span>}
          <button className="btn-ghost rounded p-1" onClick={onClose}><X size={14} /></button>
        </div>
        <div className="max-h-[52vh] overflow-y-auto py-1">
          {items.map((it, i) => (
            <button key={`${it.href}${i}`} onMouseEnter={() => setSel(i)} onClick={() => go(it.href)} className={`flex w-full items-center justify-between gap-3 px-3 py-1.5 text-left ${i === sel ? "bg-bg-2" : ""}`}>
              <span className="min-w-0">
                <span className="font-medium">{it.label}</span>
                {it.sub && <span className="faint ml-2 truncate text-[11.5px]">{it.sub}</span>}
              </span>
              {i === sel && <CornerDownLeft size={12} className="faint shrink-0" />}
            </button>
          ))}
          {!items.length && <div className="muted px-3 py-4 text-[12px]">No matches.</div>}
        </div>
      </div>
    </div>
  );
}

export function TopBar() {
  const path = usePathname();
  const [palette, setPalette] = useState(false);
  const { data: status } = useApi<any>("/api/status", { staleMs: 300_000 });
  useAlertPoller();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(tag))) {
        e.preventDefault();
        setPalette(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const active = (href: string) => (href === "/" ? path === "/" : path?.startsWith(href));
  return (
    <>
      <header className="sticky top-0 z-40 border-b border-line bg-bg/85 backdrop-blur-xl">
        <div className="mx-auto flex h-11 max-w-[1920px] items-center gap-3 px-3 sm:px-4">
          <Link href="/" className="shrink-0 text-[13px] font-semibold tracking-tight" title="Trading Engine">
            Trading Engine
          </Link>
          <nav className="-mx-1 flex min-w-0 flex-1 items-center gap-0.5 overflow-x-auto">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} className={`shrink-0 rounded-md px-2 py-1 text-[12.5px] ${active(n.href) ? "bg-bg-2 font-semibold text-fg" : "text-fg-2 hover:text-fg"}`}>
                {n.label}
              </Link>
            ))}
          </nav>
          <button onClick={() => setPalette(true)} className="hidden h-7 w-56 shrink-0 items-center gap-2 rounded-md border border-line bg-bg-2 px-2 text-[12px] text-fg-3 hover:border-line-2 lg:flex">
            <Search size={13} />
            <span className="flex-1 text-left">Search symbols</span>
            <kbd className="rounded border border-line-2 px-1 text-[10px]">Ctrl K</kbd>
          </button>
          <button onClick={() => setPalette(true)} className="btn-ghost inline-flex h-7 w-7 items-center justify-center rounded-md lg:hidden" title="Search"><Search size={15} /></button>
          <div className="flex shrink-0 items-center gap-0.5">
            <span className="hidden items-center gap-1.5 px-1 text-[11px] text-fg-3 xl:inline-flex" title={status?.neural_model?.available ? `Neural ensemble ${status.neural_model.version}` : "Model unavailable"}>
              <span className={`h-1.5 w-1.5 rounded-full ${status?.neural_model?.available ? "bg-fg" : "bg-fg-4"}`} />
              {status?.llm?.provider_label ? `AI: ${status.llm.provider_label}` : "AI: data only"}
            </span>
            <NotificationBell />
            <ThemeButton />
            <Link href="/settings" className="btn-ghost inline-flex h-7 w-7 items-center justify-center rounded-md" title="Settings"><Settings size={15} /></Link>
          </div>
        </div>
      </header>
      <CommandPalette open={palette} onClose={() => setPalette(false)} />
    </>
  );
}
