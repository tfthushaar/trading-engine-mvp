"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Plus, TrendingUp, TrendingDown, Brain } from "lucide-react";

interface JournalEntry {
  id: string;
  ticker: string;
  direction: string;
  pnl_percent: number | null;
  entry_date: string;
  rule_followed: boolean | null;
  ai_review: any;
}

export default function JournalPage() {
  const [showForm, setShowForm] = useState(false);
  const qc = useQueryClient();

  const { data: entries = [], isLoading } = useQuery<JournalEntry[]>({
    queryKey: ["journal"],
    queryFn: () => api.get("/api/journal/entries").then((r) => r.data),
  });

  const { data: behavioralReport, isLoading: reportLoading } = useQuery({
    queryKey: ["behavioral-report"],
    queryFn: () => api.get("/api/journal/behavioral-report").then((r) => r.data),
  });

  const addEntry = useMutation({
    mutationFn: (data: any) => api.post("/api/journal/entries", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["journal"] });
      qc.invalidateQueries({ queryKey: ["behavioral-report"] });
      setShowForm(false);
    },
  });

  const winRate = entries.length > 0
    ? Math.round(entries.filter((e) => (e.pnl_percent ?? 0) > 0).length / entries.filter((e) => e.pnl_percent !== null).length * 100)
    : null;

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Trade Journal</h1>
          <p className="text-gray-400 text-sm">Track, review, and learn from every trade</p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={() => setShowForm(!showForm)}>
          <Plus size={16} /> Log Trade
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="card text-center">
          <div className="stat-value">{entries.length}</div>
          <div className="stat-label">Total Trades</div>
        </div>
        <div className="card text-center">
          <div className={`stat-value ${winRate && winRate > 50 ? "positive" : "negative"}`}>
            {winRate !== null ? `${winRate}%` : "—"}
          </div>
          <div className="stat-label">Win Rate</div>
        </div>
        <div className="card text-center">
          <div className={`stat-value ${behavioralReport?.score >= 70 ? "positive" : "negative"}`}>
            {behavioralReport?.score ?? "—"}
          </div>
          <div className="stat-label">Discipline Score</div>
        </div>
        <div className="card text-center">
          <div className="stat-value">{behavioralReport?.grade ?? "—"}</div>
          <div className="stat-label">Grade</div>
        </div>
      </div>

      {/* AI Behavioral Report */}
      {behavioralReport?.ai_report && (
        <div className="card border-l-4 border-blue-500">
          <div className="flex items-center gap-2 mb-2">
            <Brain size={16} className="text-blue-400" />
            <span className="card-header mb-0">AI Behavioral Analysis</span>
          </div>
          <p className="text-sm text-gray-300 leading-relaxed">{behavioralReport.ai_report}</p>
          {behavioralReport.behavioral_patterns?.length > 0 && (
            <div className="mt-3 space-y-1">
              {behavioralReport.behavioral_patterns.map((p: any, i: number) => (
                <div key={i} className={`text-xs px-2 py-1 rounded flex items-start gap-2 ${
                  p.severity === "high" ? "bg-red-900/30 text-red-300" :
                  p.severity === "medium" ? "bg-yellow-900/30 text-yellow-300" :
                  "bg-gray-800 text-gray-400"
                }`}>
                  <span className="font-semibold capitalize">{p.pattern.replace(/_/g, " ")}:</span>
                  <span>{p.description}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Trade list */}
      <div className="space-y-2">
        {isLoading ? (
          <div className="text-gray-400 text-sm">Loading trades...</div>
        ) : entries.length === 0 ? (
          <div className="card text-center py-12 text-gray-500">
            <p>No trades logged yet.</p>
            <p className="text-sm mt-1">Log your first trade to start building your journal.</p>
          </div>
        ) : (
          entries.map((entry) => (
            <div key={entry.id} className="card flex items-center gap-4">
              <div className={entry.direction === "long" ? "text-emerald-400" : "text-red-400"}>
                {entry.direction === "long" ? <TrendingUp size={20} /> : <TrendingDown size={20} />}
              </div>
              <div className="flex-1">
                <div className="font-semibold">{entry.ticker}</div>
                <div className="text-xs text-gray-400">{new Date(entry.entry_date).toLocaleDateString()}</div>
              </div>
              {entry.pnl_percent !== null && (
                <div className={`font-semibold ${entry.pnl_percent >= 0 ? "positive" : "negative"}`}>
                  {entry.pnl_percent >= 0 ? "+" : ""}{entry.pnl_percent?.toFixed(2)}%
                </div>
              )}
              <div className={`text-xs px-2 py-0.5 rounded ${
                entry.rule_followed === true ? "badge-bullish" :
                entry.rule_followed === false ? "badge-bearish" : "badge-neutral"
              }`}>
                {entry.rule_followed === true ? "Rules ✓" : entry.rule_followed === false ? "Rule break" : "No tag"}
              </div>
              {entry.ai_review && (
                <div className="badge-neutral">AI reviewed</div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
