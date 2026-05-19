"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Plus, TrendingUp, TrendingDown, Brain, CheckCircle, XCircle } from "lucide-react";

export default function JournalPage() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    ticker:"", direction:"long", entry_price:"", stop_loss:"", target:"",
    position_size:"", entry_date: new Date().toISOString().slice(0,16),
    emotion_entry:"calm", rule_followed:"true", notes:"",
  });

  const { data: entries = [], isLoading } = useQuery({
    queryKey: ["journal"],
    queryFn: () => api.get("/api/journal/entries").then(r => r.data),
  });
  const { data: report } = useQuery({
    queryKey: ["behavioral-report"],
    queryFn: () => api.get("/api/journal/behavioral-report").then(r => r.data),
  });

  const addEntry = useMutation({
    mutationFn: (data: any) => api.post("/api/journal/entries", data),
    onSuccess: () => { qc.invalidateQueries({queryKey:["journal"]}); qc.invalidateQueries({queryKey:["behavioral-report"]}); setShowForm(false); },
  });

  const winRate = entries.length > 0
    ? Math.round(entries.filter((e:any) => (e.pnl_percent??0) > 0).length / entries.filter((e:any) => e.pnl_percent != null).length * 100)
    : null;

  const gradeColor = (g: string) => ({A:"text-green-400",B:"text-yellow-400",C:"text-orange-400",D:"text-red-400"}[g] ?? "text-[#888]");

  return (
    <div className="max-w-[1400px] mx-auto px-4 py-8 space-y-6 fade-in">
      <div className="flex items-center justify-between">
        <div><h1 className="section-title">Trade Journal</h1><p className="section-subtitle">Track every trade. Learn from each one.</p></div>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary flex items-center gap-2"><Plus size={15} />Log Trade</button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label:"Total Trades", value: entries.length || "—" },
          { label:"Win Rate", value: winRate != null ? `${winRate}%` : "—", pos: winRate != null ? winRate >= 50 : null },
          { label:"Discipline Score", value: report?.score ?? "—", pos: report?.score ? report.score >= 70 : null },
          { label:"Grade", value: report?.grade ?? "—" },
        ].map(({label,value,pos}) => (
          <div key={label} className="card-sm">
            <p className="label mb-1">{label}</p>
            <p className={`text-2xl font-bold ${pos === true ? "positive" : pos === false ? "negative" : "text-white"}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Log Form */}
      {showForm && (
        <div className="card max-w-2xl">
          <p className="label mb-4">Log Trade</p>
          <div className="grid grid-cols-2 gap-3">
            {[{k:"ticker",label:"Ticker",ph:"AAPL"},{k:"entry_price",label:"Entry Price",ph:"185.00"},{k:"stop_loss",label:"Stop Loss",ph:"180.00"},{k:"target",label:"Target",ph:"198.00"},{k:"position_size",label:"Position Size",ph:"100"}].map(({k,label,ph}) => (
              <div key={k}><label className="block text-xs text-[#888] mb-1">{label}</label>
                <input className="input" placeholder={ph} value={(form as any)[k]} onChange={e => setForm(f=>({...f,[k]:e.target.value}))} /></div>
            ))}
            <div><label className="block text-xs text-[#888] mb-1">Direction</label>
              <select className="input" value={form.direction} onChange={e => setForm(f=>({...f,direction:e.target.value}))}>
                <option value="long">Long</option><option value="short">Short</option>
              </select></div>
            <div><label className="block text-xs text-[#888] mb-1">Emotion at Entry</label>
              <select className="input" value={form.emotion_entry} onChange={e => setForm(f=>({...f,emotion_entry:e.target.value}))}>
                {["calm","confident","anxious","fomo","revenge"].map(e => <option key={e} value={e}>{e.charAt(0).toUpperCase()+e.slice(1)}</option>)}
              </select></div>
            <div><label className="block text-xs text-[#888] mb-1">Rules Followed?</label>
              <select className="input" value={form.rule_followed} onChange={e => setForm(f=>({...f,rule_followed:e.target.value}))}>
                <option value="true">Yes</option><option value="false">No</option>
              </select></div>
          </div>
          <div className="mt-3"><label className="block text-xs text-[#888] mb-1">Notes</label>
            <textarea className="input h-20 resize-none" placeholder="Trade rationale, market context, emotions..." value={form.notes} onChange={e => setForm(f=>({...f,notes:e.target.value}))} /></div>
          <button onClick={() => addEntry.mutate({...form,entry_price:+form.entry_price,stop_loss:+form.stop_loss,target:+form.target,position_size:+form.position_size,entry_date:new Date(form.entry_date).toISOString(),rule_followed:form.rule_followed==="true"})} disabled={addEntry.isPending||!form.ticker} className="btn-primary w-full mt-4">
            {addEntry.isPending ? "Logging..." : "Save Trade"}
          </button>
        </div>
      )}

      {/* AI Report */}
      {report?.ai_report && (
        <div className="card border-l-2 border-white/10">
          <div className="flex items-center gap-2 mb-3"><Brain size={14} /><p className="label">AI Monthly Review</p></div>
          <div className="ai-box mb-3">{report.ai_report}</div>
          {report.behavioral_patterns?.length > 0 && (
            <div className="space-y-2">
              {report.behavioral_patterns.map((p:any,i:number) => (
                <div key={i} className={`text-xs px-3 py-2 rounded-xl flex items-start gap-2 ${p.severity==="high"?"alert-high":p.severity==="medium"?"alert-medium":"alert-low"}`}>
                  <span className="font-semibold capitalize shrink-0">{p.pattern.replace(/_/g," ")}:</span>
                  <span className="text-[#aaa]">{p.description}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Trade list */}
      <div>
        <p className="label mb-3">Trade History</p>
        {isLoading ? (
          <div className="space-y-2">{Array.from({length:4}).map((_,i) => <div key={i} className="skeleton h-16 rounded-2xl" />)}</div>
        ) : entries.length === 0 ? (
          <div className="card text-center py-16"><p className="text-[#555] text-sm">No trades logged yet. Start by logging your first trade.</p></div>
        ) : (
          <div className="space-y-2">
            {entries.map((e:any) => (
              <div key={e.id} className="card-sm flex items-center gap-4 hover:border-[#444] transition-colors">
                <div className={e.direction==="long" ? "positive" : "negative"}>{e.direction==="long" ? <TrendingUp size={18} /> : <TrendingDown size={18} />}</div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-sm">{e.ticker}</div>
                  <div className="text-xs text-[#555]">{new Date(e.entry_date).toLocaleDateString()}</div>
                </div>
                {e.pnl_percent != null && (
                  <div className={`font-semibold tabular-nums ${e.pnl_percent>=0?"positive":"negative"}`}>
                    {e.pnl_percent>=0?"+":""}{e.pnl_percent?.toFixed(2)}%
                  </div>
                )}
                <div>{e.rule_followed === true ? <CheckCircle size={14} className="text-green-600" /> : e.rule_followed === false ? <XCircle size={14} className="text-red-600" /> : null}</div>
                {e.ai_review && <span className="badge-neutral text-[10px]">AI reviewed</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
