"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Bell, Volume2, TrendingUp, Activity } from "lucide-react";

const TYPE_ICONS: Record<string, any> = {
  volume_spike: Volume2,
  breakout: TrendingUp,
  price_move: Activity,
  options_anomaly: Bell,
};

const SEVERITY_CLASSES: Record<string, string> = {
  high: "border-red-500/40 bg-red-950/20",
  medium: "border-yellow-500/40 bg-yellow-950/20",
  low: "border-gray-700 bg-gray-900",
};

export function WatchlistAlerts() {
  const { data } = useQuery({
    queryKey: ["watchlist-alerts"],
    queryFn: () => api.get("/api/intelligence/watchlist-alerts").then((r) => r.data),
    refetchInterval: 60_000,
  });

  const alerts = data?.alerts ?? [];

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div className="card-header mb-0">Watchlist Intelligence</div>
        {alerts.length > 0 && (
          <span className="bg-red-600 text-white text-xs px-2 py-0.5 rounded-full">{alerts.length}</span>
        )}
      </div>

      {alerts.length === 0 ? (
        <p className="text-sm text-gray-500">No alerts right now. Your watchlist is quiet.</p>
      ) : (
        <div className="space-y-2">
          {alerts.slice(0, 5).map((alert: any, i: number) => {
            const Icon = TYPE_ICONS[alert.type] ?? Bell;
            return (
              <div key={i} className={`flex gap-3 rounded-lg p-3 border ${SEVERITY_CLASSES[alert.severity] ?? "border-gray-700"}`}>
                <Icon size={16} className="text-gray-400 shrink-0 mt-0.5" />
                <div>
                  <div className="text-xs font-semibold text-gray-300">
                    {alert.ticker} — {alert.type?.replace(/_/g, " ")}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">{alert.narration}</div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
