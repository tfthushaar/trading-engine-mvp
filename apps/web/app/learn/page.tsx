"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { BookOpen, ChevronRight, Sparkles } from "lucide-react";

const CONCEPTS = [
  { key:"rsi", label:"RSI", category:"Momentum" },
  { key:"macd", label:"MACD", category:"Momentum" },
  { key:"moving_average", label:"Moving Averages", category:"Trend" },
  { key:"support_resistance", label:"Support & Resistance", category:"Price Action" },
  { key:"volume", label:"Volume Analysis", category:"Confirmation" },
  { key:"bollinger_bands", label:"Bollinger Bands", category:"Volatility" },
  { key:"risk_reward", label:"Risk / Reward", category:"Risk Management" },
];

export default function LearnPage() {
  const [selected, setSelected] = useState<string | null>(null);
  const [ticker, setTicker] = useState("");

  const { data: nextTopic } = useQuery({
    queryKey: ["next-topic"],
    queryFn: () => api.get("/api/learn/next-topic").then(r => r.data),
  });

  const { data: explanation, isLoading: explaining } = useQuery({
    queryKey: ["explain", selected, ticker],
    queryFn: () => api.get(`/api/learn/explain/${selected}${ticker ? `?context_ticker=${ticker}` : ""}`).then(r => r.data),
    enabled: !!selected,
  });

  const byCategory = CONCEPTS.reduce((acc, c) => {
    (acc[c.category] = acc[c.category] || []).push(c);
    return acc;
  }, {} as Record<string, typeof CONCEPTS>);

  return (
    <div className="max-w-[1400px] mx-auto px-4 py-8 fade-in">
      <div className="mb-6">
        <h1 className="section-title">Learning Hub</h1>
        <p className="section-subtitle">Context-aware explanations adapted to your level</p>
      </div>

      {nextTopic?.recommended_topic && !selected && (
        <button
          onClick={() => setSelected(nextTopic.recommended_topic)}
          className="card-sm w-full text-left flex items-center justify-between mb-6 hover:border-[#444] transition-colors"
        >
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center shrink-0">
              <Sparkles size={14} className="text-black" />
            </div>
            <div>
              <p className="text-[10px] text-[#888] uppercase tracking-widest mb-0.5">Recommended Next</p>
              <p className="font-semibold">{nextTopic.topic_display}</p>
              <p className="text-xs text-[#555]">{nextTopic.concepts_remaining_at_level} concepts remaining at {nextTopic.user_level} level</p>
            </div>
          </div>
          <ChevronRight size={16} className="text-[#555]" />
        </button>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Concept list */}
        <div className="space-y-4">
          {Object.entries(byCategory).map(([cat, concepts]) => (
            <div key={cat}>
              <p className="label mb-2">{cat}</p>
              <div className="space-y-1">
                {concepts.map(c => (
                  <button
                    key={c.key}
                    onClick={() => setSelected(c.key)}
                    className={`w-full card-sm text-left flex items-center justify-between hover:border-[#444] transition-all ${selected===c.key?"border-white bg-[#1a1a1a]":""}`}
                  >
                    <span className="text-sm font-medium">{c.label}</span>
                    <ChevronRight size={14} className="text-[#555]" />
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Explanation */}
        <div className="lg:col-span-2">
          {!selected ? (
            <div className="card flex flex-col items-center justify-center py-20 text-center">
              <BookOpen size={32} className="text-[#333] mb-3" />
              <p className="text-[#555] text-sm">Select a concept to get an AI-powered contextual explanation</p>
            </div>
          ) : (
            <div className="card space-y-4">
              {/* Context ticker */}
              <div className="flex gap-2">
                <input
                  value={ticker}
                  onChange={e => setTicker(e.target.value.toUpperCase())}
                  placeholder="Optional: add ticker for live context (e.g. AAPL)"
                  className="input flex-1"
                />
                {ticker && <button onClick={() => setTicker("")} className="btn-secondary px-3 text-xs">Clear</button>}
              </div>

              {explaining ? (
                <div className="space-y-3">{[100,85,70,90,60].map(w=><div key={w} className="skeleton h-3 rounded" style={{width:`${w}%`}}/>)}</div>
              ) : explanation ? (
                <>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <h2 className="text-xl font-bold">{explanation.full_name}</h2>
                      {ticker && <span className="badge-blue">{ticker} context</span>}
                    </div>
                    <div className="flex gap-2">
                      <span className="badge-neutral">{explanation.category}</span>
                      <span className="badge-neutral">{explanation.user_level}</span>
                    </div>
                  </div>
                  <div className="ai-box whitespace-pre-wrap">{explanation.explanation}</div>
                  <p className="text-[10px] text-[#3a3a3a]">{explanation.disclaimer}</p>
                </>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
