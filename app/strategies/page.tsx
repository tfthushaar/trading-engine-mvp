"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { FlaskConical, Play, Plus, Trash2 } from "lucide-react";
import { Bars, Histogram, LineChart, TONES } from "@/components/charts";
import { EvaluatorView } from "@/components/evaluator";
import { PriceChart } from "@/components/PriceChart";
import { useResolvedTheme } from "@/components/shell";
import { Card, Change, Disclaimer, Empty, ErrorBox, Field, PageHeader, Seg, SourceTag, Spinner, Stat, SymbolLink } from "@/components/ui";
import { api, useAction, useApi } from "@/lib/api";
import { fpct, num, rate } from "@/lib/format";
import { useWatchlist } from "@/lib/store";

/* ---- Competition ---------------------------------------------------------------------------- */
function CompetitionTab() {
  const wl = useWatchlist();
  const [symbols, setSymbols] = useState(wl.list.join(","));
  const edited = useRef(false);
  const listKey = wl.list.join(",");
  useEffect(() => {
    if (!edited.current) setSymbols(listKey); // the saved watchlist only becomes readable after hydration
  }, [listKey]);
  const [period, setPeriod] = useState("2y");
  const [slip, setSlip] = useState(2);
  const comp = useAction((body: any, signal) => api("/api/strategies/competition", { body, signal }));
  const r = comp.data;
  return (
    <div className="grid grid-cols-1 gap-3 xl:grid-cols-[320px_1fr]">
      <Card title="Five strategy agents">
        <div className="space-y-2">
          <Field label="Symbols" hint={`Defaults to your "${wl.active}" watchlist`}><textarea className="input" rows={3} value={symbols} onChange={(e) => { edited.current = true; setSymbols(e.target.value.toUpperCase()); }} /></Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Period"><select className="select" value={period} onChange={(e) => setPeriod(e.target.value)}>{["1y", "2y", "5y", "10y"].map((p) => <option key={p}>{p}</option>)}</select></Field>
            <Field label="Slippage (bps)"><input className="input num" type="number" value={slip} onChange={(e) => setSlip(Number(e.target.value))} /></Field>
          </div>
          <button className="btn btn-primary w-full" disabled={comp.running} onClick={() => comp.run({ symbols: symbols.split(/[\s,]+/).filter(Boolean), period, interval: "1d", cost_bps: 5, slippage_bps: slip })}>{comp.running ? <Spinner /> : <Play size={13} />}Run competition</button>
          <p className="faint text-[10.5px]">RSI mean reversion, EMA trend, Bollinger breakout, MACD momentum and volume-price agents each backtest every symbol with 5 bps commission plus slippage, ranked by Sharpe.</p>
          <Link href="/lab?tab=arena" className="btn w-full"><FlaskConical size={13} />Pit them against neural networks</Link>
        </div>
      </Card>
      <div className="min-w-0 space-y-3">
        <ErrorBox error={comp.error} />
        {!r && !comp.running && <Card><Empty title="Which style fits your symbols?">Run the competition to see which rule family wins on each symbol and overall.</Empty></Card>}
        {comp.running && <Card><div className="flex items-center gap-2 text-[12px]"><Spinner />Agents are backtesting...</div></Card>}
        {r && (
          <>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              <Card title="Wins by strategy" right={<span className="faint text-[11px]">{r.results.length} symbols · {r.cost_bps} bps all-in</span>}>
                <Bars labels={Object.keys(r.win_counts).map((k) => k.split(" ")[0])} values={Object.values(r.win_counts) as number[]} format={(v) => String(v)} height={150} />
                <div className="mt-1 text-[12px]">Overall leader: <b>{r.overall_best ?? "none"}</b></div>
                {r.skipped?.length > 0 && <div className="faint mt-1 text-[11px]">Skipped: {r.skipped.map((x: any) => `${x.symbol} (${x.reason})`).join(", ")}</div>}
              </Card>
              <Card title="Coach" right={<SourceTag source={r.interpretation?.source} note={r.interpretation?.note} />}><p className="text-[12.5px] leading-relaxed">{r.interpretation?.text}</p></Card>
            </div>
            <Card title="Per symbol" bodyClass="p-0">
              <table className="tbl">
                <thead><tr><th>Symbol</th><th>Winner</th><th className="r">Winner Sharpe</th><th className="r">Buy and hold Sharpe</th><th className="r">Winner return</th><th>All five (Sharpe)</th></tr></thead>
                <tbody>
                  {r.results.map((x: any) => (
                    <tr key={x.symbol}>
                      <td><SymbolLink symbol={x.symbol} /></td>
                      <td className="font-medium">{x.winner}</td>
                      <td className="r num font-semibold">{num(x.ranking[0].sharpe)}</td>
                      <td className="r num muted">{num(x.buy_hold.sharpe)}</td>
                      <td className="r"><Change value={x.ranking[0].total_return * 100} icon={false} /></td>
                      <td className="faint text-[11px]">{x.note ? `${x.note} ` : ""}{x.ranking.map((s: any) => `${s.name.split(" ")[0]} ${num(s.sharpe, 1)}`).join(" · ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}

/* ---- Rule builder ---------------------------------------------------------------------------- */
interface Operand { kind: string; period?: number; value?: number }
interface Cond { left: Operand; op: string; right: Operand }
const PRESETS: Record<string, { entry: Cond[]; exit: Cond[]; sl?: number; tp?: number }> = {
  "Golden cross": { entry: [{ left: { kind: "sma", period: 50 }, op: "crosses_above", right: { kind: "sma", period: 200 } }], exit: [{ left: { kind: "sma", period: 50 }, op: "crosses_below", right: { kind: "sma", period: 200 } }] },
  "Trend pullback": { entry: [{ left: { kind: "price" }, op: ">", right: { kind: "sma", period: 200 } }, { left: { kind: "rsi", period: 14 }, op: "<", right: { kind: "value", value: 40 } }], exit: [{ left: { kind: "rsi", period: 14 }, op: ">", right: { kind: "value", value: 65 } }], sl: 8 },
  "RSI dip": { entry: [{ left: { kind: "rsi", period: 14 }, op: "crosses_above", right: { kind: "value", value: 30 } }], exit: [{ left: { kind: "rsi", period: 14 }, op: ">", right: { kind: "value", value: 70 } }], sl: 10 },
  "MACD cross": { entry: [{ left: { kind: "macd" }, op: "crosses_above", right: { kind: "macd_signal" } }], exit: [{ left: { kind: "macd" }, op: "crosses_below", right: { kind: "macd_signal" } }] },
  "Bollinger breakout": { entry: [{ left: { kind: "price" }, op: "crosses_above", right: { kind: "bb_upper", period: 20 } }, { left: { kind: "volume_ratio", period: 20 }, op: ">", right: { kind: "value", value: 1.3 } }], exit: [{ left: { kind: "price" }, op: "crosses_below", right: { kind: "sma", period: 20 } }], sl: 6, tp: 15 },
};

function OperandInput({ v, onChange, catalog }: { v: Operand; onChange: (o: Operand) => void; catalog: any }) {
  const meta = catalog?.operands?.[v.kind];
  return (
    <div className="flex min-w-0 gap-1">
      <select className="select w-auto min-w-0 flex-1" value={v.kind} onChange={(e) => onChange({ kind: e.target.value, period: catalog?.operands?.[e.target.value]?.default, value: e.target.value === "value" ? 50 : undefined })}>
        {Object.entries(catalog?.operands ?? {}).map(([k, o]: any) => <option key={k} value={k}>{o.label}</option>)}
      </select>
      {v.kind === "value" && <input className="input num w-16" type="number" step="any" value={v.value ?? 0} onChange={(e) => onChange({ ...v, value: Number(e.target.value) })} />}
      {meta?.period && <input className="input num w-14" type="number" title="Period" value={v.period ?? meta.default} onChange={(e) => onChange({ ...v, period: Number(e.target.value) })} />}
    </div>
  );
}

function CondRows({ title, rows, setRows, catalog, joiner }: { title: string; rows: Cond[]; setRows: (r: Cond[]) => void; catalog: any; joiner: string }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between"><span className="label mb-0">{title}</span><button type="button" className="btn btn-sm btn-ghost" onClick={() => setRows([...rows, { left: { kind: "price" }, op: ">", right: { kind: "sma", period: 50 } }])}><Plus size={11} />Add</button></div>
      <div className="space-y-1.5">
        {rows.map((c, i) => (
          <div key={i}>
            {i > 0 && <div className="faint py-0.5 text-center text-[10px] font-semibold uppercase">{joiner}</div>}
            <div className="grid grid-cols-[1fr_auto] gap-1 rounded-lg border border-line p-1.5">
              <div className="space-y-1">
                <OperandInput v={c.left} catalog={catalog} onChange={(o) => setRows(rows.map((x, j) => (j === i ? { ...x, left: o } : x)))} />
                <select className="select" value={c.op} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, op: e.target.value } : x)))}>
                  {Object.entries(catalog?.operators ?? {}).map(([k, l]: any) => <option key={k} value={k}>{l}</option>)}
                </select>
                <OperandInput v={c.right} catalog={catalog} onChange={(o) => setRows(rows.map((x, j) => (j === i ? { ...x, right: o } : x)))} />
              </div>
              <button type="button" className="btn-ghost self-start rounded p-1" onClick={() => setRows(rows.filter((_, j) => j !== i))}><Trash2 size={12} /></button>
            </div>
          </div>
        ))}
        {!rows.length && <div className="faint rounded-lg border border-dashed border-line-2 px-2 py-2 text-center text-[11px]">No conditions</div>}
      </div>
    </div>
  );
}

const toTs = (d: string) => {
  const [date, time] = d.split(" ");
  const [y, m, dd] = date.split("-").map(Number);
  const [hh, mm] = (time ?? "00:00").split(":").map(Number);
  return Date.UTC(y, m - 1, dd, hh, mm) / 1000;
};

function BuilderTab() {
  const { data: catalog } = useApi<any>("/api/strategies", { staleMs: 86_400_000 });
  const theme = useResolvedTheme();
  const [symbol, setSymbol] = useState("SPY");
  const [interval, setIntervalV] = useState("1d");
  const [period, setPeriod] = useState("5y");
  const [entry, setEntry] = useState<Cond[]>(PRESETS["Trend pullback"].entry);
  const [exit, setExit] = useState<Cond[]>(PRESETS["Trend pullback"].exit);
  const [sl, setSl] = useState(8);
  const [tp, setTp] = useState(0);
  const [cost, setCost] = useState(5);
  const bt = useAction((body: any, signal) => api("/api/strategies/backtest", { body, signal }));
  const r = bt.data;
  const chartRange = r ? (r.interval === "1d" ? (["1y", "2y", "5y", "10y", "max"].includes(r.period) ? r.period : "5y") : r.period) : null;
  const { data: chart, error: chartError } = useApi<any>(r ? `/api/market/chart/${encodeURIComponent(r.symbol)}?range=${chartRange}&interval=${r.interval}` : null, { staleMs: 600_000 });
  const markers = useMemo(() => r?.trades?.flatMap((t: any) => [{ t: toTs(t.entry), kind: "entry" as const }, { t: toTs(t.exit), kind: "exit" as const }]) ?? [], [r]);
  const periods: string[] = catalog?.intervals?.[interval] ?? [];
  const applyPreset = (name: string) => {
    const p = PRESETS[name];
    setEntry(p.entry);
    setExit(p.exit);
    setSl(p.sl ?? 0);
    setTp(p.tp ?? 0);
  };
  return (
    <div className="grid grid-cols-1 gap-3 xl:grid-cols-[360px_1fr]">
      <Card title="Strategy" right={<select className="select h-6 w-auto text-[12px]" value="" onChange={(e) => e.target.value && applyPreset(e.target.value)}><option value="">Presets</option>{Object.keys(PRESETS).map((p) => <option key={p}>{p}</option>)}</select>}>
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); bt.run({ symbol, interval, period, entry, exit, stop_loss_pct: sl, take_profit_pct: tp, cost_bps: cost, monte_carlo: true }); }}>
          <div className="grid grid-cols-3 gap-2">
            <Field label="Symbol"><input className="input font-semibold" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} /></Field>
            <Field label="Bars"><select className="select" value={interval} onChange={(e) => { setIntervalV(e.target.value); setPeriod(catalog?.intervals?.[e.target.value]?.[2] ?? catalog?.intervals?.[e.target.value]?.[0]); }}>{Object.keys(catalog?.intervals ?? { "1d": [] }).map((k) => <option key={k}>{k}</option>)}</select></Field>
            <Field label="History"><select className="select" value={period} onChange={(e) => setPeriod(e.target.value)}>{periods.map((p) => <option key={p}>{p}</option>)}</select></Field>
          </div>
          <CondRows title="Enter long when all hold" rows={entry} setRows={setEntry} catalog={catalog} joiner="and" />
          <CondRows title="Exit when any holds" rows={exit} setRows={setExit} catalog={catalog} joiner="or" />
          <div className="grid grid-cols-3 gap-2">
            <Field label="Stop loss %"><input className="input num" type="number" value={sl} onChange={(e) => setSl(Number(e.target.value))} /></Field>
            <Field label="Take profit %"><input className="input num" type="number" value={tp} onChange={(e) => setTp(Number(e.target.value))} /></Field>
            <Field label="Cost (bps)"><input className="input num" type="number" value={cost} onChange={(e) => setCost(Number(e.target.value))} /></Field>
          </div>
          <button className="btn btn-primary w-full" disabled={bt.running}>{bt.running ? <Spinner /> : <Play size={13} />}Backtest</button>
          <p className="faint text-[10.5px]">Decisions at each bar close earn the next bar's return. Costs charged on every position change. 0 disables stop or target.</p>
        </form>
      </Card>
      <div className="min-w-0 space-y-3">
        <ErrorBox error={bt.error} />
        {!r && !bt.running && <Card><Empty title="Build and test a rule">Combine indicators with comparisons and crossovers, or start from a preset.</Empty></Card>}
        {r && (
          <>
            <div className="grid grid-cols-2 gap-3 rounded-[10px] border border-line bg-panel p-3 sm:grid-cols-4 xl:grid-cols-8">
              <Stat label="Total return" value={fpct(r.metrics.total_return)} sub={`B&H ${fpct(r.buy_hold.total_return)}`} strong />
              <Stat label="CAGR" value={fpct(r.metrics.cagr)} sub={`B&H ${fpct(r.buy_hold.cagr)}`} />
              <Stat label="Sharpe" value={num(r.metrics.sharpe)} sub={`B&H ${num(r.buy_hold.sharpe)}`} />
              <Stat label="Sortino" value={num(r.metrics.sortino)} />
              <Stat label="Max drawdown" value={fpct(r.metrics.max_drawdown, 1)} sub={`B&H ${fpct(r.buy_hold.max_drawdown, 1)}`} />
              <Stat label="Trades" value={r.metrics.trades} sub={`win ${rate(r.metrics.trade_win_rate, 0)}`} />
              <Stat label="Profit factor" value={num(r.metrics.profit_factor)} sub={`avg ${fpct(r.metrics.avg_trade)}`} />
              <Stat label="Exposure" value={rate(r.metrics.exposure, 0)} sub={`${r.start} to ${r.end}`} />
            </div>
            {r.note && <p className="muted text-[12px]">{r.note}</p>}
            <div className="grid grid-cols-1 gap-3 2xl:grid-cols-2">
              <Card title="Equity and drawdown">
                <LineChart x={r.curve.dates} series={[{ name: "Strategy", values: r.curve.equity, width: 2 }, { name: "Buy and hold", values: r.buy_hold_curve.equity, dash: "4 3" }]} height={180} yFormat={(v) => v.toFixed(2)} xFormat={(d) => String(d).slice(0, 7)} />
                <LineChart x={r.curve.dates} series={[{ name: "Strategy drawdown", values: r.curve.drawdown, fill: true }, { name: "Buy and hold drawdown", values: r.buy_hold_curve.drawdown, dash: "4 3", tone: TONES[2] }]} height={100} yFormat={(v) => `${(v * 100).toFixed(0)}%`} xFormat={(d) => String(d).slice(0, 7)} />
              </Card>
              <Card title="Trades on the chart" bodyClass="p-0">{chart?.bars ? <PriceChart bars={chart.bars} type="line" indicators={["volume"]} intraday={chart.intraday} markers={markers} height={300} theme={theme} /> : <div className="p-3">{chartError ? <ErrorBox error={chartError} /> : <Spinner />}</div>}</Card>
              {r.monte_carlo && !r.monte_carlo.error && (
                <Card title={`Monte Carlo: ${r.monte_carlo.n_sims.toLocaleString()} block-bootstrap paths over ${r.monte_carlo.horizon_days} bars`}>
                  <LineChart
                    x={r.monte_carlo.bands.p50.map((_: any, i: number) => i)}
                    series={[{ name: "Median", values: r.monte_carlo.bands.p50, width: 2 }, { name: "5th", values: r.monte_carlo.bands.p5, dash: "2 2" }, { name: "95th", values: r.monte_carlo.bands.p95, dash: "2 2" }]}
                    area={{ upper: r.monte_carlo.bands.p75, lower: r.monte_carlo.bands.p25 }}
                    height={180}
                    yFormat={(v) => v.toFixed(2)}
                  />
                  <div className="mt-2 grid grid-cols-2 gap-3">
                    <div>
                      <div className="eyebrow mb-1">Final return distribution</div>
                      <Histogram counts={r.monte_carlo.histogram.counts} edges={r.monte_carlo.histogram.edges} format={(v) => fpct(v, 0)} marker={0} />
                    </div>
                    <dl className="kv text-[12px]">
                      <dt>Median return</dt><dd>{fpct(r.monte_carlo.final_return.p50)}</dd>
                      <dt>5th / 95th</dt><dd>{fpct(r.monte_carlo.final_return.p5)} / {fpct(r.monte_carlo.final_return.p95)}</dd>
                      <dt>Probability of loss</dt><dd>{rate(r.monte_carlo.prob_loss)}</dd>
                      <dt>P(drawdown 20%+)</dt><dd>{rate(r.monte_carlo.prob_drawdown_20)}</dd>
                      <dt>Median max DD</dt><dd>{fpct(r.monte_carlo.max_drawdown.median, 1)}</dd>
                      <dt>Worst 5% max DD</dt><dd>{fpct(r.monte_carlo.max_drawdown.p5, 1)}</dd>
                    </dl>
                  </div>
                </Card>
              )}
              <Card title={`Trades (${r.trades.length})`} bodyClass="p-0">
                <div className="max-h-[360px] overflow-auto">
                  <table className="tbl">
                    <thead><tr><th>Entry</th><th>Exit</th><th className="r">Bars</th><th className="r">Return</th></tr></thead>
                    <tbody>{[...r.trades].reverse().map((t: any, i: number) => <tr key={i}><td className="num">{t.entry}</td><td className="num">{t.exit}</td><td className="r num">{t.days}</td><td className="r"><Change value={t.return * 100} icon={false} /></td></tr>)}</tbody>
                  </table>
                </div>
              </Card>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function EvaluatorTab() {
  const [symbol, setSymbol] = useState("AAPL");
  const [form, setForm] = useState({ entry: "", stop: "", target: "" });
  const ev = useAction((body: any, signal) => api("/api/trade/evaluate", { body, signal }));
  return (
    <Card title="Trade evaluator">
      <EvaluatorView
        form={form}
        setForm={setForm}
        ev={ev}
        onRun={() => ev.run({ symbol, entry: +form.entry, stop: +form.stop, target: +form.target })}
        symbolField={
          <Field label="Symbol">
            <div className="flex gap-1">
              <input className="input font-semibold" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
              <button type="button" className="btn" onClick={async () => { const q = await api(`/api/market/quotes?symbols=${encodeURIComponent(symbol)}`); const p = q?.[symbol]?.price; if (p) setForm({ entry: p.toFixed(2), stop: (p * 0.95).toFixed(2), target: (p * 1.1).toFixed(2) }); }}>Use price</button>
            </div>
          </Field>
        }
      />
    </Card>
  );
}

function StrategiesInner() {
  const sp = useSearchParams();
  const router = useRouter();
  const tab = (sp.get("tab") as "competition" | "builder" | "evaluator") || "competition";
  return (
    <div>
      <PageHeader
        title="Strategies"
        subtitle="Rule-based strategies are the baselines the neural networks have to beat. Compete them, build your own, or grade a trade plan."
        right={<Seg value={tab} onChange={(t) => router.replace(`/strategies?tab=${t}`)} options={[{ value: "competition", label: "Competition" }, { value: "builder", label: "Builder" }, { value: "evaluator", label: "Evaluator" }]} />}
      />
      {tab === "competition" && <CompetitionTab />}
      {tab === "builder" && <BuilderTab />}
      {tab === "evaluator" && <EvaluatorTab />}
      <Disclaimer>Backtests are hypothetical, use adjusted daily data, and ignore taxes and borrow costs. Past results do not predict future performance.</Disclaimer>
    </div>
  );
}

export default function StrategiesPage() {
  return (
    <Suspense fallback={null}>
      <StrategiesInner />
    </Suspense>
  );
}
