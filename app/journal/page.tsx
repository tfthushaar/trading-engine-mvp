"use client";
import { Fragment, useEffect, useMemo, useState } from "react";
import { Download, Plus, Trash2 } from "lucide-react";
import { Bars, LineChart } from "@/components/charts";
import { Card, Change, Disclaimer, Empty, ErrorBox, Field, Meter, PageHeader, Seg, SignalPill, SourceTag, Spinner, Stat, SymbolLink } from "@/components/ui";
import { api } from "@/lib/api";
import { downloadFile, num, pct, rate, toCSV } from "@/lib/format";
import { KEYS, useStored } from "@/lib/store";

interface Entry {
  id: string;
  symbol: string;
  direction: "long" | "short";
  entry_price: number;
  stop_loss: number;
  target: number;
  size: number;
  entry_date: string;
  exit_price?: number | null;
  exit_date?: string | null;
  emotion_entry: string;
  emotion_exit?: string;
  rule_followed: boolean | null;
  notes?: string;
  model_prob?: number | null;
  model_signal?: string | null;
  review?: string | null;
}
const EMOTIONS = ["calm", "confident", "anxious", "fomo", "revenge", "bored"];
const pnlPct = (e: Entry) => (e.exit_price == null ? null : ((e.exit_price / e.entry_price - 1) * 100) * (e.direction === "short" ? -1 : 1));
const nowLocal = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);

function LogForm({ onSave }: { onSave: (e: Entry) => void }) {
  const [f, setF] = useState({ symbol: "", direction: "long" as "long" | "short", entry_price: "", stop_loss: "", target: "", size: "", entry_date: nowLocal(), emotion_entry: "calm", rule_followed: "yes", notes: "", exit_price: "", exit_date: "" });
  const [saving, setSaving] = useState(false);
  const submit = async () => {
    if (!f.symbol || !Number(f.entry_price)) return;
    setSaving(true);
    let model_prob = null;
    let model_signal = null;
    try {
      const s = await api(`/api/signals/${encodeURIComponent(f.symbol)}?lookback=20`);
      model_prob = s.prob_up;
      model_signal = s.signal;
    } catch {
      /* model view unavailable for this symbol */
    }
    onSave({
      id: Math.random().toString(36).slice(2, 10), symbol: f.symbol.toUpperCase(), direction: f.direction, entry_price: +f.entry_price, stop_loss: +f.stop_loss, target: +f.target,
      size: +f.size || 0, entry_date: f.entry_date, exit_price: f.exit_price ? +f.exit_price : null, exit_date: f.exit_price ? f.exit_date || nowLocal() : null,
      emotion_entry: f.emotion_entry, rule_followed: f.rule_followed === "yes" ? true : f.rule_followed === "no" ? false : null, notes: f.notes, model_prob, model_signal,
    });
    setF({ ...f, symbol: "", entry_price: "", stop_loss: "", target: "", size: "", notes: "", exit_price: "", exit_date: "" });
    setSaving(false);
  };
  return (
    <form className="grid grid-cols-2 gap-2" onSubmit={(e) => (e.preventDefault(), submit())}>
      <Field label="Symbol"><input className="input font-semibold" value={f.symbol} onChange={(e) => setF({ ...f, symbol: e.target.value.toUpperCase() })} /></Field>
      <Field label="Direction"><Seg value={f.direction} onChange={(v) => setF({ ...f, direction: v })} options={[{ value: "long", label: "Long" }, { value: "short", label: "Short" }]} /></Field>
      <Field label="Entry"><input className="input num" inputMode="decimal" value={f.entry_price} onChange={(e) => setF({ ...f, entry_price: e.target.value })} /></Field>
      <Field label="Size"><input className="input num" inputMode="decimal" value={f.size} onChange={(e) => setF({ ...f, size: e.target.value })} /></Field>
      <Field label="Stop"><input className="input num" inputMode="decimal" value={f.stop_loss} onChange={(e) => setF({ ...f, stop_loss: e.target.value })} /></Field>
      <Field label="Target"><input className="input num" inputMode="decimal" value={f.target} onChange={(e) => setF({ ...f, target: e.target.value })} /></Field>
      <Field label="Entry time"><input className="input" type="datetime-local" value={f.entry_date} onChange={(e) => setF({ ...f, entry_date: e.target.value })} /></Field>
      <Field label="Feeling at entry"><select className="select" value={f.emotion_entry} onChange={(e) => setF({ ...f, emotion_entry: e.target.value })}>{EMOTIONS.map((x) => <option key={x}>{x}</option>)}</select></Field>
      <Field label="Followed my rules"><select className="select" value={f.rule_followed} onChange={(e) => setF({ ...f, rule_followed: e.target.value })}><option value="yes">Yes</option><option value="no">No</option><option value="unsure">Not sure</option></select></Field>
      <Field label="Exit (optional)"><input className="input num" inputMode="decimal" placeholder="Still open" value={f.exit_price} onChange={(e) => setF({ ...f, exit_price: e.target.value })} /></Field>
      <Field label="Notes" className="col-span-2"><textarea className="input" rows={2} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} placeholder="Thesis, context, what you were thinking" /></Field>
      <button className="btn btn-primary col-span-2" disabled={saving}>{saving ? <Spinner /> : <Plus size={12} />}Log trade</button>
      <p className="faint col-span-2 text-[10.5px]">The neural ensemble's reading at entry is saved with the trade so you can compare your calls with the model's.</p>
    </form>
  );
}

export default function JournalPage() {
  const [entries, setEntries] = useStored<Entry[]>(KEYS.journal, []);
  const [closing, setClosing] = useState<string | null>(null);
  const [exitPx, setExitPx] = useState("");
  const [exitEmotion, setExitEmotion] = useState("calm");
  const [report, setReport] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<string | null>(null);
  const key = useMemo(() => JSON.stringify(entries.map((e) => [e.id, e.exit_price, e.rule_followed])), [entries]);
  useEffect(() => {
    if (!entries.length) return setReport(null);
    const id = setTimeout(() => {
      api("/api/journal/analyze", { body: { entries, coach: true } }).then(setReport).catch((e) => setErr(e.message));
    }, 400);
    return () => clearTimeout(id);
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  const closeTrade = async (e: Entry) => {
    if (!Number(exitPx)) return;
    const updated: Entry = { ...e, exit_price: +exitPx, exit_date: nowLocal(), emotion_exit: exitEmotion };
    setEntries(entries.map((x) => (x.id === e.id ? updated : x)));
    setClosing(null);
    setExitPx("");
    setReviewing(e.id);
    try {
      const r = await api("/api/journal/review", { body: { entry: updated } });
      setEntries((prev) => prev.map((x) => (x.id === e.id ? { ...x, review: r.review } : x)));
    } finally {
      setReviewing(null);
    }
  };
  const sorted = [...entries].sort((a, b) => b.entry_date.localeCompare(a.entry_date));
  return (
    <div>
      <PageHeader
        title="Journal"
        subtitle="Log trades, track emotions and rule adherence, and see how your decisions compare with the neural model. Stored only in this browser."
        right={<button className="btn" disabled={!entries.length} onClick={() => downloadFile("journal.csv", toCSV(entries as any), "text/csv")}><Download size={12} />Export</button>}
      />
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[340px_1fr]">
        <div className="space-y-3">
          <Card title="Log a trade"><LogForm onSave={(e) => setEntries([e, ...entries])} /></Card>
          {report?.score != null && (
            <Card title="Discipline" right={report.coaching && <SourceTag source={report.coaching.source} note={report.coaching.note} />}>
              <div className="flex items-center gap-3">
                <div className="grid h-12 w-12 place-items-center rounded-xl bg-inv text-[22px] font-bold text-inv-fg">{report.grade}</div>
                <div className="flex-1"><div className="num text-[18px] font-semibold">{report.score}/100</div><Meter value={report.score} max={100} /></div>
              </div>
              <div className="faint mt-1 text-[11px]">Rule adherence {rate(report.rule_adherence)}</div>
              {report.coaching && <p className="mt-2 rounded-lg bg-bg-2 px-2.5 py-2 text-[12.5px] leading-relaxed">{report.coaching.text}</p>}
            </Card>
          )}
        </div>
        <div className="min-w-0 space-y-3">
          <ErrorBox error={err} />
          {report?.stats && (
            <div className="grid grid-cols-2 gap-3 rounded-[10px] border border-line bg-panel p-3 sm:grid-cols-4 xl:grid-cols-8">
              <Stat label="Trades" value={report.stats.total} sub={`${report.stats.open} open`} strong />
              <Stat label="Win rate" value={rate(report.stats.win_rate)} />
              <Stat label="Avg win" value={pct(report.stats.avg_win_pct)} />
              <Stat label="Avg loss" value={pct(report.stats.avg_loss_pct)} />
              <Stat label="Expectancy" value={pct(report.stats.expectancy_pct)} sub="per trade" />
              <Stat label="Profit factor" value={num(report.stats.profit_factor)} />
              <Stat label="Best" value={pct(report.stats.best_pct)} />
              <Stat label="Worst" value={pct(report.stats.worst_pct)} />
            </div>
          )}
          {report?.score != null && (
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
              <Card title="You vs the neural model" bodyClass="p-0">
                {report.vs_model?.length ? (
                  <table className="tbl"><thead><tr><th>Trades</th><th className="r">n</th><th className="r">Win rate</th><th className="r">Avg</th></tr></thead>
                    <tbody>{report.vs_model.map((g: any) => <tr key={g.group}><td className="capitalize">{g.group}</td><td className="r num">{g.trades}</td><td className="r num">{rate(g.win_rate)}</td><td className="r"><Change value={g.avg_pct} icon={false} /></td></tr>)}</tbody></table>
                ) : <Empty title="Close trades to compare">Each trade records the model's signal at entry.</Empty>}
              </Card>
              <Card title="Behavioural patterns">
                {report.patterns.length === 0 ? <p className="muted text-[12px]">No problematic patterns detected.</p> : (
                  <div className="space-y-1.5">{report.patterns.map((p: any) => (
                    <div key={p.pattern} className="text-[12px]"><div className="flex items-center justify-between"><b className="capitalize">{p.pattern.replace(/_/g, " ")}</b><span className={`pill ${p.severity === "high" ? "pill-solid" : p.severity === "medium" ? "pill-outline" : "pill-soft"}`}>{p.severity}</span></div><p className="muted leading-snug">{p.description}</p></div>
                  ))}</div>
                )}
              </Card>
              <Card title="Feeling vs outcome" bodyClass="p-0">
                {report.by_emotion?.length ? (
                  <table className="tbl"><thead><tr><th>Feeling</th><th className="r">n</th><th className="r">Win rate</th><th className="r">Avg</th></tr></thead>
                    <tbody>{report.by_emotion.map((g: any) => <tr key={g.emotion}><td className="capitalize">{g.emotion}</td><td className="r num">{g.trades}</td><td className="r num">{rate(g.win_rate)}</td><td className="r"><Change value={g.avg_pct} icon={false} /></td></tr>)}</tbody></table>
                ) : <Empty title="No closed trades yet" />}
              </Card>
              {report.equity_pct?.length > 1 && <Card title="Cumulative return (sum of trade %)" className="lg:col-span-2"><LineChart x={report.equity_pct.map((_: any, i: number) => i + 1)} series={[{ name: "Cumulative %", values: report.equity_pct, fill: true }]} height={140} yFormat={(v) => `${v.toFixed(1)}%`} legend={false} refLine={{ value: 0 }} /></Card>}
              {report.monthly?.length > 0 && <Card title="By month"><Bars labels={report.monthly.map((m: any) => m.month.slice(2))} values={report.monthly.map((m: any) => m.return_pct)} format={(v) => v.toFixed(1)} height={140} /></Card>}
            </div>
          )}
          <Card title={`Trades (${entries.length})`} bodyClass="p-0">
            {!entries.length ? <Empty title="Your journal is empty">Log your first trade on the left. Closing a trade generates an AI post-trade review.</Empty> : (
              <div className="overflow-x-auto">
                <table className="tbl">
                  <thead><tr><th>Date</th><th>Symbol</th><th>Side</th><th className="r">Entry</th><th className="r">Stop / target</th><th className="r">Exit</th><th className="r">Return</th><th>Feeling</th><th>Rules</th><th>Model at entry</th><th /></tr></thead>
                  <tbody>
                    {sorted.map((e) => (
                      <Fragment key={e.id}>
                        <tr>
                          <td className="num faint">{e.entry_date.replace("T", " ")}</td>
                          <td><SymbolLink symbol={e.symbol} /></td>
                          <td className="capitalize">{e.direction}</td>
                          <td className="r num">{num(e.entry_price)}</td>
                          <td className="r num faint">{num(e.stop_loss)} / {num(e.target)}</td>
                          <td className="r num">
                            {e.exit_price != null ? num(e.exit_price) : closing === e.id ? (
                              <span className="inline-flex gap-1"><input autoFocus className="input num h-6 w-20" value={exitPx} onChange={(x) => setExitPx(x.target.value)} placeholder="Exit" /><select className="select h-6 w-auto" value={exitEmotion} onChange={(x) => setExitEmotion(x.target.value)}>{EMOTIONS.map((m) => <option key={m}>{m}</option>)}</select><button className="btn btn-sm btn-primary" onClick={() => closeTrade(e)}>Close</button></span>
                            ) : <button className="btn btn-sm" onClick={() => setClosing(e.id)}>Close trade</button>}
                          </td>
                          <td className="r"><Change value={pnlPct(e)} icon={false} /></td>
                          <td className="capitalize">{e.emotion_entry}</td>
                          <td>{e.rule_followed == null ? "--" : e.rule_followed ? "Yes" : "No"}</td>
                          <td>{e.model_prob != null ? <span className="inline-flex items-center gap-1.5"><span className="num">{e.model_prob.toFixed(3)}</span><SignalPill signal={e.model_signal} /></span> : <span className="faint">--</span>}</td>
                          <td className="w-6"><button className="btn-ghost rounded p-1" onClick={() => setEntries(entries.filter((x) => x.id !== e.id))}><Trash2 size={11} /></button></td>
                        </tr>
                        {(e.review || reviewing === e.id || e.notes) && (
                          <tr><td /><td colSpan={10} className="!whitespace-normal pb-2 text-[12px]">
                            {e.notes && <p className="muted"><span className="eyebrow mr-1">Notes</span>{e.notes}</p>}
                            {reviewing === e.id && <p className="faint flex items-center gap-1"><Spinner size={11} />Writing post-trade review</p>}
                            {e.review && <p className="mt-0.5"><span className="eyebrow mr-1">Review</span>{e.review}</p>}
                          </td></tr>
                        )}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      </div>
      <Disclaimer>Your journal never leaves this browser except when sent for analysis; it is not stored on the server.</Disclaimer>
    </div>
  );
}
