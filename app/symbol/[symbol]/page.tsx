"use client";
import Link from "next/link";
import { Fragment, use, useEffect, useMemo, useState } from "react";
import { FlaskConical, Maximize2, Minimize2 } from "lucide-react";
import { DivergingBars, LineChart, TONES } from "@/components/charts";
import { PriceChart, type ModelPoint } from "@/components/PriceChart";
import { useResolvedTheme } from "@/components/shell";
import { Card, Change, Disclaimer, Empty, ErrorBox, Field, Markdown, Meter, PageHeader, Seg, SignalPill, Skeleton, SourceTag, Spinner, StarButton } from "@/components/ui";
import { api, useAction, useApi } from "@/lib/api";
import { ago, compact, fpct, num, pct, price, rate } from "@/lib/format";
import { INDICATORS } from "@/lib/indicators";
import { DEFAULT_PREFS, KEYS, pushRecent, useStored, type Prefs } from "@/lib/store";
import { EvaluatorView } from "@/components/evaluator";

const RANGE_LABELS: Record<string, string> = { "1d": "1D", "5d": "5D", "1mo": "1M", "3mo": "3M", "6mo": "6M", ytd: "YTD", "1y": "1Y", "2y": "2Y", "5y": "5Y", "10y": "10Y", max: "MAX" };
const INTERVAL_LABELS: Record<string, string> = { "1m": "1 min", "5m": "5 min", "15m": "15 min", "30m": "30 min", "1h": "1 hour", "4h": "4 hours", "1d": "1 day", "1wk": "1 week", "1mo": "1 month" };

function ChartPanel({ symbol }: { symbol: string }) {
  const [prefs, setPrefs] = useStored<Prefs>(KEYS.prefs, DEFAULT_PREFS);
  const [full, setFull] = useState(false);
  const theme = useResolvedTheme();
  const { data: tf } = useApi<any>("/api/market/timeframes", { staleMs: 86_400_000 });
  const range = prefs.chartRange;
  const allowed: string[] = tf ? Object.keys(tf.intervals).filter((iv) => tf.intervals[iv].includes(range)) : [];
  const interval = prefs.chartInterval && (!tf || allowed.includes(prefs.chartInterval)) ? prefs.chartInterval : null;
  const { data, error, loading, reload } = useApi<any>(`/api/market/chart/${encodeURIComponent(symbol)}?range=${range}${interval ? `&interval=${interval}` : ""}`, { refreshMs: 60_000 });
  const effInterval = data?.interval ?? interval ?? "1d";
  const wantModel = prefs.indicators.includes("model") && effInterval === "1d";
  const { data: sig } = useApi<any>(wantModel ? `/api/signals/${encodeURIComponent(symbol)}?lookback=250` : null, { staleMs: 300_000 });
  const model: ModelPoint[] | undefined = useMemo(
    () => sig?.history?.dates.map((d: string, i: number) => ({ t: Date.UTC(+d.slice(0, 4), +d.slice(5, 7) - 1, +d.slice(8, 10)) / 1000, p: sig.history.prob_up[i] })).filter((x: ModelPoint) => x.p != null),
    [sig],
  );
  const toggle = (id: string) => setPrefs({ ...prefs, indicators: prefs.indicators.includes(id) ? prefs.indicators.filter((x) => x !== id) : [...prefs.indicators, id] });
  const height = full ? Math.max(480, typeof window !== "undefined" ? window.innerHeight - 170 : 700) : 440;
  return (
    <Card
      className={full ? "fixed inset-2 z-50 shadow-2xl" : ""}
      bodyClass="p-0"
      title={
        <div className="flex flex-wrap items-center gap-1.5">
          <Seg value={range} onChange={(v) => setPrefs({ ...prefs, chartRange: v, chartInterval: null })} options={Object.keys(RANGE_LABELS).map((r) => ({ value: r, label: RANGE_LABELS[r] }))} />
          <select className="select h-6 w-auto text-[12px]" value={interval ?? ""} onChange={(e) => setPrefs({ ...prefs, chartInterval: e.target.value || null })} title="Bar interval">
            <option value="">Auto ({INTERVAL_LABELS[tf?.ranges?.[range]?.interval] ?? "..."})</option>
            {allowed.map((iv) => <option key={iv} value={iv}>{INTERVAL_LABELS[iv]}</option>)}
          </select>
          <Seg value={prefs.chartType} onChange={(v) => setPrefs({ ...prefs, chartType: v })} options={[{ value: "candles", label: "Candles" }, { value: "line", label: "Line" }, { value: "area", label: "Area" }]} />
        </div>
      }
      right={
        <>
          {data && <span className="num text-[11.5px]"><span className="faint">{RANGE_LABELS[range]}</span> <Change value={data.change_pct} /></span>}
          <button className="btn btn-sm btn-ghost" onClick={() => setFull((f) => !f)} title={full ? "Exit full screen" : "Full screen"}>{full ? <Minimize2 size={13} /> : <Maximize2 size={13} />}</button>
        </>
      }
    >
      <div className="flex flex-wrap gap-1 border-b border-line px-2.5 py-1.5">
        {INDICATORS.map((ind) => (
          <button
            key={ind.id}
            className="chip"
            data-on={prefs.indicators.includes(ind.id)}
            onClick={() => toggle(ind.id)}
            disabled={(ind.id === "vwap" && !data?.intraday) || (ind.id === "model" && effInterval !== "1d")}
            title={ind.id === "model" ? "Neural ensemble P(up over 5 days), daily bars only" : ind.id === "vwap" ? "Intraday only" : undefined}
          >
            {ind.label}
          </button>
        ))}
      </div>
      <ErrorBox error={error} onRetry={reload} />
      {loading && <Skeleton h={height} className="rounded-none" />}
      {data && data.bars.length > 0 && (
        <PriceChart bars={data.bars} type={prefs.chartType} indicators={prefs.indicators} intraday={data.intraday} model={wantModel ? model : undefined} height={height} theme={theme} />
      )}
      {data && !data.bars.length && <Empty title="No bars for this timeframe" />}
      {data && <div className="faint border-t border-line px-2.5 py-1 text-[10.5px]">{data.bars.length} bars · {INTERVAL_LABELS[data.interval]} · range high {price(data.high)} low {price(data.low)} {data.intraday ? "· times in exchange local time" : ""}</div>}
    </Card>
  );
}

function NeuralPanel({ symbol }: { symbol: string }) {
  const { data, error, loading, reload } = useApi<any>(`/api/signals/${encodeURIComponent(symbol)}?lookback=120`, { staleMs: 300_000 });
  return (
    <Card title="Neural forecast" right={<Link href="/lab?tab=model" className="btn btn-sm btn-ghost">Model card</Link>}>
      <ErrorBox error={error} onRetry={reload} />
      {loading && <Skeleton h={260} />}
      {data && (
        <div className="space-y-3">
          <div className="flex items-end justify-between">
            <div>
              <div className="eyebrow">P(higher in {data.horizon_days} trading days)</div>
              <div className="num text-[28px] font-semibold leading-8">{data.prob_up.toFixed(3)}</div>
              <div className="faint num text-[11px]">90% MC-dropout band {data.uncertainty.p05.toFixed(3)} to {data.uncertainty.p95.toFixed(3)}</div>
            </div>
            <div className="text-right"><SignalPill signal={data.signal} /><div className="faint mt-1 text-[11px]">as of {data.as_of}</div></div>
          </div>
          <Meter value={data.prob_up} min={0.4} max={0.75} marker={data.calibrated?.base_rate} height={8} />
          {data.calibrated && (
            <div className="rounded-lg bg-bg-2 px-2.5 py-2 text-[12px] leading-snug">
              This reading is in confidence decile <b>{data.calibrated.decile}/10</b>. On held-out 2024 to 2026 data, readings in this decile were followed by a rise <b>{rate(data.calibrated.historical_up_frequency)}</b> of the time (average 5-day move {fpct(data.calibrated.mean_fwd_return)}), versus a base rate of {rate(data.calibrated.base_rate)}.
            </div>
          )}
          <div>
            <div className="eyebrow mb-1">Ensemble members · {Math.round(data.agreement * 100)}% agree on up</div>
            {data.members.map((m: any) => (
              <div key={m.id} className="flex items-center gap-2 py-0.5 text-[12px]">
                <span className="w-24 truncate">{m.name}</span>
                <Meter value={m.prob_up} min={0.4} max={0.75} />
                <span className="num w-11 text-right">{m.prob_up.toFixed(3)}</span>
              </div>
            ))}
          </div>
          <div>
            <div className="eyebrow mb-1">Why: input attribution (gradient x input)</div>
            <DivergingBars labelWidth={130} format={(v) => v.toFixed(3)} rows={data.attribution.slice(0, 7).map((a: any) => ({ key: a.feature, label: <span title={a.feature}>{a.label}</span>, value: a.contribution }))} />
            <p className="faint mt-1 text-[10.5px]">Solid bars pushed the probability up, outlined bars pushed it down.</p>
          </div>
          <div>
            <div className="eyebrow mb-1">P(up) over the last {data.history.dates.length} sessions</div>
            <LineChart x={data.history.dates} series={[{ name: "P(up)", values: data.history.prob_up, tone: TONES[0] }]} height={110} yFormat={(v) => v.toFixed(2)} xFormat={(d) => String(d).slice(5)} refLine={data.calibrated ? { value: data.calibrated.base_rate } : undefined} legend={false} />
          </div>
          {!data.in_universe && <p className="faint text-[11px]">{symbol} was not in the training universe; the model scores it with the same scale-free features.</p>}
        </div>
      )}
    </Card>
  );
}

function AIRead({ symbol }: { symbol: string }) {
  const { data, error, loading, reload } = useApi<any>(`/api/insights/ticker/${encodeURIComponent(symbol)}`, { staleMs: 900_000 });
  if (loading) return <div className="space-y-2"><Skeleton h={16} w="60%" /><Skeleton h={12} /><Skeleton h={12} w="85%" /></div>;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return null;
  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between"><div className="flex items-center gap-2"><span className="eyebrow">Overall read</span><SignalPill signal={data.stance} /></div><SourceTag source={data.source} note={data.note} /></div>
      <p className="text-[13px] leading-relaxed">{data.summary}</p>
      <div className="grid gap-3 md:grid-cols-2">
        <div><div className="eyebrow mb-1">What is happening</div><ul className="space-y-1 text-[12px]">{data.happening.map((h: string, i: number) => <li key={i}>{h}</li>)}</ul></div>
        <div><div className="eyebrow mb-1">What to consider</div><ul className="space-y-1 text-[12px]">{data.consider.map((h: string, i: number) => <li key={i}>{h}</li>)}</ul></div>
      </div>
      <div className="rounded-lg bg-bg-2 px-2.5 py-2 text-[12px]"><span className="eyebrow mr-1.5">Model</span>{data.model}</div>
      <div className="text-[12px]"><span className="eyebrow mr-1.5">Risks</span>{data.risks.join(" ")}</div>
      <p className="faint text-[10.5px]">Generated {ago(data.generated_at)}. {data.disclaimer}</p>
    </div>
  );
}

function News({ symbol }: { symbol: string }) {
  const { data, error, loading, reload } = useApi<any>(`/api/insights/news/${encodeURIComponent(symbol)}`, { staleMs: 900_000 });
  if (loading) return <Skeleton h={200} />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return null;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="pill pill-soft">tone {data.tone}</span>
        <span className={`pill ${data.impact === "high" ? "pill-solid" : data.impact === "medium" ? "pill-outline" : "pill-soft"}`}>impact {data.impact}</span>
        {data.themes?.map((t: string) => <span key={t} className="chip">{t}</span>)}
        {data.affected_sectors?.length > 0 && <span className="faint text-[11px]">Sectors: {data.affected_sectors.join(", ")}</span>}
        <span className="ml-auto"><SourceTag source={data.source} note={data.note} /></span>
      </div>
      <p className="text-[12.5px]">{data.summary}</p>
      <div className="divide-y divide-line">
        {data.articles.map((a: any, i: number) => (
          <a key={i} href={a.url} target="_blank" rel="noreferrer" className="flex items-start justify-between gap-3 py-1.5 hover:bg-bg-2">
            <span className="min-w-0"><span className="block text-[12.5px] font-medium leading-snug">{a.title}</span><span className="faint text-[11px]">{a.source} · {ago(a.published_at)}</span></span>
            <span className={`pill shrink-0 ${a.sentiment === "positive" ? "pill-solid" : a.sentiment === "negative" ? "pill-outline" : "pill-soft"}`}>{a.sentiment}</span>
          </a>
        ))}
        {!data.articles.length && <Empty title="No recent headlines" />}
      </div>
    </div>
  );
}

function Technicals({ symbol }: { symbol: string }) {
  const { data } = useApi<any>(`/api/market/technicals/${encodeURIComponent(symbol)}`, { staleMs: 300_000 });
  if (!data) return <Skeleton h={160} />;
  const rows: [string, string][] = [
    ["Trend", data.trend], ["RSI (14)", num(data.rsi_14, 1)], ["SMA 20", price(data.sma_20)], ["SMA 50", price(data.sma_50)], ["SMA 200", price(data.sma_200)],
    ["MACD histogram", num(data.macd_hist, 3)], ["ATR (14)", price(data.atr_14)], ["Volatility 20d (ann.)", fpct(data.volatility_20d_ann, 1)],
    ["52-week high", price(data.high_52w)], ["52-week low", price(data.low_52w)], ["Volume vs 20d", `${num(data.volume_ratio_20d, 2)}x`],
    ["1 month", fpct(data.return_1m)], ["3 months", fpct(data.return_3m)], ["1 year", fpct(data.return_1y)],
  ];
  return (
    <dl className="kv grid-cols-[auto_1fr_auto_1fr] text-[12px]">
      {rows.map(([k, v]) => (
        <Fragment key={k}>
          <dt>{k}</dt>
          <dd className="capitalize">{v}</dd>
        </Fragment>
      ))}
    </dl>
  );
}

function Evaluator({ symbol, last }: { symbol: string; last?: number }) {
  const [form, setForm] = useState({ entry: "", stop: "", target: "" });
  useEffect(() => {
    if (last && !form.entry) setForm({ entry: last.toFixed(2), stop: (last * 0.95).toFixed(2), target: (last * 1.1).toFixed(2) });
  }, [last]); // eslint-disable-line react-hooks/exhaustive-deps
  const ev = useAction((body: any, signal) => api("/api/trade/evaluate", { body, signal }));
  return <EvaluatorView form={form} setForm={setForm} ev={ev} onRun={() => ev.run({ symbol, entry: +form.entry, stop: +form.stop, target: +form.target })} />;
}

function StrategyArena({ symbol }: { symbol: string }) {
  const [period, setPeriod] = useState("2y");
  const cmp = useAction((body: any, signal) => api("/api/strategies/compare", { body, signal }));
  const r = cmp.data;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Seg value={period} onChange={setPeriod} options={["1y", "2y", "5y", "10y"].map((p) => ({ value: p, label: p.toUpperCase() }))} />
        <button className="btn btn-primary" onClick={() => cmp.run({ symbol, period, interval: "1d" })} disabled={cmp.running}>{cmp.running && <Spinner />}Run 5 strategy agents</button>
        <Link href={`/lab?tab=arena&symbol=${symbol}`} className="btn"><FlaskConical size={13} />Neural networks vs rules</Link>
      </div>
      <ErrorBox error={cmp.error} />
      {r && (
        <div className="grid gap-3 lg:grid-cols-2">
          <table className="tbl">
            <thead><tr><th>#</th><th>Strategy</th><th className="r">Sharpe</th><th className="r">Return</th><th className="r">Max DD</th><th className="r">Trades</th></tr></thead>
            <tbody>
              {r.strategies.map((s: any) => (
                <tr key={s.id} title={s.description}><td className="num">{s.rank}</td><td className="font-medium">{s.name}</td><td className="r num">{num(s.metrics.sharpe)}</td><td className="r"><Change value={s.metrics.total_return * 100} icon={false} /></td><td className="r num">{fpct(s.metrics.max_drawdown, 1)}</td><td className="r num">{s.trades}</td></tr>
              ))}
              <tr><td /><td className="faint">Buy and hold</td><td className="r num faint">{num(r.buy_hold.metrics.sharpe)}</td><td className="r faint">{fpct(r.buy_hold.metrics.total_return)}</td><td className="r num faint">{fpct(r.buy_hold.metrics.max_drawdown, 1)}</td><td /></tr>
            </tbody>
          </table>
          <div>
            <LineChart x={r.buy_hold.curve.dates} series={[...r.strategies.slice(0, 3).map((s: any, i: number) => ({ name: s.name, values: s.curve.equity, tone: TONES[i] })), { name: "Buy and hold", values: r.buy_hold.curve.equity, tone: "var(--fg-3)", dash: "4 3" }]} height={180} yFormat={(v) => v.toFixed(2)} xFormat={(d) => String(d).slice(0, 7)} />
            <div className="mt-2 rounded-lg bg-bg-2 px-2.5 py-2 text-[12px]"><div className="mb-0.5 flex justify-between"><span className="eyebrow">Coach</span><SourceTag source={r.interpretation?.source} note={r.interpretation?.note} /></div>{r.interpretation?.text}</div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SymbolPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol: raw } = use(params);
  const symbol = decodeURIComponent(raw).toUpperCase();
  const [tab, setTab] = useState<"ai" | "news" | "tech" | "eval" | "strat">("ai");
  const { data: q } = useApi<any>(`/api/market/quotes?symbols=${encodeURIComponent(symbol)}`, { refreshMs: 30_000 });
  const { data: prof } = useApi<any>(`/api/market/profile/${encodeURIComponent(symbol)}`, { staleMs: 3_600_000 });
  const quote = q?.[symbol];
  useEffect(() => {
    pushRecent(symbol);
  }, [symbol]);
  useEffect(() => {
    document.title = `${symbol}${quote ? ` ${price(quote.price)}` : ""} · Trading Engine`;
  }, [symbol, quote]);
  return (
    <div>
      <PageHeader
        title={symbol}
        subtitle={prof ? `${prof.name}${prof.exchange ? ` · ${prof.exchange}` : ""}${prof.sector ? ` · ${prof.sector}` : ""}` : " "}
        right={
          <div className="flex flex-wrap items-center gap-4">
            <div className="text-right">
              <div className="num text-[22px] font-semibold leading-6">{price(quote?.price)}</div>
              <div className="text-[12px]"><Change value={quote?.change_pct} /> <span className="faint num">{quote ? `${quote.change >= 0 ? "+" : "−"}${price(Math.abs(quote.change))}` : ""}</span></div>
            </div>
            {[["Market cap", compact(prof?.market_cap)], ["P/E", num(prof?.pe, 1)], ["Beta", num(prof?.beta, 2)], ["Volume", compact(quote?.volume)]].map(([k, v]) => (
              <div key={k} className="hidden md:block"><div className="eyebrow">{k}</div><div className="num font-medium">{v}</div></div>
            ))}
            {prof?.high_52w && quote && (
              <div className="hidden w-36 lg:block">
                <div className="eyebrow">52-week range</div>
                <Meter value={quote.price} min={prof.low_52w} max={prof.high_52w} />
                <div className="faint num flex justify-between text-[10.5px]"><span>{price(prof.low_52w)}</span><span>{price(prof.high_52w)}</span></div>
              </div>
            )}
            <StarButton symbol={symbol} size={16} />
            <Link href={`/lab?symbol=${symbol}`} className="btn"><FlaskConical size={13} />Train a model</Link>
          </div>
        }
      />
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-12">
        <div className="space-y-3 xl:col-span-8 2xl:col-span-9">
          <ChartPanel symbol={symbol} />
          <Card
            title={<Seg value={tab} onChange={setTab} options={[{ value: "ai", label: "AI read" }, { value: "news", label: "News" }, { value: "tech", label: "Technicals" }, { value: "eval", label: "Trade evaluator" }, { value: "strat", label: "Strategy agents" }]} />}
          >
            {tab === "ai" && <AIRead symbol={symbol} />}
            {tab === "news" && <News symbol={symbol} />}
            {tab === "tech" && <Technicals symbol={symbol} />}
            {tab === "eval" && <Evaluator symbol={symbol} last={quote?.price} />}
            {tab === "strat" && <StrategyArena symbol={symbol} />}
          </Card>
        </div>
        <div className="space-y-3 xl:col-span-4 2xl:col-span-3">
          <NeuralPanel symbol={symbol} />
          {prof?.summary && <Card title="Profile"><p className="muted text-[12px] leading-relaxed">{prof.summary}{prof.summary.length >= 600 ? "..." : ""}</p><p className="faint mt-1 text-[11px]">{prof.industry}</p></Card>}
        </div>
      </div>
      <Disclaimer />
    </div>
  );
}
