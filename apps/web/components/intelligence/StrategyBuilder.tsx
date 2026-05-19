"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Plus, Trash2 } from "lucide-react";

const INDICATORS = ["RSI", "MACD", "EMA", "SMA", "Volume", "Bollinger Band", "ATR", "Stochastic"];
const OPERATORS = ["is above", "is below", "crosses above", "crosses below", "is greater than", "is less than"];

interface Rule {
  indicator: string;
  operator: string;
  value: string;
}

export function StrategyBuilder() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [entryRules, setEntryRules] = useState<Rule[]>([{ indicator: "RSI", operator: "is below", value: "30" }]);
  const [exitRules, setExitRules] = useState<Rule[]>([{ indicator: "RSI", operator: "is above", value: "60" }]);

  const { data: templates } = useQuery({
    queryKey: ["templates"],
    queryFn: () => api.get("/api/trade-lab/templates").then((r) => r.data),
  });

  const { data: myStrategies } = useQuery({
    queryKey: ["my-strategies"],
    queryFn: () => api.get("/api/trade-lab/strategies").then((r) => r.data),
  });

  const saveStrategy = useMutation({
    mutationFn: (data: any) => api.post("/api/trade-lab/strategies", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-strategies"] }),
  });

  const addRule = (type: "entry" | "exit") => {
    const rule = { indicator: "RSI", operator: "is above", value: "50" };
    if (type === "entry") setEntryRules((r) => [...r, rule]);
    else setExitRules((r) => [...r, rule]);
  };

  const updateRule = (type: "entry" | "exit", index: number, field: keyof Rule, value: string) => {
    const setter = type === "entry" ? setEntryRules : setExitRules;
    setter((rules) => rules.map((r, i) => i === index ? { ...r, [field]: value } : r));
  };

  const removeRule = (type: "entry" | "exit", index: number) => {
    const setter = type === "entry" ? setEntryRules : setExitRules;
    setter((rules) => rules.filter((_, i) => i !== index));
  };

  const RuleEditor = ({ type, rules }: { type: "entry" | "exit"; rules: Rule[] }) => (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs font-semibold text-gray-400 uppercase">{type} Rules</div>
        <button className="text-xs text-blue-400 flex items-center gap-1" onClick={() => addRule(type)}>
          <Plus size={12} /> Add Rule
        </button>
      </div>
      <div className="space-y-2">
        {rules.map((rule, i) => (
          <div key={i} className="flex gap-2 items-center">
            <select
              value={rule.indicator}
              onChange={(e) => updateRule(type, i, "indicator", e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded-lg px-2 py-1.5 text-xs flex-1"
            >
              {INDICATORS.map((ind) => <option key={ind}>{ind}</option>)}
            </select>
            <select
              value={rule.operator}
              onChange={(e) => updateRule(type, i, "operator", e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded-lg px-2 py-1.5 text-xs flex-1"
            >
              {OPERATORS.map((op) => <option key={op}>{op}</option>)}
            </select>
            <input
              type="text"
              value={rule.value}
              onChange={(e) => updateRule(type, i, "value", e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded-lg px-2 py-1.5 text-xs w-20"
            />
            <button onClick={() => removeRule(type, i)} className="text-gray-600 hover:text-red-400">
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Builder */}
      <div className="lg:col-span-2 card space-y-4">
        <div className="card-header">No-Code Strategy Builder</div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Strategy Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My RSI Strategy"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
          />
        </div>

        <RuleEditor type="entry" rules={entryRules} />
        <RuleEditor type="exit" rules={exitRules} />

        <button
          className="btn-primary"
          disabled={!name || saveStrategy.isPending}
          onClick={() => saveStrategy.mutate({
            strategy_name: name,
            entry_conditions: entryRules.map((r) => ({ indicator: r.indicator, operator: r.operator, value: parseFloat(r.value) || r.value })),
            exit_conditions: exitRules.map((r) => ({ indicator: r.indicator, operator: r.operator, value: parseFloat(r.value) || r.value })),
          })}
        >
          {saveStrategy.isPending ? "Saving..." : "Save Strategy"}
        </button>
        {saveStrategy.isSuccess && <div className="text-xs text-emerald-400">Strategy saved!</div>}
      </div>

      {/* My Strategies */}
      <div className="card">
        <div className="card-header">My Strategies</div>
        {!myStrategies?.length ? (
          <p className="text-xs text-gray-500">No strategies saved yet.</p>
        ) : (
          <div className="space-y-2">
            {myStrategies.map((s: any) => (
              <div key={s.id} className="bg-gray-800 rounded-lg p-3 text-sm font-medium">{s.name}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
