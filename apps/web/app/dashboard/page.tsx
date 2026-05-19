"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { MacroBar } from "@/components/intelligence/MacroBar";
import { SectorHeatmap } from "@/components/charts/SectorHeatmap";
import { WatchlistAlerts } from "@/components/intelligence/WatchlistAlerts";
import { DailyBriefing } from "@/components/intelligence/DailyBriefing";
import { TopMovers } from "@/components/intelligence/TopMovers";

export default function DashboardPage() {
  const { data: briefing, isLoading: briefingLoading } = useQuery({
    queryKey: ["daily-briefing"],
    queryFn: () => api.get("/api/intelligence/briefing/daily").then((r) => r.data),
    staleTime: 4 * 60 * 60 * 1000, // 4 hours
  });

  const { data: macro } = useQuery({
    queryKey: ["macro"],
    queryFn: () => api.get("/api/market/macro").then((r) => r.data),
    refetchInterval: 60_000,
  });

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

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* Macro bar */}
      <MacroBar data={macro} />

      {/* AI Daily Briefing */}
      <DailyBriefing data={briefing} loading={briefingLoading} />

      {/* Three-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <SectorHeatmap data={sectors} />
        </div>
        <div>
          <TopMovers data={movers} />
        </div>
      </div>

      {/* Watchlist alerts */}
      <WatchlistAlerts />
    </div>
  );
}
