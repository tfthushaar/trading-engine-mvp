"use client";
import Link from "next/link";
import { useState } from "react";
import { Plus, RefreshCw, Trash2 } from "lucide-react";
import { DivergingBars, Sparkline } from "@/components/charts";
import { Card, Change, Disclaimer, Empty, ErrorBox, Meter, SignalPill, Skeleton, SourceTag, StarButton, SymbolLink } from "@/components/ui";
import { useApi } from "@/lib/api";
import { ago, pct, price, rate } from "@/lib/format";
import { KEYS, useStored, useWatchlist, type Notification } from "@/lib/store";

function MacroStrip({ data }: { data?: any }) {
  if (!data) return <div className="grid grid-cols-2 gap-2 sm:grid-cols-5 xl:grid-cols-10">{Array.from({ length: 10 }).map((_, i) => <Skeleton key={i} h={52} />)}</div>;
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-5 xl:grid-cols-10">
      {data.macro.map((m: any) => (
        <Link key={m.symbol} href={`/symbol/${encodeURIComponent(m.symbol)}`} className="card flex items-center justify-between gap-2 px-2.5 py-1.5 hover:border-line-2">
          <div className="min-w-0">
            <div className="truncate text-[11px] text-fg-2">{m.label}</div>
            <div className="num text-[13px] font-semibold">{price(m.price)}</div>
            <Change value={m.change_pct} className="text-[11px]" />
          </div>
          <Sparkline values={m.spark} width={44} height={26} />
        </Link>
      ))}
    </div>
  );
}

function Briefing() {
  const { data, error, loading, reload, refreshing } = useApi<any>("/api/insights/briefing", { staleMs: 600_000 });
  return (
    <Card
      className="lg:col-span-5"
      title="Market briefing"
      right={<><SourceTag source={data?.source} note={data?.note} /><button className="btn btn-sm btn-ghost" onClick={() => reload()} title="Refresh">{refreshing ? <RefreshCw size={12} className="spin" /> : <RefreshCw size={12} />}</button></>}
    >
      {loading && <div className="space-y-2"><Skeleton h={18} w="70%" /><Skeleton h={12} /><Skeleton h={12} w="90%" /><Skeleton h={12} w="80%" /></div>}
      <ErrorBox error={error} onRetry={reload} />
      {data && (
        <div className="space-y-2.5">
          <div>
            <h2 className="text-[15px] font-semibold leading-snug">{data.headline}</h2>
            <p className="mt-1 text-[12.5px] leading-relaxed">{data.summary}</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <div className="eyebrow mb-1">Drivers</div>
              <ul className="space-y-1 text-[12px]">{data.drivers?.map((d: string, i: number) => <li key={i} className="flex gap-1.5"><span className="faint">{i + 1}</span><span>{d}</span></li>)}</ul>
            </div>
            <div>
              <div className="eyebrow mb-1">Watch next</div>
              <ul className="space-y-1 text-[12px]">{data.watch?.map((d: string, i: number) => <li key={i} className="flex gap-1.5"><span className="faint">{i + 1}</span><span>{d}</span></li>)}</ul>
            </div>
          </div>
          <div className="rounded-lg bg-bg-2 px-2.5 py-2 text-[12px]">
            <span className="eyebrow mr-1.5">Neural view</span>
            {data.model_view}
          </div>
          {data.risks?.length > 0 && <div className="text-[12px]"><span className="eyebrow mr-1.5">Risks</span>{data.risks.join(" ")}</div>}
          <div className="faint flex flex-wrap items-center justify-between gap-2 text-[11px]">
            <span>Regime: {data.regime?.label?.replace(/_/g, " ")} · as of {data.as_of}</span>
            <span>Updated {ago(data.generated_at)}</span>
          </div>
        </div>
      )}
    </Card>
  );
}

function NeuralBreadth() {
  const { data, error, reload } = useApi<any>("/api/signals/scan", { staleMs: 120_000 });
  const total = data ? data.rows.length : 0;
  return (
    <Card className="lg:col-span-3" title="Neural ensemble" right={<Link href="/signals" className="btn btn-sm btn-ghost">All signals</Link>}>
      <ErrorBox error={error} onRetry={reload} />
      {!data && !error && <div className="space-y-2"><Skeleton h={28} /><Skeleton h={120} /></div>}
      {data && (
        <div className="space-y-3">
          <div>
            <div className="mb-1 flex justify-between text-[11px]"><span className="muted">5-day outlook across {total} symbols</span><span className="faint">{data.as_of}</span></div>
            <div className="flex h-5 overflow-hidden rounded-md border border-line">
              <div className="flex items-center justify-center bg-inv text-[10.5px] font-semibold text-inv-fg" style={{ width: `${(data.breadth.bullish / total) * 100}%` }}>{data.breadth.bullish}</div>
              <div className="flex items-center justify-center bg-bg-3 text-[10.5px] text-fg-2" style={{ width: `${(data.breadth.neutral / total) * 100}%` }}>{data.breadth.neutral}</div>
              <div className="flex items-center justify-center text-[10.5px] text-fg-2" style={{ width: `${(data.breadth.bearish / total) * 100}%` }}>{data.breadth.bearish}</div>
            </div>
            <div className="faint mt-1 flex justify-between text-[10.5px]"><span>Bullish (top 2 deciles)</span><span>Neutral</span><span>Bearish</span></div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[12px]">
            <div className="rounded-lg bg-bg-2 p-2"><div className="eyebrow">Mean P(up)</div><div className="num text-[15px] font-semibold">{data.breadth.mean_prob_up.toFixed(3)}</div><div className="faint text-[10.5px]">base rate {rate(data.breadth.base_rate)}</div></div>
            <div className="rounded-lg bg-bg-2 p-2"><div className="eyebrow">Members</div><div className="text-[12px] font-medium leading-tight">{data.model.members.join(", ")}</div></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {[{ t: "Most bullish", rows: data.rows.slice(0, 5) }, { t: "Least bullish", rows: data.rows.slice(-5).reverse() }].map((g) => (
              <div key={g.t}>
                <div className="eyebrow mb-1">{g.t}</div>
                {g.rows.map((r: any) => (
                  <div key={r.symbol} className="flex items-center justify-between py-0.5 text-[12px]"><SymbolLink symbol={r.symbol} /><span className="num">{r.prob_up.toFixed(3)}</span></div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function Sectors({ data }: { data?: any }) {
  return (
    <Card className="lg:col-span-4" title="Sectors" right={<Link href="/markets" className="btn btn-sm btn-ghost">Heatmap</Link>}>
      {!data ? <Skeleton h={220} /> : (
        <DivergingBars labelWidth={120} format={(v) => pct(v)} rows={data.sectors.map((s: any) => ({ key: s.symbol, label: <Link href={`/symbol/${s.symbol}`} className="hover:underline">{s.label} <span className="faint">{s.symbol}</span></Link>, value: s.change_pct }))} />
      )}
      {data?.regime && (
        <div className="mt-3 rounded-lg bg-bg-2 px-2.5 py-2 text-[12px]">
          <span className="eyebrow mr-1.5">Regime</span>
          <b className="capitalize">{data.regime.label.replace(/_/g, " ")}</b> <span className="muted">{data.regime.description}</span>
          <div className="faint num mt-1 text-[11px]">SPY vs 200d {pct((data.regime.spy_vs_sma200 ?? 0) * 100)} · 20d {pct((data.regime.spy_return_20d ?? 0) * 100)} · VIX {data.regime.vix}</div>
        </div>
      )}
    </Card>
  );
}

function Movers({ data }: { data?: any }) {
  const Table = ({ rows, title }: { rows: any[]; title: string }) => (
    <div className="min-w-0">
      <div className="eyebrow px-2.5 pb-1">{title}</div>
      <table className="tbl">
        <tbody>
          {rows.map((m: any) => (
            <tr key={m.symbol}>
              <td><SymbolLink symbol={m.symbol} /></td>
              <td className="r">{price(m.price)}</td>
              <td className="r"><Change value={m.change_pct} /></td>
              <td className="r faint">{m.volume_ratio ? `${m.volume_ratio.toFixed(1)}x vol` : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
  return (
    <Card className="lg:col-span-5" title="Movers" bodyClass="py-2 grid grid-cols-1 gap-2 sm:grid-cols-2" right={data && <span className="faint text-[11px]">{data.breadth.advancing} up / {data.breadth.declining} down</span>}>
      {!data ? <Skeleton h={180} /> : <><Table rows={data.gainers} title="Gainers" /><Table rows={data.losers} title="Decliners" /></>}
    </Card>
  );
}

function WatchlistPanel() {
  const wl = useWatchlist();
  const [adding, setAdding] = useState("");
  const syms = wl.list.join(",");
  const { data: quotes } = useApi<any>(syms ? `/api/market/quotes?symbols=${encodeURIComponent(syms)}` : null, { refreshMs: 60_000 });
  const { data: sig } = useApi<any>(syms ? `/api/signals/scan?symbols=${encodeURIComponent(syms)}` : null, { staleMs: 120_000 });
  const bySym: Record<string, any> = Object.fromEntries((sig?.rows ?? []).map((r: any) => [r.symbol, r]));
  return (
    <Card
      className="lg:col-span-4"
      title={
        <select className="select h-6 w-auto border-0 bg-transparent px-0 font-semibold" value={wl.active} onChange={(e) => (e.target.value === "__new" ? wl.create(prompt("New watchlist name") || "New list") : wl.setActive(e.target.value))}>
          {wl.names.map((n) => <option key={n} value={n}>{n}</option>)}
          <option value="__new">New watchlist...</option>
        </select>
      }
      right={
        <form className="flex gap-1" onSubmit={(e) => { e.preventDefault(); if (adding.trim()) wl.toggle(adding.trim()); setAdding(""); }}>
          <input className="input h-6 w-24 text-[12px]" placeholder="Add symbol" value={adding} onChange={(e) => setAdding(e.target.value.toUpperCase())} />
          <button className="btn btn-sm" title="Add"><Plus size={12} /></button>
          {wl.names.length > 1 && <button type="button" className="btn btn-sm btn-ghost" title="Delete this watchlist" onClick={() => confirm(`Delete ${wl.active}?`) && wl.remove(wl.active)}><Trash2 size={12} /></button>}
        </form>
      }
      bodyClass="p-0"
    >
      {wl.list.length === 0 ? <Empty title="Empty watchlist">Add symbols here or with the star on any symbol page.</Empty> : (
        <table className="tbl">
          <thead><tr><th>Symbol</th><th className="r">Price</th><th className="r">Day</th><th className="r">P(up 5d)</th><th>Signal</th><th /></tr></thead>
          <tbody>
            {wl.list.map((s) => {
              const q = quotes?.[s];
              const r = bySym[s];
              return (
                <tr key={s}>
                  <td><SymbolLink symbol={s} /></td>
                  <td className="r">{price(q?.price)}</td>
                  <td className="r"><Change value={q?.change_pct} /></td>
                  <td className="r num">{r ? r.prob_up.toFixed(3) : "--"}</td>
                  <td><SignalPill signal={r?.signal} /></td>
                  <td className="w-6"><StarButton symbol={s} size={12} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </Card>
  );
}

function AlertFeed() {
  const [items, setItems] = useStored<Notification[]>(KEYS.notifications, []);
  return (
    <Card className="lg:col-span-3" title="Watchlist alerts" right={items.some((n) => !n.read) && <button className="btn btn-sm btn-ghost" onClick={() => setItems(items.map((n) => ({ ...n, read: true })))}>Mark read</button>} bodyClass="p-0">
      {items.length === 0 ? (
        <Empty title="No alerts yet">Watchlists are scanned every few minutes for volume spikes, breakouts, large moves, RSI extremes, options flow and neural extremes.</Empty>
      ) : (
        <div className="max-h-[300px] overflow-y-auto">
          {items.slice(0, 20).map((n) => (
            <Link key={n.id} href={`/symbol/${n.symbol}`} className="block border-b border-line px-3 py-1.5 hover:bg-bg-2">
              <div className="flex items-center justify-between gap-2 text-[12px]">
                <span className="flex items-center gap-1.5 font-semibold">{!n.read && <span className="h-1.5 w-1.5 rounded-full bg-fg" />}{n.title}</span>
                <span className={`pill ${n.severity === "high" ? "pill-solid" : n.severity === "medium" ? "pill-outline" : "pill-soft"}`}>{n.severity}</span>
              </div>
              <p className="muted text-[11.5px] leading-snug">{n.narration}</p>
            </Link>
          ))}
        </div>
      )}
    </Card>
  );
}

export default function OverviewPage() {
  const { data, error, reload } = useApi<any>("/api/market/overview", { refreshMs: 60_000 });
  return (
    <div className="space-y-3">
      <ErrorBox error={error} onRetry={reload} />
      <MacroStrip data={data} />
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
        <Briefing />
        <NeuralBreadth />
        <Sectors data={data} />
        <Movers data={data} />
        <WatchlistPanel />
        <AlertFeed />
      </div>
      <Disclaimer />
    </div>
  );
}
