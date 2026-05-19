"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Activity, TrendingUp, TrendingDown, Zap, AlertCircle } from "lucide-react";
import { useRouter } from "next/navigation";

export default function DashboardPage() {
  const router = useRouter();

  const { data: briefing, isLoading: briefingLoading } = useQuery({
    queryKey: ["daily-briefing"],
    queryFn: () => api.get("/api/intelligence/briefing/daily").then(r => r.data),
    staleTime: 4 * 60 * 60 * 1000,
  });

  const { data: macro } = useQuery({
    queryKey: ["macro"],
    queryFn: () => api.get("/api/market/macro").then(r => r.data),
    refetchInterval: 60_000,
  });

  const { data: movers } = useQuery({
    queryKey: ["movers"],
    queryFn: () => api.get("/api/market/movers").then(r => r.data),
    refetchInterval: 60_000,
  });

  const { data: sectors } = useQuery({
    queryKey: ["sector-heatmap"],
    queryFn: () => api.get("/api/market/sector-heatmap").then(r => r.data),
    refetchInterval: 120_000,
  });

  const { data: alerts } = useQuery({
    queryKey: ["watchlist-alerts"],
    queryFn: () => api.get("/api/intelligence/watchlist-alerts").then(r => r.data),
    refetchInterval: 60_000,
  });

  const macroItems = macro ? Object.entries(macro) : [];

  return (
    <div className="max-w-[1400px] mx-auto px-4 py-8 space-y-6 fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="section-title">Market Dashboard</h1>
          <p className="section-subtitle">{new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}</p>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="live-dot" />
          <span className="text-xs text-[#888]">Live</span>
        </div>
      </div>

      {/* Macro bar */}
      <div className="overflow-x-auto">
        <div className="flex gap-2 pb-1 min-w-max">
          {macroItems.length > 0 ? macroItems.map(([label, item]: any) => (
            <div key={label} className="card-sm flex items-center gap-3 whitespace-nowrap shrink-0">
              <span className="text-xs text-[#888] font-medium">{label}</span>
              {item.price != null && (
                <>
                  <span className="text-sm font-semibold tabular-nums">{item.price}</span>
                  <span className={`text-xs tabular-nums ${item.change_pct >= 0 ? "positive" : "negative"}`}>
                    {item.change_pct >= 0 ? "+" : ""}{item.change_pct}%
                  </span>
                </>
              )}
            </div>
          )) : Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton h-12 w-36 rounded-xl" />)}
        </div>
      </div>

      {/* Briefing + Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 card space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2"><Zap size={14} /><span className="label">AI Market Briefing</span></div>
            <span className="text-xs text-[#555]">{briefing?.date || "Today"}</span>
          </div>
          {briefingLoading ? (
            <div className="space-y-2">{[100,83,66].map(w => <div key={w} className={`skeleton h-3 rounded`} style={{width:`${w}%`}} />)}</div>
          ) : briefing ? (
            <>
              <p className="text-sm text-[#c0c0c0] leading-relaxed">{briefing.briefing?.slice(0,500)}</p>
              {briefing.top_catalysts?.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-[#1e1e1e]">
                  <p className="label">Top Catalysts</p>
                  {briefing.top_catalysts.slice(0,3).map((c: string, i: number) => (
                    <div key={i} className="flex gap-2 text-xs text-[#999]"><span className="text-white font-bold">{i+1}.</span><span>{c}</span></div>
                  ))}
                </div>
              )}
              <p className="text-[10px] text-[#3a3a3a] leading-relaxed">{briefing.disclaimer}</p>
            </>
          ) : <p className="text-sm text-[#555]">Add your Anthropic API key in Settings to enable AI briefings.</p>}
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2"><AlertCircle size={14} /><span className="label">Watchlist Alerts</span></div>
            {(alerts?.alert_count ?? 0) > 0 && <span className="text-xs bg-white text-black px-2 py-0.5 rounded-full font-semibold">{alerts.alert_count}</span>}
          </div>
          <div className="space-y-2">
            {alerts?.alerts?.slice(0,4).map((a: any, i: number) => (
              <div key={i} className={`rounded-xl p-3 ${a.severity === "high" ? "alert-high" : a.severity === "medium" ? "alert-medium" : "alert-low"}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold">{a.ticker}</span>
                  <span className="text-[10px] text-[#666]">{a.type?.replace(/_/g," ")}</span>
                </div>
                <p className="text-xs text-[#aaa]">{a.narration}</p>
              </div>
            )) || <p className="text-xs text-[#555]">No alerts. Add tickers to a watchlist to monitor them.</p>}
          </div>
        </div>
      </div>

      {/* Sectors + Movers */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 card">
          <div className="flex items-center gap-2 mb-4"><Activity size={14} /><span className="label">Sector Performance</span></div>
          <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
            {sectors ? sectors.map((s: any) => {
              const pct = s.change_pct ?? 0;
              const alpha = Math.min(Math.abs(pct)/3, 1);
              const bg = pct >= 0 ? `rgba(34,197,94,${0.06+alpha*0.2})` : `rgba(239,68,68,${0.06+alpha*0.2})`;
              const bd = pct >= 0 ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)";
              return (
                <div key={s.sector} className="rounded-xl p-3 text-center" style={{background:bg,border:`1px solid ${bd}`}}>
                  <div className="text-xs text-[#aaa] truncate mb-1">{s.sector}</div>
                  <div className={`text-sm font-bold tabular-nums ${pct >= 0 ? "positive" : "negative"}`}>{pct>=0?"+":""}{pct?.toFixed(2)}%</div>
                </div>
              );
            }) : Array.from({length:8}).map((_,i) => <div key={i} className="skeleton h-16 rounded-xl" />)}
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-2 mb-4"><TrendingUp size={14} /><span className="label">Movers</span></div>
          <div className="space-y-4">
            <div>
              <p className="text-[10px] text-green-700 font-semibold uppercase tracking-widest mb-2">Top Gainers</p>
              <div className="space-y-1.5">
                {movers?.gainers?.map((m: any) => (
                  <div key={m.ticker} onClick={() => router.push(`/ticker/${m.ticker}`)} className="flex items-center justify-between cursor-pointer hover:bg-[#1a1a1a] rounded-lg px-2 py-1 -mx-2 transition-colors">
                    <span className="text-sm font-medium">{m.ticker}</span>
                    <span className="positive text-sm font-semibold tabular-nums">+{m.change_pct?.toFixed(2)}%</span>
                  </div>
                )) ?? <div className="skeleton h-3 w-full rounded" />}
              </div>
            </div>
            <div className="divider" />
            <div>
              <p className="text-[10px] text-red-700 font-semibold uppercase tracking-widest mb-2">Top Losers</p>
              <div className="space-y-1.5">
                {movers?.losers?.map((m: any) => (
                  <div key={m.ticker} onClick={() => router.push(`/ticker/${m.ticker}`)} className="flex items-center justify-between cursor-pointer hover:bg-[#1a1a1a] rounded-lg px-2 py-1 -mx-2 transition-colors">
                    <span className="text-sm font-medium">{m.ticker}</span>
                    <span className="negative text-sm font-semibold tabular-nums">{m.change_pct?.toFixed(2)}%</span>
                  </div>
                )) ?? <div className="skeleton h-3 w-full rounded" />}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
