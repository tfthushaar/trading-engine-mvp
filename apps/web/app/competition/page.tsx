"use client";
import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Trophy, Cpu, TrendingUp, BarChart2, Play, Search } from "lucide-react";

const PERIODS = [
  { value: "6mo", label: "6 Months" },
  { value: "1y",  label: "1 Year" },
  { value: "2y",  label: "2 Years" },
];

const STRATEGY_COLORS: Record<string, string> = {
  rsi_mean_reversion: "text-blue-400",
  ema_trend_following: "text-green-400",
  bollinger_breakout: "text-yellow-400",
  macd_momentum: "text-purple-400",
  volume_price_composite: "text-orange-400",
};

export default function CompetitionPage() {
  const [ticker, setTicker] = useState("");
  const [period, setPeriod] = useState("1y");
  const [runTicker, setRunTicker] = useState<string | null>(null);

  const { data: strategies } = useQuery({
    queryKey: ["competition-strategies"],
    queryFn: () => api.get("/api/competition/strategies").then(r => r.data),
  });

  const { data: watchlists } = useQuery({
    queryKey: ["watchlists"],
    queryFn: () => api.get("/api/watchlist/").then(r => r.data),
  });

  const runSingle = useMutation({
    mutationFn: (t: string) => api.post(`/api/competition/run/${t}?period=${period}`).then(r => r.data),
  });

  const runWatchlist = useMutation({
    mutationFn: () => api.post(`/api/competition/run-watchlist?period=${period}`).then(r => r.data),
  });

  const result = runSingle.data;
  const wlResult = runWatchlist.data;

  function getRankColor(rank: number) {
    return rank === 1 ? "text-yellow-400" : rank === 2 ? "text-[#888]" : rank === 3 ? "text-orange-700" : "text-[#555]";
  }

  return (
    <div className="max-w-[1400px] mx-auto px-4 py-8 space-y-6 fade-in">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="section-title">Strategy Competition</h1>
          <p className="section-subtitle">5 AI agents test different strategies on your stocks — the best one wins</p>
        </div>
        <div className="flex items-center gap-2">
          {PERIODS.map(p => (
            <button key={p.value} onClick={() => setPeriod(p.value)} className={`btn text-xs py-1.5 px-3 ${period === p.value ? "btn-primary" : "btn-secondary"}`}>{p.label}</button>
          ))}
        </div>
      </div>

      {/* Strategy agents overview */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {strategies?.strategies?.map((s: any, i: number) => (
          <div key={s.id} className="card-sm text-center">
            <div className="w-8 h-8 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg flex items-center justify-center mx-auto mb-2">
              <Cpu size={14} className={STRATEGY_COLORS[s.id] || "text-[#888]"} />
            </div>
            <p className="text-xs font-medium leading-snug">{s.name}</p>
            <p className="text-[10px] text-[#555] mt-0.5">Agent {i + 1}</p>
          </div>
        ))}
      </div>

      {/* Run controls */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Single ticker */}
        <div className="card space-y-4">
          <div className="flex items-center gap-2"><BarChart2 size={14} /><p className="label">Single Ticker Competition</p></div>
          <div className="flex gap-2">
            <input
              className="input flex-1"
              placeholder="Enter ticker (e.g. AAPL)"
              value={ticker}
              onChange={e => setTicker(e.target.value.toUpperCase())}
              onKeyDown={e => { if (e.key === "Enter" && ticker) runSingle.mutate(ticker); }}
            />
            <button onClick={() => ticker && runSingle.mutate(ticker)} disabled={!ticker || runSingle.isPending} className="btn-primary">
              {runSingle.isPending ? <><Cpu size={13} className="animate-spin" /> Running...</> : <><Play size={13} /> Run</>}
            </button>
          </div>
          <p className="text-xs text-[#555]">All 5 strategy agents backtest simultaneously on {period} of data</p>
        </div>

        {/* Watchlist */}
        <div className="card space-y-4">
          <div className="flex items-center gap-2"><Search size={14} /><p className="label">Watchlist Competition</p></div>
          <div>
            <p className="text-xs text-[#888] mb-2">
              {watchlists?.length > 0
                ? `Will run on ${watchlists.reduce((acc: number, wl: any) => acc + (wl.tickers?.length || 0), 0)} tickers across ${watchlists.length} watchlist(s)`
                : "Add stocks to your watchlist first"}
            </p>
            <button onClick={() => runWatchlist.mutate()} disabled={!watchlists?.length || runWatchlist.isPending} className="btn-primary w-full">
              {runWatchlist.isPending ? <><Cpu size={13} className="animate-spin" /> Running all tickers...</> : <><Play size={13} /> Run Watchlist Competition</>}
            </button>
          </div>
        </div>
      </div>

      {/* Single ticker result */}
      {(runSingle.isPending || result) && (
        <div className="card space-y-5 fade-in">
          {runSingle.isPending ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm text-[#888]"><Cpu size={14} className="animate-spin" /> 5 agents competing...</div>
              {Array.from({length:5}).map((_,i) => <div key={i} className="skeleton h-8 rounded-xl" />)}
            </div>
          ) : result ? (
            <>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <h2 className="text-xl font-bold">{result.ticker}</h2>
                    <span className="badge-neutral">{result.period}</span>
                  </div>
                  {result.winner_name && (
                    <div className="flex items-center gap-2">
                      <Trophy size={16} className="text-yellow-400" />
                      <span className="font-semibold text-yellow-400">{result.winner_name}</span>
                      <span className="text-xs text-[#555]">wins</span>
                    </div>
                  )}
                </div>
              </div>

              {/* AI interpretation */}
              {result.ai_interpretation && (
                <div className="ai-box">{result.ai_interpretation}</div>
              )}

              {/* Rankings table */}
              <div>
                <p className="label mb-3">Strategy Rankings</p>
                <div className="space-y-2">
                  {result.ranking?.map((r: any) => (
                    <div key={r.strategy_id} className={`rounded-xl p-3 ${r.rank === 1 ? "bg-[#1a1a0a] border border-yellow-900/30" : "bg-[#0f0f0f] border border-[#1e1e1e]"}`}>
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <div className="flex items-center gap-3">
                          <span className={`text-lg font-bold ${getRankColor(r.rank)}`}>#{r.rank}</span>
                          <div>
                            <p className="text-sm font-medium">{r.strategy_name}</p>
                            {r.status === "error" && <p className="text-xs text-red-400">Insufficient trades</p>}
                          </div>
                        </div>
                        {r.status !== "error" && (
                          <div className="flex gap-4 text-xs">
                            <div className="text-right">
                              <p className="text-[#555]">Sharpe</p>
                              <p className={`font-semibold tabular-nums ${r.sharpe_ratio > 0 ? "positive" : "negative"}`}>{r.sharpe_ratio?.toFixed(2)}</p>
                            </div>
                            <div className="text-right">
                              <p className="text-[#555]">Return</p>
                              <p className={`font-semibold tabular-nums ${r.total_return_pct >= 0 ? "positive" : "negative"}`}>{r.total_return_pct >= 0 ? "+" : ""}{r.total_return_pct?.toFixed(1)}%</p>
                            </div>
                            <div className="text-right">
                              <p className="text-[#555]">Win Rate</p>
                              <p className="font-semibold tabular-nums">{(r.win_rate * 100)?.toFixed(0)}%</p>
                            </div>
                            <div className="text-right">
                              <p className="text-[#555]">Trades</p>
                              <p className="font-semibold tabular-nums">{r.total_trades}</p>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <p className="text-[10px] text-[#3a3a3a]">{result.disclaimer}</p>
            </>
          ) : null}
        </div>
      )}

      {/* Watchlist competition result */}
      {(runWatchlist.isPending || wlResult) && (
        <div className="card space-y-5 fade-in">
          {runWatchlist.isPending ? (
            <div className="text-sm text-[#888] flex items-center gap-2"><Cpu size={14} className="animate-spin" /> Running competition across all watchlist tickers...</div>
          ) : wlResult ? (
            <>
              {/* Overall winner */}
              {wlResult.overall_best_strategy?.strategy_name && (
                <div className="bg-[#1a1a0a] border border-yellow-900/30 rounded-2xl p-5">
                  <div className="flex items-center gap-3 mb-2">
                    <Trophy size={20} className="text-yellow-400" />
                    <h3 className="text-lg font-bold">Overall Best Strategy</h3>
                  </div>
                  <p className="text-2xl font-bold text-yellow-400 mb-1">{wlResult.overall_best_strategy.strategy_name}</p>
                  <p className="text-sm text-[#888]">
                    Won {wlResult.overall_best_strategy.wins} out of {wlResult.overall_best_strategy.total_tickers} ticker(s)
                  </p>
                </div>
              )}

              {/* Strategy win distribution */}
              {wlResult.strategy_win_counts && Object.keys(wlResult.strategy_win_counts).length > 0 && (
                <div>
                  <p className="label mb-3">Win Distribution</p>
                  <div className="space-y-2">
                    {Object.entries(wlResult.strategy_win_counts)
                      .sort(([,a],[,b]) => (b as number) - (a as number))
                      .map(([sid, wins]) => {
                        const stratName = strategies?.strategies?.find((s:any) => s.id === sid)?.name || sid;
                        const pct = ((wins as number) / wlResult.overall_best_strategy.total_tickers) * 100;
                        return (
                          <div key={sid}>
                            <div className="flex justify-between text-xs mb-1">
                              <span className={`font-medium ${STRATEGY_COLORS[sid] || "text-white"}`}>{stratName}</span>
                              <span className="text-[#888]">{wins as number} wins</span>
                            </div>
                            <div className="h-1.5 bg-[#1a1a1a] rounded-full overflow-hidden">
                              <div className="h-full bg-white rounded-full" style={{width:`${pct}%`}} />
                            </div>
                          </div>
                        );
                      })}
                  </div>
                </div>
              )}

              {/* Per-ticker results */}
              <div>
                <p className="label mb-3">Per-Ticker Results</p>
                <div className="space-y-3">
                  {wlResult.per_ticker?.map((r: any) => (
                    <div key={r.ticker} className="card-sm">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-semibold">{r.ticker}</span>
                        {r.winner && (
                          <div className="flex items-center gap-1.5">
                            <Trophy size={12} className="text-yellow-400" />
                            <span className="text-xs text-yellow-400 font-medium">{r.winner}</span>
                          </div>
                        )}
                      </div>
                      {r.ai_interpretation && <p className="text-xs text-[#999] leading-relaxed">{r.ai_interpretation}</p>}
                    </div>
                  ))}
                </div>
              </div>

              <p className="text-[10px] text-[#3a3a3a]">{wlResult.disclaimer}</p>
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}
