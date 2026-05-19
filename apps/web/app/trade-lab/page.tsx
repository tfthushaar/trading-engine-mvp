"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { FlaskConical, Plus, Trash2, Play, Clock } from "lucide-react";

type Tab = "evaluate" | "build" | "backtest";

const INDICATORS = ["RSI","MACD","EMA","SMA","Volume","Bollinger Band","ATR","Stochastic"];
const OPERATORS  = ["is above","is below","crosses above","crosses below","is greater than","is less than"];

interface Rule { indicator:string; operator:string; value:string; }

export default function TradeLabPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("evaluate");

  // Evaluator
  const [evalForm, setEvalForm] = useState({ ticker:"", entry_price:"", stop_loss:"", target:"" });
  const [evalResult, setEvalResult] = useState<any>(null);
  const [evalLoading, setEvalLoading] = useState(false);

  // Builder
  const [stratName, setStratName] = useState("");
  const [entryRules, setEntryRules] = useState<Rule[]>([{ indicator:"RSI", operator:"is below", value:"30" }]);
  const [exitRules, setExitRules] = useState<Rule[]>([{ indicator:"RSI", operator:"is above", value:"60" }]);

  // Backtester
  const [backtestTaskId, setBacktestTaskId] = useState<string|null>(null);

  const { data: strategies } = useQuery({ queryKey:["my-strategies"], queryFn: () => api.get("/api/trade-lab/strategies").then(r=>r.data) });

  const saveStrategy = useMutation({
    mutationFn: (data:any) => api.post("/api/trade-lab/strategies", data),
    onSuccess: () => { qc.invalidateQueries({queryKey:["my-strategies"]}); setStratName(""); },
  });

  const { data: btStatus } = useQuery({
    queryKey: ["backtest-status", backtestTaskId],
    queryFn: () => api.get(`/api/trade-lab/backtest/${backtestTaskId}/status`).then(r=>r.data),
    enabled: !!backtestTaskId,
    refetchInterval: (data:any) => data?.status === "SUCCESS" ? false : 2500,
  });

  async function runEval() {
    setEvalLoading(true);
    try {
      const r = await api.post("/api/intelligence/trade/evaluate", {
        ticker: evalForm.ticker.toUpperCase(),
        entry_price: +evalForm.entry_price, stop_loss: +evalForm.stop_loss, target: +evalForm.target,
      });
      setEvalResult(r.data);
    } catch {} finally { setEvalLoading(false); }
  }

  const RuleRow = ({ rules, type }: { rules:Rule[]; type:"entry"|"exit" }) => {
    const setter = type==="entry" ? setEntryRules : setExitRules;
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-[#888] uppercase tracking-widest">{type} conditions</p>
          <button onClick={() => setter(r => [...r, {indicator:"RSI",operator:"is above",value:"50"}])} className="btn-ghost text-xs py-1 px-2">
            <Plus size={12} /> Add
          </button>
        </div>
        {rules.map((rule,i) => (
          <div key={i} className="flex gap-2 items-center">
            <select value={rule.indicator} onChange={e => setter(r => r.map((x,j) => j===i?{...x,indicator:e.target.value}:x))} className="input-sm flex-1">{INDICATORS.map(ind => <option key={ind}>{ind}</option>)}</select>
            <select value={rule.operator} onChange={e => setter(r => r.map((x,j) => j===i?{...x,operator:e.target.value}:x))} className="input-sm flex-1">{OPERATORS.map(op => <option key={op}>{op}</option>)}</select>
            <input type="text" value={rule.value} onChange={e => setter(r => r.map((x,j) => j===i?{...x,value:e.target.value}:x))} className="input-sm w-16" />
            <button onClick={() => setter(r => r.filter((_,j) => j!==i))} className="text-[#555] hover:text-red-400 transition-colors"><Trash2 size={13} /></button>
          </div>
        ))}
      </div>
    );
  };

  const gradeColor = (g:string) => ["A+","A"].includes(g) ? "text-green-400" : g==="B" ? "text-yellow-400" : "text-red-400";

  return (
    <div className="max-w-[1400px] mx-auto px-4 py-8 fade-in">
      <div className="mb-6">
        <h1 className="section-title">Trade Lab</h1>
        <p className="section-subtitle">Evaluate setups, build strategies, run backtests</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-[#111] border border-[#2a2a2a] rounded-xl p-1 w-fit">
        {([{id:"evaluate",label:"Evaluator"},{id:"build",label:"Builder"},{id:"backtest",label:"Backtester"}] as const).map(({id,label}) => (
          <button key={id} onClick={() => setTab(id)} className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${tab===id?"bg-white text-black":"text-[#888] hover:text-white"}`}>{label}</button>
        ))}
      </div>

      {tab === "evaluate" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="card space-y-4">
            <div className="flex items-center gap-2"><FlaskConical size={14}/><p className="label">Setup Evaluator</p></div>
            {[{k:"ticker",label:"Ticker",ph:"AAPL"},{k:"entry_price",label:"Entry Price",ph:"185.00"},{k:"stop_loss",label:"Stop Loss",ph:"180.00"},{k:"target",label:"Target",ph:"198.00"}].map(({k,label,ph}) => (
              <div key={k}><label className="block text-xs text-[#888] mb-1">{label}</label>
                <input className="input" placeholder={ph} value={(evalForm as any)[k]} onChange={e => setEvalForm(f=>({...f,[k]:e.target.value}))} /></div>
            ))}
            <button onClick={runEval} disabled={evalLoading||!evalForm.ticker} className="btn-primary w-full">{evalLoading?"Evaluating...":"Evaluate Trade"}</button>
          </div>
          {evalResult && (
            <div className="card space-y-4 fade-in">
              <div className="flex items-center justify-between">
                <div><span className={`text-5xl font-bold ${gradeColor(evalResult.grade)}`}>{evalResult.grade}</span><span className="text-[#555] text-xl ml-3">{evalResult.overall_score}/100</span></div>
                <div className="text-right"><div className="text-2xl font-bold">{evalResult.risk_reward?.risk_reward_ratio}:1</div><div className="text-xs text-[#555]">Risk/Reward</div></div>
              </div>
              <div className="ai-box">{evalResult.ai_assessment}</div>
              {evalResult.technical_analysis?.signals?.length>0 && <div><p className="label mb-2">Signals</p>{evalResult.technical_analysis.signals.map((s:string,i:number)=><div key={i} className="text-xs text-green-400 flex gap-2"><span>✓</span>{s}</div>)}</div>}
              {evalResult.risk_warnings?.length>0 && <div><p className="label mb-2">Warnings</p>{evalResult.risk_warnings.map((w:string,i:number)=><div key={i} className="text-xs text-yellow-500 flex gap-2"><span>⚠</span>{w}</div>)}</div>}
            </div>
          )}
        </div>
      )}

      {tab === "build" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 card space-y-5">
            <p className="label">No-Code Strategy Builder</p>
            <div><label className="block text-xs text-[#888] mb-1">Strategy Name</label><input className="input" placeholder="My RSI Strategy" value={stratName} onChange={e => setStratName(e.target.value)} /></div>
            <RuleRow rules={entryRules} type="entry" />
            <div className="divider" />
            <RuleRow rules={exitRules} type="exit" />
            <button onClick={() => saveStrategy.mutate({strategy_name:stratName,entry_conditions:entryRules.map(r=>({indicator:r.indicator,operator:r.operator,value:parseFloat(r.value)||r.value})),exit_conditions:exitRules.map(r=>({indicator:r.indicator,operator:r.operator,value:parseFloat(r.value)||r.value}))})} disabled={!stratName||saveStrategy.isPending} className="btn-primary">
              {saveStrategy.isPending?"Saving...":"Save Strategy"}
            </button>
            {saveStrategy.isSuccess && <p className="text-xs positive">Strategy saved!</p>}
          </div>
          <div className="card">
            <p className="label mb-3">My Strategies</p>
            {!strategies?.length ? <p className="text-xs text-[#555]">No strategies saved yet.</p> : (
              <div className="space-y-2">
                {strategies.map((s:any) => (
                  <div key={s.id} className="bg-[#0f0f0f] rounded-xl px-3 py-2.5 text-sm font-medium">{s.name}</div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "backtest" && (
        <div className="card max-w-xl space-y-4">
          <div className="flex items-center gap-2"><Play size={14}/><p className="label">Run Backtest</p></div>
          <div>
            <label className="block text-xs text-[#888] mb-1">Select Strategy</label>
            <select id="strat-select" className="input">
              <option value="">Choose strategy...</option>
              {strategies?.map((s:any) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <button onClick={async () => {
            const sel = (document.getElementById("strat-select") as HTMLSelectElement).value;
            if (!sel) return;
            const r = await api.post("/api/trade-lab/backtest", {strategy_id:sel,tickers:["AAPL","MSFT","NVDA"],start_date:"2023-01-01",end_date:"2024-12-31"});
            setBacktestTaskId(r.data.task_id);
          }} className="btn-primary flex items-center gap-2"><Play size={14}/>Run Backtest</button>
          {backtestTaskId && (
            <div className="bg-[#0f0f0f] rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <Clock size={13} className="text-[#555]" />
                <span className="text-xs text-[#888]">Status: <span className={btStatus?.status==="SUCCESS"?"positive":"text-yellow-400"}>{btStatus?.status ?? "Queued"}</span></span>
              </div>
              {btStatus?.result && (
                <div className="grid grid-cols-2 gap-3">
                  {Object.entries(btStatus.result).filter(([k]) => k !== "disclaimer" && k !== "strategy_id").map(([k,v]) => (
                    <div key={k} className="bg-[#111] rounded-lg p-2">
                      <p className="text-[10px] text-[#666] mb-0.5">{k.replace(/_/g," ")}</p>
                      <p className="text-sm font-semibold">{typeof v === "number" ? v.toFixed(3) : String(v)}</p>
                    </div>
                  ))}
                </div>
              )}
              {btStatus?.result?.disclaimer && <p className="text-[10px] text-[#3a3a3a] mt-3">{btStatus.result.disclaimer}</p>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
