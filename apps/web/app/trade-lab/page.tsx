"use client";
import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { TradeEvaluatorFull } from "@/components/intelligence/TradeEvaluatorFull";
import { StrategyBuilder } from "@/components/intelligence/StrategyBuilder";
import { BacktestResults } from "@/components/charts/BacktestResults";

type Tab = "evaluate" | "build" | "backtest";

export default function TradeLabPage() {
  const [activeTab, setActiveTab] = useState<Tab>("evaluate");

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <h1 className="text-2xl font-bold mb-2">Trade Lab</h1>
      <p className="text-gray-400 text-sm mb-6">
        Evaluate trade setups, build strategies, and backtest with historical data
      </p>

      {/* Tab bar */}
      <div className="flex gap-1 bg-gray-900 p-1 rounded-xl w-fit mb-6">
        {(["evaluate", "build", "backtest"] as Tab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-white"
            }`}
          >
            {tab === "evaluate" ? "Trade Evaluator" : tab === "build" ? "Strategy Builder" : "Backtester"}
          </button>
        ))}
      </div>

      {activeTab === "evaluate" && <TradeEvaluatorFull />}
      {activeTab === "build" && <StrategyBuilder />}
      {activeTab === "backtest" && <BacktestResults />}
    </div>
  );
}
