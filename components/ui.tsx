"use client";
import Link from "next/link";
import { ArrowDownRight, ArrowUpRight, Info, Loader2, Star } from "lucide-react";
import type { ReactNode } from "react";
import { pct } from "@/lib/format";
import { useWatchlist } from "@/lib/store";

export function Card({ title, right, children, className = "", bodyClass = "card-body", id }: { title?: ReactNode; right?: ReactNode; children: ReactNode; className?: string; bodyClass?: string; id?: string }) {
  return (
    <section id={id} className={`card min-w-0 ${className}`}>
      {(title || right) && (
        <header className="card-head">
          <div className="card-title flex min-w-0 items-center gap-2">{title}</div>
          {right && <div className="flex shrink-0 items-center gap-1.5">{right}</div>}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  );
}

export function PageHeader({ title, subtitle, right }: { title: string; subtitle?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
      <div className="min-w-0">
        <h1 className="text-[17px] font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="muted text-[12px]">{subtitle}</p>}
      </div>
      {right && <div className="flex flex-wrap items-center gap-2">{right}</div>}
    </div>
  );
}

export function Seg<T extends string>({ value, options, onChange, disabled }: { value: T; options: { value: T; label: ReactNode; disabled?: boolean; title?: string }[]; onChange: (v: T) => void; disabled?: boolean }) {
  return (
    <div className="seg" role="tablist">
      {options.map((o) => (
        <button key={o.value} type="button" role="tab" title={o.title} data-on={o.value === value} disabled={disabled || o.disabled} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Field({ label, children, hint, className = "" }: { label: string; children: ReactNode; hint?: string; className?: string }) {
  return (
    <label className={`block min-w-0 ${className}`}>
      <span className="label">{label}</span>
      {children}
      {hint && <span className="faint mt-0.5 block text-[11px]">{hint}</span>}
    </label>
  );
}

export function Stat({ label, value, sub, strong }: { label: string; value: ReactNode; sub?: ReactNode; strong?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="eyebrow truncate">{label}</div>
      <div className={`num truncate text-[17px] leading-6 ${strong ? "font-semibold" : "font-medium"}`}>{value}</div>
      {sub != null && <div className="faint num truncate text-[11px]">{sub}</div>}
    </div>
  );
}

export function Change({ value, digits = 2, icon = true, className = "" }: { value: number | null | undefined; digits?: number; icon?: boolean; className?: string }) {
  if (value == null || !Number.isFinite(value)) return <span className="faint">--</span>;
  const up = value > 0;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={`num inline-flex items-center gap-0.5 ${up ? "font-semibold" : value < 0 ? "muted" : ""} ${className}`}>
      {icon && value !== 0 && <Icon size={12} strokeWidth={2.4} />}
      {pct(value, digits)}
    </span>
  );
}

export function SignalPill({ signal }: { signal?: string | null }) {
  if (!signal) return <span className="faint">--</span>;
  const cls = signal === "bullish" || signal === "bullish_setup" ? "pill-solid" : signal === "bearish" || signal === "bearish_setup" ? "pill-outline" : "pill-soft";
  return <span className={`pill ${cls}`}>{signal.replace("_setup", "").replace("_", " ")}</span>;
}

export function SourceTag({ source, note }: { source?: string; note?: string | null }) {
  if (!source) return null;
  return (
    <span className="faint inline-flex items-center gap-1 text-[11px]" title={note ?? undefined}>
      {source === "ai" ? "AI narrative" : "Data summary"}
      {note && <Info size={11} />}
    </span>
  );
}

export function Spinner({ size = 14 }: { size?: number }) {
  return <Loader2 size={size} className="spin" />;
}

export function Skeleton({ h = 14, w = "100%", className = "" }: { h?: number; w?: number | string; className?: string }) {
  return <div className={`skeleton ${className}`} style={{ height: h, width: w }} />;
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1.5 px-4 py-8 text-center">
      <div className="text-[13px] font-medium">{title}</div>
      {children && <div className="muted max-w-md text-[12px]">{children}</div>}
      {action && <div className="mt-1.5">{action}</div>}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error?: string | { message?: string } | null; onRetry?: () => void }) {
  if (!error) return null;
  const msg = typeof error === "string" ? error : error.message;
  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-line-2 bg-bg-2 px-3 py-2 text-[12px]">
      <span>{msg || "Something went wrong."}</span>
      {onRetry && (
        <button className="btn btn-sm" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function Meter({ value, min = 0, max = 1, marker, height = 6 }: { value: number | null | undefined; min?: number; max?: number; marker?: number | null; height?: number }) {
  const p = value == null ? 0 : Math.max(0, Math.min(1, (value - min) / (max - min)));
  const m = marker == null ? null : Math.max(0, Math.min(1, (marker - min) / (max - min)));
  return (
    <div className="relative w-full overflow-hidden rounded-full bg-bg-3" style={{ height }}>
      <div className="h-full rounded-full bg-fg" style={{ width: `${p * 100}%` }} />
      {m != null && <div className="absolute top-0 h-full w-px bg-fg-3" style={{ left: `${m * 100}%` }} />}
    </div>
  );
}

export function StarButton({ symbol, size = 14 }: { symbol: string; size?: number }) {
  const wl = useWatchlist();
  const on = wl.has(symbol);
  return (
    <button
      className="btn-ghost inline-flex h-6 w-6 items-center justify-center rounded-md"
      title={on ? `Remove ${symbol} from ${wl.active}` : `Add ${symbol} to ${wl.active}`}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        wl.toggle(symbol);
      }}
    >
      <Star size={size} fill={on ? "currentColor" : "none"} strokeWidth={1.8} />
    </button>
  );
}

export function SymbolLink({ symbol, children, className = "" }: { symbol: string; children?: ReactNode; className?: string }) {
  return (
    <Link href={`/symbol/${encodeURIComponent(symbol)}`} className={`font-semibold hover:underline ${className}`}>
      {children ?? symbol}
    </Link>
  );
}

export function Disclaimer({ children }: { children?: ReactNode }) {
  return <p className="faint mt-2 text-[10.5px] leading-snug">{children ?? "Research output from statistical models and public data. Not financial advice."}</p>;
}

/** Minimal, dependency-free markdown renderer for model answers (headings, lists, bold, code, tables, paragraphs). */
export function Markdown({ text }: { text: string }) {
  const lines = (text || "").replace(/\r/g, "").split("\n");
  const out: ReactNode[] = [];
  let i = 0;
  const inline = (s: string, key: string | number): ReactNode => {
    const parts: ReactNode[] = [];
    const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
    let last = 0;
    let m: RegExpExecArray | null;
    let k = 0;
    while ((m = re.exec(s))) {
      if (m.index > last) parts.push(s.slice(last, m.index));
      const t = m[0];
      if (t.startsWith("**")) parts.push(<strong key={k++}>{t.slice(2, -2)}</strong>);
      else if (t.startsWith("`")) parts.push(<code key={k++}>{t.slice(1, -1)}</code>);
      else parts.push(<em key={k++}>{t.slice(1, -1)}</em>);
      last = m.index + t.length;
    }
    if (last < s.length) parts.push(s.slice(last));
    return <span key={key}>{parts}</span>;
  };
  while (i < lines.length) {
    const l = lines[i];
    if (!l.trim()) {
      i++;
      continue;
    }
    const h = /^(#{1,3})\s+(.*)$/.exec(l);
    if (h) {
      const Tag = (`h${h[1].length}` as "h1" | "h2" | "h3");
      out.push(<Tag key={i}>{inline(h[2], i)}</Tag>);
      i++;
      continue;
    }
    if (/^\s*(-{3,}|\*{3,})\s*$/.test(l)) {
      out.push(<hr key={i} />);
      i++;
      continue;
    }
    if (/^\s*\|/.test(l)) {
      const rows: string[][] = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) {
        const cells = lines[i].trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        if (!cells.every((c) => /^:?-{2,}:?$/.test(c))) rows.push(cells);
        i++;
      }
      out.push(
        <table key={`t${i}`}>
          <thead>
            <tr>{rows[0]?.map((c, j) => <th key={j}>{inline(c, j)}</th>)}</tr>
          </thead>
          <tbody>
            {rows.slice(1).map((r, ri) => (
              <tr key={ri}>{r.map((c, j) => <td key={j}>{inline(c, j)}</td>)}</tr>
            ))}
          </tbody>
        </table>,
      );
      continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(l)) {
      const ordered = /^\s*\d+\./.test(l);
      const items: string[] = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*([-*]|\d+\.)\s+/, ""));
        i++;
      }
      const List = ordered ? "ol" : "ul";
      out.push(<List key={`l${i}`}>{items.map((it, j) => <li key={j}>{inline(it, j)}</li>)}</List>);
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,3}\s|\s*([-*]|\d+\.)\s+|\s*\|)/.test(lines[i])) {
      para.push(lines[i]);
      i++;
    }
    out.push(<p key={`p${i}`}>{inline(para.join(" "), i)}</p>);
  }
  return <div className="prose-te">{out}</div>;
}
