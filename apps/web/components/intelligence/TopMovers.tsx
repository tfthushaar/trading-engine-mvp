"use client";
import { TrendingUp, TrendingDown } from "lucide-react";

interface Mover {
  ticker: string;
  price: number;
  change_pct: number;
}

interface Props {
  data: { gainers: Mover[]; losers: Mover[] } | undefined;
}

export function TopMovers({ data }: Props) {
  return (
    <div className="card h-full">
      <div className="card-header">Top Movers</div>
      <div className="space-y-4">
        <div>
          <div className="text-xs text-emerald-400 font-semibold mb-2 flex items-center gap-1">
            <TrendingUp size={12} /> GAINERS
          </div>
          <div className="space-y-1.5">
            {data?.gainers?.map((m) => (
              <div key={m.ticker} className="flex items-center justify-between">
                <span className="text-sm font-medium">{m.ticker}</span>
                <span className="positive text-sm font-semibold">+{m.change_pct}%</span>
              </div>
            )) ?? <div className="text-xs text-gray-600">Loading...</div>}
          </div>
        </div>
        <div>
          <div className="text-xs text-red-400 font-semibold mb-2 flex items-center gap-1">
            <TrendingDown size={12} /> LOSERS
          </div>
          <div className="space-y-1.5">
            {data?.losers?.map((m) => (
              <div key={m.ticker} className="flex items-center justify-between">
                <span className="text-sm font-medium">{m.ticker}</span>
                <span className="negative text-sm font-semibold">{m.change_pct}%</span>
              </div>
            )) ?? <div className="text-xs text-gray-600">Loading...</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
