"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState } from "react";
import { Plus, Briefcase, TrendingUp, Shield, GitMerge } from "lucide-react";

export default function PortfolioPage() {
  const qc = useQueryClient();
  const [addForm, setAddForm] = useState({ ticker: "", quantity: "", avg_cost: "" });
  const [showAdd, setShowAdd] = useState(false);

  const { data: analysis, isLoading } = useQuery({
    queryKey: ["portfolio-analysis"],
    queryFn: () => api.get("/api/portfolio/analysis").then(r => r.data),
  });
  const { data: risk } = useQuery({
    queryKey: ["portfolio-risk"],
    queryFn: () => api.get("/api/portfolio/risk").then(r => r.data),
  });
  const { data: corr } = useQuery({
    queryKey: ["portfolio-correlation"],
    queryFn: () => api.get("/api/portfolio/correlation").then(r => r.data),
  });

  const addPosition = useMutation({
    mutationFn: (data: any) => api.post("/api/portfolio/positions", data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["portfolio-analysis"] }); qc.invalidateQueries({ queryKey: ["portfolio-risk"] }); setShowAdd(false); setAddForm({ ticker: "", quantity: "", avg_cost: "" }); },
  });

  const scoreColor = (s: number) => s >= 70 ? "text-green-400" : s >= 50 ? "text-yellow-400" : "text-red-400";

  return (
    <div className="max-w-[1400px] mx-auto px-4 py-8 space-y-6 fade-in">
      <div className="flex items-center justify-between">
        <div><h1 className="section-title">Portfolio Brain</h1><p className="section-subtitle">Risk-aware portfolio analysis powered by AI</p></div>
        <button onClick={() => setShowAdd(!showAdd)} className="btn-primary flex items-center gap-2"><Plus size={15} />Add Position</button>
      </div>

      {showAdd && (
        <div className="card max-w-md space-y-3">
          <p className="label">Add Position</p>
          {[{k:"ticker",label:"Ticker",ph:"AAPL"},{k:"quantity",label:"Quantity",ph:"100"},{k:"avg_cost",label:"Avg Cost ($)",ph:"185.00"}].map(({k,label,ph}) => (
            <div key={k}><label className="block text-xs text-[#888] mb-1">{label}</label>
              <input className="input" placeholder={ph} value={(addForm as any)[k]} onChange={e => setAddForm(f=>({...f,[k]:e.target.value}))} /></div>
          ))}
          <button disabled={addPosition.isPending || !addForm.ticker} onClick={() => addPosition.mutate({ticker:addForm.ticker.toUpperCase(),quantity:+addForm.quantity,avg_cost:+addForm.avg_cost})} className="btn-primary w-full">
            {addPosition.isPending ? "Adding..." : "Add Position"}
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">{Array.from({length:4}).map((_,i) => <div key={i} className="skeleton h-20 rounded-2xl" />)}</div>
      ) : analysis?.message ? (
        <div className="card text-center py-16"><Briefcase size={32} className="mx-auto mb-3 text-[#555]" /><p className="text-[#555] text-sm">No positions yet. Add positions to see AI portfolio analysis.</p></div>
      ) : analysis ? (
        <>
          {/* Score row */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label:"Health Score", value: analysis.health_score, colored: true },
              { label:"Total Value", value: `$${(analysis.total_value||0).toLocaleString()}` },
              { label:"Positions", value: analysis.position_count },
              { label:"Beta", value: risk?.beta_vs_spy?.toFixed(2) ?? "—" },
            ].map(({label,value,colored}) => (
              <div key={label} className="card-sm">
                <p className="label mb-1">{label}</p>
                <p className={`text-2xl font-bold tabular-nums ${colored && typeof value === "number" ? scoreColor(value) : "text-white"}`}>{value}</p>
              </div>
            ))}
          </div>

          {/* AI Narrative */}
          {analysis.ai_narrative && (
            <div className="card">
              <div className="flex items-center gap-2 mb-3"><Shield size={14} /><p className="label">AI Portfolio Assessment</p></div>
              <div className="ai-box">{analysis.ai_narrative}</div>
            </div>
          )}

          {/* Sector + Correlation */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="card">
              <div className="flex items-center gap-2 mb-4"><TrendingUp size={14} /><p className="label">Sector Exposure</p></div>
              <div className="space-y-2">
                {Object.entries(analysis.sector_weights||{}).sort(([,a],[,b]) => (b as number)-(a as number)).map(([sector,pct]) => (
                  <div key={sector}>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-[#aaa]">{sector}</span>
                      <span className="font-semibold tabular-nums">{(pct as number).toFixed(1)}%</span>
                    </div>
                    <div className="h-1.5 bg-[#1a1a1a] rounded-full overflow-hidden">
                      <div className="h-full bg-white rounded-full transition-all" style={{width:`${pct}%`}} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="card">
              <div className="flex items-center gap-2 mb-4"><GitMerge size={14} /><p className="label">Risk Metrics</p></div>
              {risk ? (
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { label:"VaR 95% (1-day)", value:`${risk.var_95_pct?.toFixed(2)}%`, neg:true },
                    { label:"Max Drawdown", value:`${risk.max_drawdown_pct?.toFixed(2)}%`, neg:true },
                    { label:"CVaR 95%", value:`${risk.cvar_95_pct?.toFixed(2)}%`, neg:true },
                    { label:"Annual Volatility", value:`${risk.annualized_volatility_pct?.toFixed(2)}%` },
                  ].map(({label,value,neg}) => (
                    <div key={label} className="bg-[#0f0f0f] rounded-xl p-3">
                      <p className="text-[10px] text-[#666] mb-1">{label}</p>
                      <p className={`text-sm font-semibold tabular-nums ${neg ? "negative" : "text-white"}`}>{value}</p>
                    </div>
                  ))}
                </div>
              ) : <div className="skeleton h-24 rounded-xl" />}
              {corr?.highest_correlation && (
                <div className="mt-3 p-3 rounded-xl bg-[#0f0f0f] border border-[#2a2a2a]">
                  <p className="text-[10px] text-[#666] mb-1">Highest Correlation</p>
                  <p className="text-sm font-medium">{corr.highest_correlation.pair.join(" ↔ ")}</p>
                  <p className={`text-xs mt-0.5 ${corr.highest_correlation.risk_level === "high" ? "negative" : "text-[#888]"}`}>
                    r = {corr.highest_correlation.correlation} · {corr.highest_correlation.risk_level} risk
                  </p>
                </div>
              )}
            </div>
          </div>

          <p className="text-[10px] text-[#3a3a3a] text-center">{analysis.disclaimer}</p>
        </>
      ) : null}
    </div>
  );
}
