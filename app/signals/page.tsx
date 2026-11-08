"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Download } from "lucide-react";
import { Dots } from "@/components/charts";
import { Card, Change, Disclaimer, Empty, ErrorBox, Meter, PageHeader, Seg, SignalPill, Skeleton, StarButton, SymbolLink } from "@/components/ui";
import { useApi } from "@/lib/api";
import { downloadFile, pct, price, rate, toCSV } from "@/lib/format";
import { useWatchlist } from "@/lib/store";

type SortKey = "prob_up" | "change_pct" | "return_1m" | "symbol" | "uncertainty";

function NeuralTable({ symbols }: { symbols: string | null }) {
  const path = symbols ? `/api/signals/scan?symbols=${encodeURIComponent(symbols)}` : "/api/signals/scan";
  const { data, error, reload, loading } = useApi<any>(path, { staleMs: 120_000 });
  const [filter, setFilter] = useState<"all" | "bullish" | "neutral" | "bearish">("all");
  const [sector, setSector] = useState("all");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "prob_up", dir: -1 });
  const sectors = useMemo(() => Array.from(new Set((data?.rows ?? []).map((r: any) => r.sector).filter(Boolean))) as string[], [data]);
  const rows = useMemo(() => {
    let r = (data?.rows ?? []) as any[];
    if (filter !== "all") r = r.filter((x) => x.signal === filter);
    if (sector !== "all") r = r.filter((x) => x.sector === sector);
    if (q) r = r.filter((x) => x.symbol.includes(q.toUpperCase()) || (x.name || "").toLowerCase().includes(q.toLowerCase()));
    return [...r].sort((a, b) => {
      const va = a[sort.key] ?? -Infinity;
      const vb = b[sort.key] ?? -Infinity;
      return (va > vb ? 1 : va < vb ? -1 : 0) * sort.dir;
    });
  }, [data, filter, sector, q, sort]);
  const Th = ({ k, children, r }: { k: SortKey; children: React.ReactNode; r?: boolean }) => (
    <th className={`cursor-pointer select-none ${r ? "r" : ""}`} onClick={() => setSort((s) => ({ key: k, dir: s.key === k ? ((-s.dir) as 1 | -1) : -1 }))}>
      <span className="inline-flex items-center gap-0.5">{children}{sort.key === k && (sort.dir === -1 ? <ArrowDown size={10} /> : <ArrowUp size={10} />)}</span>
    </th>
  );
  return (
    <Card
      title={<>Neural ensemble <span className="faint font-normal">LSTM, GRU, TCN, Transformer · 5-day direction</span></>}
      right={
        <>
          <input className="input h-6 w-32 text-[12px]" placeholder="Filter" value={q} onChange={(e) => setQ(e.target.value)} />
          <select className="select h-6 w-auto text-[12px]" value={sector} onChange={(e) => setSector(e.target.value)}>
            <option value="all">All sectors</option>
            {sectors.map((s) => <option key={s}>{s}</option>)}
          </select>
          <Seg value={filter} onChange={setFilter} options={[{ value: "all", label: "All" }, { value: "bullish", label: "Bullish" }, { value: "neutral", label: "Neutral" }, { value: "bearish", label: "Bearish" }]} />
          <button className="btn btn-sm" title="Export CSV" disabled={!data} onClick={() => downloadFile("neural-signals.csv", toCSV(rows.map((r) => ({ symbol: r.symbol, name: r.name, sector: r.sector, price: r.price, change_pct: r.change_pct, return_1m: r.return_1m, prob_up: r.prob_up, signal: r.signal, decile: r.calibrated?.decile, hist_up_freq: r.calibrated?.historical_up_frequency, agreement: r.agreement, uncertainty: r.uncertainty }))), "text/csv")}><Download size={12} /></button>
        </>
      }
      bodyClass="p-0"
    >
      <ErrorBox error={error} onRetry={reload} />
      {loading && <div className="p-3"><Skeleton h={360} /></div>}
      {data && (
        <>
          <div className="faint flex flex-wrap gap-x-4 gap-y-1 border-b border-line px-3 py-1.5 text-[11px]">
            <span>As of {data.as_of}</span>
            <span>Base rate {rate(data.breadth.base_rate)} of 5-day windows rose in the test period</span>
            <span>{data.signal_rule}</span>
          </div>
          <div className="max-h-[calc(100vh-230px)] overflow-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <Th k="symbol">Symbol</Th>
                  <th>Name</th>
                  <th>Sector</th>
                  <Th k="change_pct" r>Price / day</Th>
                  <Th k="return_1m" r>1M</Th>
                  <Th k="prob_up" r>P(up 5d)</Th>
                  <th className="r">Decile</th>
                  <th className="r" title="Historical up-frequency for this confidence decile">Hit rate</th>
                  <th title="Members predicting up">Agree</th>
                  <Th k="uncertainty" r>MC std</Th>
                  <th>Signal</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((r: any) => (
                  <tr key={r.symbol}>
                    <td><SymbolLink symbol={r.symbol} /></td>
                    <td className="max-w-[180px] truncate">{r.name}</td>
                    <td className="faint">{r.sector}</td>
                    <td className="r"><span className="num mr-2">{price(r.price)}</span><Change value={r.change_pct} /></td>
                    <td className="r"><Change value={r.return_1m} icon={false} /></td>
                    <td className="r">
                      <div className="ml-auto flex w-[110px] items-center gap-2">
                        <Meter value={r.prob_up} min={0.4} max={0.75} marker={data.breadth.base_rate} />
                        <span className="num w-10 text-right font-medium">{r.prob_up.toFixed(3)}</span>
                      </div>
                    </td>
                    <td className="r num">{r.calibrated?.decile ?? "--"}/10</td>
                    <td className="r num">{rate(r.calibrated?.historical_up_frequency)}</td>
                    <td><Dots value={Math.round(r.agreement * 4)} /></td>
                    <td className="r num faint">{r.uncertainty?.toFixed(3) ?? "--"}</td>
                    <td><SignalPill signal={r.signal} /></td>
                    <td className="w-6"><StarButton symbol={r.symbol} size={12} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!rows.length && <Empty title="No symbols match the filters" />}
          </div>
        </>
      )}
    </Card>
  );
}

function TechnicalTable({ symbols }: { symbols: string | null }) {
  const path = symbols ? `/api/signals/technical/scan?symbols=${encodeURIComponent(symbols)}` : "/api/signals/technical/scan";
  const { data, error, reload } = useApi<any>(path, { staleMs: 120_000 });
  return (
    <Card title={<>Technical baseline <span className="faint font-normal">RSI + EMA rules</span></>} bodyClass="p-0">
      <ErrorBox error={error} onRetry={reload} />
      {!data && !error && <div className="p-3"><Skeleton h={300} /></div>}
      {data && (
        <>
          <p className="faint border-b border-line px-3 py-1.5 text-[11px]">{data.method}</p>
          <div className="max-h-[calc(100vh-260px)] overflow-auto">
            <table className="tbl">
              <thead><tr><th>Symbol</th><th className="r">RSI</th><th className="r">Vol x</th><th className="r">Score</th><th>Setup</th><th>Reasons</th></tr></thead>
              <tbody>
                {data.rows.map((r: any) => (
                  <tr key={r.symbol}>
                    <td><SymbolLink symbol={r.symbol} /></td>
                    <td className="r num">{r.rsi.toFixed(0)}</td>
                    <td className="r num">{r.volume_ratio.toFixed(1)}</td>
                    <td className="r num font-medium">{r.score > 0 ? "+" : ""}{r.score}</td>
                    <td><SignalPill signal={r.signal} /></td>
                    <td className="faint max-w-[260px] truncate text-[11.5px]" title={r.reasons.join("; ")}>{r.reasons.join("; ") || "--"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="faint px-3 py-1.5 text-[10.5px]">{data.disclaimer}</p>
        </>
      )}
    </Card>
  );
}

export default function SignalsPage() {
  const wl = useWatchlist();
  const [scope, setScope] = useState<"universe" | "watchlist" | "custom">("universe");
  const [custom, setCustom] = useState("");
  const symbols = scope === "watchlist" ? wl.list.join(",") : scope === "custom" ? custom : null;
  return (
    <div>
      <PageHeader
        title="Signals"
        subtitle={<>The pretrained neural ensemble scores the next five trading days for each symbol, next to a classic RSI + EMA rule baseline. <Link href="/lab?tab=model" className="underline">How reliable is it?</Link></>}
        right={
          <>
            <Seg value={scope} onChange={setScope} options={[{ value: "universe", label: "Model universe" }, { value: "watchlist", label: wl.active }, { value: "custom", label: "Custom" }]} />
            {scope === "custom" && (
              <form onSubmit={(e) => { e.preventDefault(); setCustom(((e.currentTarget.elements.namedItem("s") as HTMLInputElement).value || "").toUpperCase().replace(/\s+/g, "")); }} className="flex gap-1">
                <input name="s" className="input h-7 w-64" placeholder="PLTR,COIN,UBER,SHOP" defaultValue={custom} />
                <button className="btn btn-primary">Scan</button>
              </form>
            )}
          </>
        }
      />
      {scope === "custom" && !custom ? (
        <Card><Empty title="Enter symbols to scan">The ensemble was trained on 48 liquid US stocks and ETFs, but its features are scale-free, so it can score any symbol with a year of history.</Empty></Card>
      ) : (
        <div className="grid grid-cols-1 gap-3 min-[1800px]:grid-cols-12">
          <div className="min-[1800px]:col-span-8"><NeuralTable symbols={symbols} /></div>
          <div className="min-[1800px]:col-span-4"><TechnicalTable symbols={symbols} /></div>
        </div>
      )}
      <Disclaimer>Signals are statistical tilts measured against a {"55%"} base rate, not buy or sell recommendations. Edges on daily equity data are small and change over time.</Disclaimer>
    </div>
  );
}
