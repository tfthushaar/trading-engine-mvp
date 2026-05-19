"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";
import { Search, TrendingUp, TrendingDown, Activity } from "lucide-react";

const WATCHLIST_DEFAULTS = [
  "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
  "META", "TSLA", "AMD", "NFLX", "INTC",
  "JPM", "BAC", "GS", "XOM", "CVX",
  "JNJ", "PFE", "ABBV", "UNH", "LLY",
];

export default function ExplorePage() {
  const router = useRouter();
  const [searchInput, setSearchInput] = useState("");
  const [searchedTicker, setSearchedTicker] = useState<string | null>(null);

  const { data: movers } = useQuery({
    queryKey: ["movers"],
    queryFn: () => api.get("/api/market/movers").then((r) => r.data),
    refetchInterval: 60_000,
  });

  const { data: sectors } = useQuery({
    queryKey: ["sector-heatmap"],
    queryFn: () => api.get("/api/market/sector-heatmap").then((r) => r.data),
    refetchInterval: 120_000,
  });

  const { data: tickerData, isLoading: tickerLoading } = useQuery({
    queryKey: ["explore-ticker", searchedTicker],
    queryFn: () => api.get(`/api/market/quote/${searchedTicker}`).then((r) => r.data),
    enabled: !!searchedTicker,
  });

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const t = searchInput.trim().toUpperCase();
    if (t) setSearchedTicker(t);
  }

  function navigateToTicker(ticker: string) {
    router.push(`/ticker/${ticker}`);
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Explore</h1>
        <p className="text-gray-400 text-sm">Search any ticker, scan movers, or browse sectors</p>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="flex gap-3 max-w-lg">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={16} />
          <input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value.toUpperCase())}
            placeholder="Search ticker... (AAPL, MSFT, NVDA)"
            className="w-full bg-gray-900 border border-gray-700 rounded-xl pl-9 pr-4 py-2.5 text-sm focus:outline-none focus:border-blue-500"
          />
        </div>
        <button type="submit" className="btn-primary px-5">Search</button>
      </form>

      {/* Quick search result */}
      {searchedTicker && (
        <div
          className="card cursor-pointer hover:border-blue-500/50 transition-colors max-w-sm"
          onClick={() => navigateToTicker(searchedTicker)}
        >
          {tickerLoading ? (
            <div className="text-gray-400 text-sm animate-pulse">Loading {searchedTicker}...</div>
          ) : tickerData ? (
            <div className="flex items-center justify-between">
              <div>
                <div className="text-lg font-bold">{tickerData.ticker}</div>
                <div className="text-sm text-gray-400">${tickerData.price?.toFixed(2)}</div>
              </div>
              <div className="text-right">
                <div className={`text-lg font-semibold ${tickerData.change_pct >= 0 ? "positive" : "negative"}`}>
                  {tickerData.change_pct >= 0 ? "+" : ""}{tickerData.change_pct?.toFixed(2)}%
                </div>
                <div
                  className="text-xs text-blue-400 mt-1 cursor-pointer hover:text-blue-300"
                  onClick={(e) => { e.stopPropagation(); navigateToTicker(searchedTicker); }}
                >
                  View analysis →
                </div>
              </div>
            </div>
          ) : (
            <div className="text-gray-400 text-sm">Ticker not found or data unavailable.</div>
          )}
        </div>
      )}

      {/* Top Movers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <div className="card-header flex items-center gap-2">
            <TrendingUp size={14} className="text-emerald-400" />
            Top Gainers
          </div>
          <div className="space-y-2">
            {movers?.gainers?.map((m: any) => (
              <div
                key={m.ticker}
                className="flex items-center justify-between py-1.5 border-b border-gray-800 last:border-0 cursor-pointer hover:bg-gray-800/50 rounded px-2 -mx-2 transition-colors"
                onClick={() => navigateToTicker(m.ticker)}
              >
                <div className="font-semibold">{m.ticker}</div>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-400">${m.price?.toFixed(2)}</span>
                  <span className="positive font-semibold">+{m.change_pct?.toFixed(2)}%</span>
                </div>
              </div>
            )) ?? <div className="text-gray-500 text-sm">Loading...</div>}
          </div>
        </div>
        <div className="card">
          <div className="card-header flex items-center gap-2">
            <TrendingDown size={14} className="text-red-400" />
            Top Losers
          </div>
          <div className="space-y-2">
            {movers?.losers?.map((m: any) => (
              <div
                key={m.ticker}
                className="flex items-center justify-between py-1.5 border-b border-gray-800 last:border-0 cursor-pointer hover:bg-gray-800/50 rounded px-2 -mx-2 transition-colors"
                onClick={() => navigateToTicker(m.ticker)}
              >
                <div className="font-semibold">{m.ticker}</div>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-400">${m.price?.toFixed(2)}</span>
                  <span className="negative font-semibold">{m.change_pct?.toFixed(2)}%</span>
                </div>
              </div>
            )) ?? <div className="text-gray-500 text-sm">Loading...</div>}
          </div>
        </div>
      </div>

      {/* Quick access tickers */}
      <div className="card">
        <div className="card-header">Quick Access</div>
        <div className="flex flex-wrap gap-2">
          {WATCHLIST_DEFAULTS.map((ticker) => (
            <button
              key={ticker}
              onClick={() => navigateToTicker(ticker)}
              className="bg-gray-800 hover:bg-gray-700 border border-gray-700 hover:border-blue-500/50 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
            >
              {ticker}
            </button>
          ))}
        </div>
      </div>

      {/* Sector heat mini */}
      <div className="card">
        <div className="card-header">Sectors Today</div>
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
          {sectors?.map((s: any) => (
            <div
              key={s.sector}
              className={`rounded-lg p-2.5 text-center cursor-pointer ${
                s.change_pct >= 1 ? "bg-emerald-800/60" :
                s.change_pct >= 0 ? "bg-emerald-900/30" :
                s.change_pct >= -1 ? "bg-red-900/30" : "bg-red-800/60"
              }`}
            >
              <div className="text-xs font-semibold truncate text-gray-300">{s.sector}</div>
              <div className={`text-sm font-bold mt-0.5 ${s.change_pct >= 0 ? "positive" : "negative"}`}>
                {s.change_pct >= 0 ? "+" : ""}{s.change_pct?.toFixed(2)}%
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
