"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { BookOpen, ChevronRight } from "lucide-react";

const CONCEPTS = [
  { key: "rsi", label: "RSI", category: "Momentum" },
  { key: "macd", label: "MACD", category: "Momentum" },
  { key: "moving_average", label: "Moving Averages", category: "Trend" },
  { key: "support_resistance", label: "Support & Resistance", category: "Price Action" },
  { key: "volume", label: "Volume Analysis", category: "Confirmation" },
  { key: "bollinger_bands", label: "Bollinger Bands", category: "Volatility" },
  { key: "risk_reward", label: "Risk/Reward", category: "Risk Management" },
];

export default function LearnPage() {
  const [selected, setSelected] = useState<string | null>(null);
  const [tickerInput, setTickerInput] = useState("");

  const { data: nextTopic } = useQuery({
    queryKey: ["next-topic"],
    queryFn: () => api.get("/api/learn/next-topic").then((r) => r.data),
  });

  const { data: explanation, isLoading: explaining } = useQuery({
    queryKey: ["explain", selected, tickerInput],
    queryFn: () =>
      api.get(`/api/learn/explain/${selected}${tickerInput ? `?context_ticker=${tickerInput}` : ""}`).then((r) => r.data),
    enabled: !!selected,
  });

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
      <h1 className="text-2xl font-bold">Learning Hub</h1>
      <p className="text-gray-400 text-sm">Contextual AI explanations — adapted to your level</p>

      {nextTopic?.recommended_topic && (
        <div
          className="card border border-blue-500/40 cursor-pointer hover:border-blue-400 transition-colors"
          onClick={() => setSelected(nextTopic.recommended_topic)}
        >
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-blue-400 font-semibold mb-1">RECOMMENDED NEXT</div>
              <div className="font-semibold">{nextTopic.topic_display}</div>
              <div className="text-xs text-gray-400">
                {nextTopic.concepts_remaining_at_level} concepts remaining at {nextTopic.user_level} level
              </div>
            </div>
            <ChevronRight className="text-blue-400" />
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Concept list */}
        <div className="space-y-2">
          <div className="card-header">Concepts</div>
          {CONCEPTS.map((c) => (
            <button
              key={c.key}
              onClick={() => setSelected(c.key)}
              className={`w-full card text-left flex items-center justify-between hover:border-blue-500/50 transition-colors ${
                selected === c.key ? "border-blue-500" : ""
              }`}
            >
              <div>
                <div className="font-medium text-sm">{c.label}</div>
                <div className="text-xs text-gray-500">{c.category}</div>
              </div>
              <ChevronRight size={16} className="text-gray-500" />
            </button>
          ))}
        </div>

        {/* Explanation panel */}
        <div className="lg:col-span-2">
          {!selected ? (
            <div className="card h-64 flex items-center justify-center text-gray-500 flex-col gap-2">
              <BookOpen size={32} />
              <p>Select a concept to get an AI-powered explanation</p>
            </div>
          ) : (
            <div className="card">
              {/* Ticker context input */}
              <div className="flex gap-2 mb-4">
                <input
                  type="text"
                  placeholder="Optional: enter ticker for live context (e.g. AAPL)"
                  value={tickerInput}
                  onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
                  className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>

              {explaining ? (
                <div className="text-gray-400 text-sm animate-pulse">Generating explanation...</div>
              ) : explanation ? (
                <>
                  <h2 className="text-lg font-bold mb-1">{explanation.full_name}</h2>
                  <div className="flex gap-2 mb-4">
                    <span className="badge-neutral">{explanation.category}</span>
                    <span className="badge-neutral">{explanation.user_level}</span>
                    {explanation.context_ticker && (
                      <span className="bg-blue-900/40 text-blue-400 text-xs px-2 py-0.5 rounded-full">
                        {explanation.context_ticker} context
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                    {explanation.explanation}
                  </div>
                  <p className="text-xs text-gray-500 mt-4">{explanation.disclaimer}</p>
                </>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
