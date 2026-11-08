"use client";
import { useEffect, useMemo, useState } from "react";
import { Download, Plus, Trash2, Upload } from "lucide-react";
import { DivergingBars, Heatmap } from "@/components/charts";
import { Card, Change, Disclaimer, Empty, ErrorBox, Meter, PageHeader, SignalPill, Skeleton, SourceTag, Spinner, Stat, SymbolLink } from "@/components/ui";
import { api } from "@/lib/api";
import { downloadFile, fpct, num, pct, price, rate, toCSV } from "@/lib/format";
import { KEYS, useStored } from "@/lib/store";

interface Position { symbol: string; quantity: number; avg_cost: number }
const SAMPLE: Position[] = [
  { symbol: "AAPL", quantity: 20, avg_cost: 210 }, { symbol: "MSFT", quantity: 10, avg_cost: 380 }, { symbol: "NVDA", quantity: 30, avg_cost: 120 },
  { symbol: "JPM", quantity: 15, avg_cost: 190 }, { symbol: "XOM", quantity: 25, avg_cost: 105 }, { symbol: "LLY", quantity: 4, avg_cost: 700 },
];

export default function PortfolioPage() {
  const [positions, setPositions] = useStored<Position[]>(KEYS.portfolio, []);
  const [draft, setDraft] = useState({ symbol: "", quantity: "", avg_cost: "" });
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const key = useMemo(() => JSON.stringify(positions), [positions]);
  useEffect(() => {
    if (!positions.length) return setData(null);
    let cancelled = false;
    const id = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const r = await api("/api/portfolio/analyze", { body: { positions, narrate: true } });
        if (!cancelled) setData(r);
      } catch (e: any) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 500);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  const add = () => {
    const s = draft.symbol.trim().toUpperCase();
    if (!s || !Number(draft.quantity)) return;
    setPositions([...positions.filter((p) => p.symbol !== s), { symbol: s, quantity: Number(draft.quantity), avg_cost: Number(draft.avg_cost) || 0 }]);
    setDraft({ symbol: "", quantity: "", avg_cost: "" });
  };
  const importCSV = (file: File) =>
    file.text().then((t) => {
      const rows = t.trim().split(/\r?\n/).slice(1).map((l) => l.split(","));
      setPositions(rows.filter((r) => r[0]).map((r) => ({ symbol: r[0].trim().toUpperCase(), quantity: Number(r[1]), avg_cost: Number(r[2]) || 0 })));
    });
  return (
    <div>
      <PageHeader
        title="Portfolio"
        subtitle="Risk, diversification and a neural-network read on every holding. Positions are stored only in this browser."
        right={
          <>
            <label className="btn cursor-pointer"><Upload size={12} />Import CSV<input type="file" accept=".csv" className="hidden" onChange={(e) => e.target.files?.[0] && importCSV(e.target.files[0])} /></label>
            <button className="btn" disabled={!positions.length} onClick={() => downloadFile("portfolio.csv", toCSV(positions as any), "text/csv")}><Download size={12} />Export</button>
          </>
        }
      />
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-12">
        <Card className="xl:col-span-8" title="Positions" right={loading && <Spinner size={12} />} bodyClass="p-0">
          <form className="flex flex-wrap gap-1.5 border-b border-line p-2" onSubmit={(e) => (e.preventDefault(), add())}>
            <input className="input w-24 font-semibold" placeholder="Symbol" value={draft.symbol} onChange={(e) => setDraft({ ...draft, symbol: e.target.value.toUpperCase() })} />
            <input className="input num w-24" placeholder="Quantity" inputMode="decimal" value={draft.quantity} onChange={(e) => setDraft({ ...draft, quantity: e.target.value })} />
            <input className="input num w-28" placeholder="Average cost" inputMode="decimal" value={draft.avg_cost} onChange={(e) => setDraft({ ...draft, avg_cost: e.target.value })} />
            <button className="btn btn-primary"><Plus size={12} />Add or update</button>
            {!positions.length && <button type="button" className="btn btn-ghost" onClick={() => setPositions(SAMPLE)}>Load a sample portfolio</button>}
          </form>
          {!positions.length ? <Empty title="No positions">Add holdings to see P&amp;L, value at risk, beta, correlation, sector exposure and the model's view of each holding.</Empty> : (
            <div className="overflow-x-auto">
              <table className="tbl">
                <thead><tr><th>Symbol</th><th className="r">Qty</th><th className="r">Avg cost</th><th className="r">Price</th><th className="r">Day</th><th className="r">Value</th><th className="r">Weight</th><th className="r">P&amp;L</th><th className="r">P(up 5d)</th><th>Model</th><th /></tr></thead>
                <tbody>
                  {(data?.positions ?? positions).map((p: any) => (
                    <tr key={p.symbol}>
                      <td><SymbolLink symbol={p.symbol} /><div className="faint text-[10.5px]">{p.error ?? p.sector ?? ""}</div></td>
                      <td className="r num">{p.quantity}</td>
                      <td className="r num">{price(p.avg_cost)}</td>
                      <td className="r num">{price(p.price)}</td>
                      <td className="r"><Change value={p.day_change_pct} /></td>
                      <td className="r num">{p.value != null ? Math.round(p.value).toLocaleString() : "--"}</td>
                      <td className="r num">{rate(p.weight)}</td>
                      <td className="r"><span className="num">{p.pnl != null ? `${p.pnl >= 0 ? "+" : "−"}${Math.abs(Math.round(p.pnl)).toLocaleString()}` : "--"}</span> <Change value={p.pnl_pct} icon={false} className="text-[11px]" /></td>
                      <td className="r num">{p.neural?.prob_up?.toFixed(3) ?? "--"}</td>
                      <td><SignalPill signal={p.neural?.signal} /></td>
                      <td className="w-6"><button className="btn-ghost rounded p-1" onClick={() => setPositions(positions.filter((x) => x.symbol !== p.symbol))}><Trash2 size={11} /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <Card className="xl:col-span-4" title="Health" right={data?.assessment && <SourceTag source={data.assessment.source} note={data.assessment.note} />}>
          <ErrorBox error={error} />
          {!data && positions.length > 0 && <Skeleton h={200} />}
          {data && (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <div className="num text-[30px] font-semibold leading-none">{Math.round(data.health.score)}</div>
                <div className="flex-1"><Meter value={data.health.score} max={100} height={8} /><div className="faint mt-1 text-[11px]">Diversification and risk health, 0 to 100</div></div>
              </div>
              {data.health.notes.length > 0 && <ul className="space-y-0.5 text-[12px]">{data.health.notes.map((n: string) => <li key={n} className="muted">{n}</li>)}</ul>}
              {data.assessment && <p className="rounded-lg bg-bg-2 px-2.5 py-2 text-[12.5px] leading-relaxed">{data.assessment.text}</p>}
              <div className="text-[12px]"><span className="eyebrow mr-1.5">Neural lens</span>{data.neural_summary.bullish} bullish, {data.neural_summary.neutral} neutral, {data.neural_summary.bearish} bearish holdings</div>
            </div>
          )}
        </Card>
        {data && (
          <>
            <div className="grid grid-cols-2 gap-3 rounded-[10px] border border-line bg-panel p-3 sm:grid-cols-4 xl:col-span-12 xl:grid-cols-8">
              <Stat label="Value" value={Math.round(data.total_value).toLocaleString()} sub={`cost ${Math.round(data.total_cost).toLocaleString()}`} strong />
              <Stat label="Unrealised P&L" value={`${data.total_pnl >= 0 ? "+" : "−"}${Math.abs(Math.round(data.total_pnl)).toLocaleString()}`} sub={pct(data.total_pnl_pct)} />
              <Stat label="Today" value={`${data.day_pnl >= 0 ? "+" : "−"}${Math.abs(Math.round(data.day_pnl)).toLocaleString()}`} />
              <Stat label="VaR 95% (1 day)" value={fpct(data.risk.var_95_1d)} sub={data.risk.var_95_1d_value != null ? `${Math.round(data.risk.var_95_1d_value).toLocaleString()}` : ""} />
              <Stat label="CVaR 95%" value={fpct(data.risk.cvar_95_1d)} />
              <Stat label="Beta vs SPY" value={num(data.risk.beta_vs_spy)} />
              <Stat label="Volatility (ann.)" value={fpct(data.risk.ann_vol, 1)} sub={`Sharpe 1y ${num(data.risk.sharpe_1y)}`} />
              <Stat label="Max drawdown 1y" value={fpct(data.risk.max_drawdown_1y, 1)} sub={`${data.concentration.effective_positions ?? "--"} effective positions`} />
            </div>
            <Card className="xl:col-span-5" title="Sector exposure">
              <DivergingBars labelWidth={130} format={(v) => rate(v)} rows={Object.entries(data.sectors).map(([s, w]: any) => ({ key: s, label: s, value: w }))} />
            </Card>
            <Card className="xl:col-span-7" title="Correlation (daily returns, 1 year)" right={data.correlation && <span className="faint text-[11px]">average pairwise {num(data.correlation.avg_pairwise)} · highest {data.correlation.highest.pair.join(" / ")} {num(data.correlation.highest.corr)}</span>}>
              {data.correlation ? <Heatmap matrix={data.correlation.matrix} rowLabels={data.correlation.symbols} colLabels={data.correlation.symbols} min={-1} max={1} signed /> : <Empty title="Add at least two positions" />}
            </Card>
          </>
        )}
      </div>
      <Disclaimer>{data?.disclaimer}</Disclaimer>
    </div>
  );
}
