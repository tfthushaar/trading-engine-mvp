"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState } from "react";
import { BarChart2, Newspaper, FlaskConical, Brain } from "lucide-react";

type Tab = "intelligence" | "chart" | "news" | "evaluate";

export default function TickerPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const ticker = (symbol ?? "").toUpperCase();
  const [tab, setTab] = useState<Tab>("intelligence");
  const [evalForm, setEvalForm] = useState({ entry: "", stop_loss: "", target: "" });
  const [evalResult, setEvalResult] = useState<any>(null);
  const [evalLoading, setEvalLoading] = useState(false);

  const { data: quote } = useQuery({
    queryKey: ["quote", ticker],
    queryFn: () => api.get(`/api/market/quote/${ticker}`).then(r => r.data),
    enabled: !!ticker,
    refetchInterval: 30_000,
  });

  const { data: summary, isLoading: sumLoading } = useQuery({
    queryKey: ["ticker-summary", ticker],
    queryFn: () => api.get(`/api/intelligence/ticker/${ticker}/summary`).then(r => r.data),
    enabled: !!ticker,
  });

  const { data: news } = useQuery({
    queryKey: ["news-intelligence", ticker],
    queryFn: () => api.get(`/api/intelligence/news/${ticker}`).then(r => r.data),
    enabled: !!ticker && tab === "news",
  });

  const { data: history } = useQuery({
    queryKey: ["history", ticker],
    queryFn: () => api.get(`/api/market/history/${ticker}?period=6mo&interval=1d`).then(r => r.data),
    enabled: !!ticker && tab === "chart",
  });

  async function runEval() {
    if (!evalForm.entry || !evalForm.stop_loss || !evalForm.target) return;
    setEvalLoading(true);
    try {
      const r = await api.post("/api/intelligence/trade/evaluate", {
        ticker,
        entry_price: parseFloat(evalForm.entry),
        stop_loss: parseFloat(evalForm.stop_loss),
        target: parseFloat(evalForm.target),
      });
      setEvalResult(r.data);
    } catch { /* handled silently */ } finally {
      setEvalLoading(false);
    }
  }

  const gradeColor = (g: string) =>
    ["A+", "A"].includes(g) ? "text-green-400" : g === "B" ? "text-yellow-400" : "text-red-400";

  const TABS = [
    { id: "intelligence" as Tab, label: "Intelligence", icon: Brain },
    { id: "chart" as Tab, label: "Chart", icon: BarChart2 },
    { id: "news" as Tab, label: "News", icon: Newspaper },
    { id: "evaluate" as Tab, label: "Evaluate", icon: FlaskConical },
  ];

  return (
    <div className="max-w-[1400px] mx-auto px-4 py-8 fade-in">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-4xl font-bold">{ticker}</h1>
            {quote && (
              <span className={`text-xl font-semibold tabular-nums ${quote.change_pct >= 0 ? "positive" : "negative"}`}>
                {quote.change_pct >= 0 ? "+" : ""}{quote.change_pct?.toFixed(2)}%
              </span>
            )}
          </div>
          {quote && <p className="text-2xl font-mono text-[#888] mt-1">${quote.price?.toFixed(2)}</p>}
        </div>
        {summary?.tone && (
          <span className={`badge ${summary.tone === "bullish" ? "badge-bullish" : summary.tone === "bearish" ? "badge-bearish" : "badge-neutral"}`}>
            {summary.tone}
          </span>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-[#111] border border-[#2a2a2a] rounded-xl p-1 w-fit flex-wrap">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
              tab === id ? "bg-white text-black" : "text-[#888] hover:text-white"
            }`}
          >
            <Icon size={13} />
            {label}
          </button>
        ))}
      </div>

      {/* Intelligence Tab */}
      {tab === "intelligence" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="card">
            <p className="label mb-3">AI Analysis</p>
            {sumLoading ? (
              <div className="space-y-2">
                {[100, 83, 70].map(w => <div key={w} className="skeleton h-3 rounded" style={{ width: `${w}%` }} />)}
              </div>
            ) : summary ? (
              <>
                <p className="text-sm text-[#c0c0c0] leading-relaxed">{summary.summary}</p>
                <p className="text-[10px] text-[#3a3a3a] mt-3">{summary.disclaimer}</p>
              </>
            ) : <p className="text-sm text-[#555]">Add API keys in Settings to enable AI analysis.</p>}
          </div>

          <div className="card">
            <p className="label mb-3">Live Quote</p>
            {quote ? (
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: "Price", value: `$${quote.price?.toFixed(2)}` },
                  { label: "Change", value: `${quote.change_pct >= 0 ? "+" : ""}${quote.change_pct?.toFixed(2)}%`, pos: quote.change_pct >= 0 },
                  { label: "Avg Volume", value: quote.volume?.toLocaleString() ?? "—" },
                  { label: "Market Cap", value: quote.market_cap ? `$${(quote.market_cap / 1e9).toFixed(1)}B` : "N/A" },
                ].map(({ label, value, pos }) => (
                  <div key={label} className="bg-[#0f0f0f] rounded-xl p-3">
                    <p className="text-[10px] text-[#666] mb-1">{label}</p>
                    <p className={`text-sm font-semibold tabular-nums ${pos === true ? "positive" : pos === false ? "negative" : "text-white"}`}>
                      {value}
                    </p>
                  </div>
                ))}
              </div>
            ) : <div className="skeleton h-24 rounded-xl" />}
          </div>
        </div>
      )}

      {/* Chart Tab */}
      {tab === "chart" && (
        <div className="card">
          <p className="label mb-4">{ticker} · 6 Month Price Chart</p>
          {!history ? (
            <div className="skeleton h-64 rounded-xl" />
          ) : (() => {
            const closes = history.map((b: any) => b.close as number);
            const min = Math.min(...closes);
            const max = Math.max(...closes);
            const range = max - min || 1;
            const n = closes.length;
            const isUp = closes[n - 1] >= closes[0];
            const color = isUp ? "#22c55e" : "#ef4444";
            const pts = closes.map((c, i) => `${(i / (n - 1)) * 800},${200 - ((c - min) / range) * 180}`).join(" ");
            return (
              <div className="overflow-x-auto">
                <div className="min-w-[500px]">
                  <svg viewBox="0 0 800 220" className="w-full h-56" style={{ background: "#0a0a0a", borderRadius: "8px" }}>
                    <defs>
                      <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={color} stopOpacity="0.25" />
                        <stop offset="100%" stopColor={color} stopOpacity="0" />
                      </linearGradient>
                    </defs>
                    <polygon points={`0,220 ${pts} 800,220`} fill="url(#chartGrad)" />
                    <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
                  </svg>
                  <div className="flex justify-between text-[10px] text-[#555] mt-2 px-1">
                    <span>{history[0]?.date?.slice(0, 10)}</span>
                    <span className={isUp ? "positive" : "negative"}>
                      {isUp ? "▲" : "▼"} {Math.abs(((closes[n-1] - closes[0]) / closes[0]) * 100).toFixed(1)}%
                    </span>
                    <span>{history[n - 1]?.date?.slice(0, 10)}</span>
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* News Tab */}
      {tab === "news" && (
        <div className="card">
          <p className="label mb-3">News Intelligence · {ticker}</p>
          {!news ? (
            <div className="skeleton h-32 rounded-xl" />
          ) : (
            <>
              <div className="flex gap-2 mb-4 flex-wrap">
                <span className={`badge ${news.tone === "bullish" ? "badge-bullish" : news.tone === "bearish" ? "badge-bearish" : "badge-neutral"}`}>
                  {news.tone}
                </span>
                <span className={`badge ${["high", "critical"].includes(news.severity) ? "badge-bearish" : "badge-neutral"}`}>
                  {news.severity} severity
                </span>
              </div>
              <div className="ai-box mb-4">{news.summary}</div>
              <div className="space-y-2">
                {news.articles?.slice(0, 6).map((a: any, i: number) => (
                  <a
                    key={i}
                    href={a.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block p-3 rounded-xl bg-[#0f0f0f] hover:bg-[#1a1a1a] transition-colors border border-transparent hover:border-[#2a2a2a]"
                  >
                    <p className="text-sm text-[#e0e0e0] mb-1 leading-snug">{a.title}</p>
                    <p className="text-xs text-[#555]">{a.source} · {a.published_at?.slice(0, 10)}</p>
                  </a>
                ))}
              </div>
              <p className="text-[10px] text-[#3a3a3a] mt-4">{news.disclaimer}</p>
            </>
          )}
        </div>
      )}

      {/* Evaluate Tab */}
      {tab === "evaluate" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="card">
            <p className="label mb-4">Trade Setup · {ticker}</p>
            <div className="space-y-3">
              {[
                { k: "entry", label: "Entry Price" },
                { k: "stop_loss", label: "Stop Loss" },
                { k: "target", label: "Target Price" },
              ].map(({ k, label }) => (
                <div key={k}>
                  <label className="block text-xs text-[#888] mb-1">{label}</label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="0.00"
                    value={(evalForm as any)[k]}
                    onChange={e => setEvalForm(f => ({ ...f, [k]: e.target.value }))}
                    className="input"
                  />
                </div>
              ))}
              <button
                onClick={runEval}
                disabled={evalLoading || !evalForm.entry}
                className="btn-primary w-full mt-2"
              >
                {evalLoading ? "Evaluating..." : "Evaluate Setup"}
              </button>
            </div>
          </div>

          {evalResult && (
            <div className="card space-y-5 fade-in">
              <div className="flex items-center justify-between">
                <div>
                  <span className={`text-5xl font-bold ${gradeColor(evalResult.grade)}`}>{evalResult.grade}</span>
                  <span className="text-[#555] text-xl ml-3">{evalResult.overall_score}/100</span>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold tabular-nums">{evalResult.risk_reward?.risk_reward_ratio}:1</div>
                  <div className="text-xs text-[#555]">Risk / Reward</div>
                </div>
              </div>
              <div className="ai-box">{evalResult.ai_assessment}</div>
              {evalResult.technical_analysis?.signals?.length > 0 && (
                <div>
                  <p className="label mb-2">Confirming Signals</p>
                  <div className="space-y-1">
                    {evalResult.technical_analysis.signals.map((s: string, i: number) => (
                      <div key={i} className="text-xs text-green-400 flex gap-2">
                        <span className="shrink-0">✓</span><span>{s}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {evalResult.risk_warnings?.length > 0 && (
                <div>
                  <p className="label mb-2">Risk Warnings</p>
                  <div className="space-y-1">
                    {evalResult.risk_warnings.map((w: string, i: number) => (
                      <div key={i} className="text-xs text-yellow-500 flex gap-2">
                        <span className="shrink-0">⚠</span><span>{w}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <p className="text-[10px] text-[#3a3a3a]">{evalResult.disclaimer}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
