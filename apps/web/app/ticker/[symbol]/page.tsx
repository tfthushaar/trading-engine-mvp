"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PriceChart } from "@/components/charts/PriceChart";
import { TradeEvaluator } from "@/components/intelligence/TradeEvaluator";
import { NewsIntelligence } from "@/components/intelligence/NewsIntelligence";
import { TickerSummary } from "@/components/intelligence/TickerSummary";

export default function TickerPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const ticker = symbol?.toUpperCase() ?? "";

  const { data: summary, isLoading } = useQuery({
    queryKey: ["ticker-summary", ticker],
    queryFn: () => api.get(`/api/intelligence/ticker/${ticker}/summary`).then((r) => r.data),
    enabled: !!ticker,
  });

  const { data: history } = useQuery({
    queryKey: ["history", ticker],
    queryFn: () => api.get(`/api/market/history/${ticker}?period=6mo&interval=1d`).then((r) => r.data),
    enabled: !!ticker,
  });

  const { data: news } = useQuery({
    queryKey: ["news-intelligence", ticker],
    queryFn: () => api.get(`/api/intelligence/news/${ticker}`).then((r) => r.data),
    enabled: !!ticker,
  });

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">{ticker}</h1>
        {summary && (
          <span className={`text-lg font-semibold ${summary.tone === "bullish" ? "positive" : summary.tone === "bearish" ? "negative" : "text-gray-400"}`}>
            {summary.tone?.toUpperCase()}
          </span>
        )}
      </div>

      {/* Chart */}
      <div className="card">
        <PriceChart data={history ?? []} ticker={ticker} />
      </div>

      {/* Intelligence grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <TickerSummary data={summary} loading={isLoading} />
          <NewsIntelligence data={news} />
        </div>
        <div>
          <TradeEvaluator ticker={ticker} currentPrice={history?.[history.length - 1]?.close} />
        </div>
      </div>
    </div>
  );
}
