"use client";
import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export function BacktestResults() {
  const { data: strategies } = useQuery({
    queryKey: ["my-strategies"],
    queryFn: () => api.get("/api/trade-lab/strategies").then((r) => r.data),
  });

  const [taskId, setTaskId] = useState<string | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState("");

  const runBacktest = useMutation({
    mutationFn: () => api.post("/api/trade-lab/backtest", {
      strategy_id: selectedStrategy,
      tickers: ["AAPL", "MSFT", "NVDA"],
      start_date: "2023-01-01",
      end_date: "2024-12-31",
    }).then((r) => r.data),
    onSuccess: (data) => setTaskId(data.task_id),
  });

  const { data: backtestStatus } = useQuery({
    queryKey: ["backtest-status", taskId],
    queryFn: () => api.get(`/api/trade-lab/backtest/${taskId}/status`).then((r) => r.data),
    enabled: !!taskId,
    refetchInterval: (data: any) => data?.status === "SUCCESS" ? false : 2000,
  });

  return (
    <div className="card space-y-4">
      <div className="card-header">Strategy Backtester</div>

      <div className="flex gap-3">
        <select
          value={selectedStrategy}
          onChange={(e) => setSelectedStrategy(e.target.value)}
          className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm"
        >
          <option value="">Select a strategy...</option>
          {strategies?.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <button
          className="btn-primary"
          disabled={!selectedStrategy || runBacktest.isPending}
          onClick={() => runBacktest.mutate()}
        >
          {runBacktest.isPending ? "Queuing..." : "Run Backtest"}
        </button>
      </div>

      {taskId && (
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="text-xs text-gray-400 mb-1">Status: <span className="text-blue-400">{backtestStatus?.status ?? "Queued"}</span></div>
          {backtestStatus?.result && (
            <div className="mt-3 grid grid-cols-3 gap-3">
              {Object.entries(backtestStatus.result).map(([k, v]) => (
                <div key={k}>
                  <div className="text-sm font-bold">{String(v)}</div>
                  <div className="text-xs text-gray-500">{k.replace(/_/g, " ")}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
