"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface Props {
  ticker: string;
  currentPrice?: number;
}

export function TradeEvaluator({ ticker, currentPrice }: Props) {
  const [form, setForm] = useState({
    entry_price: currentPrice?.toFixed(2) ?? "",
    stop_loss: "",
    target: "",
  });

  const evaluate = useMutation({
    mutationFn: () => api.post("/api/intelligence/trade/evaluate", {
      ticker,
      entry_price: parseFloat(form.entry_price),
      stop_loss: parseFloat(form.stop_loss),
      target: parseFloat(form.target),
    }).then((r) => r.data),
  });

  return (
    <div className="card">
      <div className="card-header">Quick Trade Evaluator</div>
      <div className="space-y-3">
        {[
          { key: "entry_price", label: "Entry" },
          { key: "stop_loss", label: "Stop Loss" },
          { key: "target", label: "Target" },
        ].map(({ key, label }) => (
          <div key={key}>
            <label className="block text-xs text-gray-400 mb-1">{label}</label>
            <input
              type="number"
              value={(form as any)[key]}
              onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
        ))}
        <button
          className="btn-primary w-full"
          disabled={evaluate.isPending}
          onClick={() => evaluate.mutate()}
        >
          {evaluate.isPending ? "Evaluating..." : "Evaluate"}
        </button>
      </div>

      {evaluate.data && (
        <div className="mt-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-400">Score</span>
            <span className="font-bold text-lg">{evaluate.data.overall_score}/100 ({evaluate.data.grade})</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-400">R:R</span>
            <span className="font-semibold">{evaluate.data.risk_reward?.risk_reward_ratio}:1</span>
          </div>
          <p className="text-xs text-gray-400 leading-relaxed">{evaluate.data.ai_assessment}</p>
        </div>
      )}
    </div>
  );
}
