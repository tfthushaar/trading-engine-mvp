"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function TradeEvaluatorFull() {
  const [form, setForm] = useState({
    ticker: "",
    entry_price: "",
    stop_loss: "",
    target: "",
    timeframe: "swing",
  });

  const evaluate = useMutation({
    mutationFn: (data: any) => api.post("/api/intelligence/trade/evaluate", {
      ...data,
      entry_price: parseFloat(data.entry_price),
      stop_loss: parseFloat(data.stop_loss),
      target: parseFloat(data.target),
    }).then((r) => r.data),
  });

  const result = evaluate.data;

  const gradeColor = (g: string) =>
    ["A+", "A"].includes(g) ? "text-emerald-400" : ["B"].includes(g) ? "text-yellow-400" : "text-red-400";

  return (
    <div className="space-y-6">
      {/* Input form */}
      <div className="card">
        <div className="card-header">Trade Setup Evaluator</div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          {[
            { key: "ticker", label: "Ticker", placeholder: "AAPL" },
            { key: "entry_price", label: "Entry Price", placeholder: "185.00" },
            { key: "stop_loss", label: "Stop Loss", placeholder: "180.00" },
            { key: "target", label: "Target", placeholder: "198.00" },
          ].map(({ key, label, placeholder }) => (
            <div key={key}>
              <label className="block text-xs text-gray-400 mb-1">{label}</label>
              <input
                type={key === "ticker" ? "text" : "number"}
                placeholder={placeholder}
                value={(form as any)[key]}
                onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
              />
            </div>
          ))}
        </div>
        <button
          className="btn-primary disabled:opacity-50"
          disabled={evaluate.isPending || !form.ticker || !form.entry_price || !form.stop_loss || !form.target}
          onClick={() => evaluate.mutate(form)}
        >
          {evaluate.isPending ? "Evaluating..." : "Evaluate Trade"}
        </button>
      </div>

      {/* Results */}
      {result && (
        <div className="card space-y-4">
          {/* Score header */}
          <div className="flex items-center justify-between">
            <div>
              <div className="text-3xl font-bold">
                <span className={gradeColor(result.grade)}>{result.grade}</span>
                <span className="text-lg text-gray-400 ml-2">{result.overall_score}/100</span>
              </div>
              <div className="text-sm text-gray-400">{result.ticker} · {result.direction?.toUpperCase()}</div>
            </div>
            <div className="text-right">
              <div className="text-xl font-bold">{result.risk_reward?.risk_reward_ratio}:1</div>
              <div className="text-xs text-gray-400">Risk/Reward</div>
            </div>
          </div>

          {/* AI Assessment */}
          <div className="bg-gray-800/50 rounded-lg p-4">
            <div className="text-xs text-gray-400 font-semibold mb-2">AI ASSESSMENT</div>
            <p className="text-sm text-gray-300 leading-relaxed">{result.ai_assessment}</p>
          </div>

          {/* Technical signals */}
          {result.technical_analysis?.signals?.length > 0 && (
            <div>
              <div className="text-xs text-gray-400 font-semibold mb-2">CONFIRMING SIGNALS</div>
              <div className="space-y-1">
                {result.technical_analysis.signals.map((s: string, i: number) => (
                  <div key={i} className="text-xs text-emerald-300 flex gap-2">
                    <span>✓</span> {s}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Warnings */}
          {result.risk_warnings?.length > 0 && (
            <div>
              <div className="text-xs text-gray-400 font-semibold mb-2">RISK WARNINGS</div>
              <div className="space-y-1">
                {result.risk_warnings.map((w: string, i: number) => (
                  <div key={i} className="text-xs text-yellow-300 flex gap-2">
                    <span>⚠</span> {w}
                  </div>
                ))}
              </div>
            </div>
          )}

          <p className="text-xs text-gray-600">{result.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
