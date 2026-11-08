"use client";
import Link from "next/link";
import { useState } from "react";
import { Card, Change, Disclaimer, ErrorBox, PageHeader, Seg, Skeleton } from "@/components/ui";
import { useApi } from "@/lib/api";
import { pct, price } from "@/lib/format";

function tileStyle(v: number | null | undefined, mode: "move" | "model", prob?: number | null) {
  if (mode === "model") {
    const p = prob ?? 0.55;
    const t = Math.max(0, Math.min(1, (p - 0.5) / 0.15));
    return { background: `color-mix(in srgb, var(--fg) ${Math.round(t * 85)}%, var(--bg-2))`, color: t > 0.5 ? "var(--bg)" : "var(--fg)" };
  }
  const x = Math.max(-1, Math.min(1, (v ?? 0) / 3));
  if (x >= 0) return { background: `color-mix(in srgb, var(--fg) ${Math.round(x * 85)}%, var(--bg-2))`, color: x > 0.5 ? "var(--bg)" : "var(--fg)" };
  return { background: "var(--panel)", color: "var(--fg)", boxShadow: `inset 0 0 0 ${1 + Math.round(-x * 2)}px var(--fg-${-x > 0.5 ? 2 : 3})` };
}

export default function MarketsPage() {
  const [mode, setMode] = useState<"move" | "model">("move");
  const { data, error, reload } = useApi<any>("/api/market/heatmap", { refreshMs: 90_000 });
  const { data: ov, error: ovError } = useApi<any>("/api/market/overview", { refreshMs: 60_000 });
  return (
    <div>
      <PageHeader
        title="Markets"
        subtitle={mode === "move" ? "Today's move. Darker tiles rose more; outlined tiles fell (thicker outline, larger fall)." : "Neural ensemble P(up over 5 days). Darker tiles carry a stronger bullish tilt."}
        right={<Seg value={mode} onChange={setMode} options={[{ value: "move", label: "Price move" }, { value: "model", label: "Neural tilt" }]} />}
      />
      <ErrorBox error={error} onRetry={reload} />
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-12">
        <div className="space-y-3 xl:col-span-9">
          {!data && !error && <Skeleton h={480} />}
          {data && (
            <div className="columns-1 gap-2 md:columns-2 2xl:columns-3">
              {data.groups.map((g: any) => (
                <Card
                  className="mb-2 break-inside-avoid"
                  key={g.sector}
                  title={g.sector}
                  right={<span className="num text-[11px]"><Change value={g.avg_change_pct} /> <span className="faint ml-1">P(up) {g.avg_prob_up?.toFixed(3) ?? "--"}</span></span>}
                  bodyClass="p-1.5"
                >
                  <div className="grid grid-cols-3 gap-1 sm:grid-cols-4">
                    {g.items.map((it: any) => (
                      <Link key={it.symbol} href={`/symbol/${it.symbol}`} className="rounded-md px-1.5 py-1 transition-opacity hover:opacity-80" style={tileStyle(it.change_pct, mode, it.prob_up)} title={`${it.name}: ${pct(it.change_pct)} · P(up) ${it.prob_up?.toFixed(3) ?? "--"}`}>
                        <div className="truncate text-[11.5px] font-semibold">{it.symbol}</div>
                        <div className="num text-[10.5px] opacity-80">{mode === "move" ? pct(it.change_pct) : it.prob_up?.toFixed(3) ?? "--"}</div>
                      </Link>
                    ))}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
        <div className="space-y-3 xl:col-span-3">
          <Card title="Macro" bodyClass="p-0">
            {!ov ? (ovError ? <div className="p-2"><ErrorBox error={ovError} /></div> : <Skeleton h={300} />) : (
              <table className="tbl">
                <tbody>
                  {ov.macro.map((m: any) => (
                    <tr key={m.symbol}>
                      <td><Link href={`/symbol/${encodeURIComponent(m.symbol)}`} className="hover:underline">{m.label}</Link></td>
                      <td className="r">{price(m.price)}</td>
                      <td className="r"><Change value={m.change_pct} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
          <Card title="Breadth">
            {ov && (
              <div className="space-y-1.5 text-[12px]">
                <div className="flex justify-between"><span className="muted">Advancing</span><b className="num">{ov.breadth.advancing}</b></div>
                <div className="flex justify-between"><span className="muted">Declining</span><b className="num">{ov.breadth.declining}</b></div>
                <div className="flex h-2 overflow-hidden rounded-full bg-bg-3"><div className="bg-fg" style={{ width: `${(ov.breadth.advancing / ov.breadth.universe) * 100}%` }} /></div>
                <div className="faint text-[11px]">{ov.breadth.universe} large caps tracked</div>
              </div>
            )}
          </Card>
        </div>
      </div>
      <Disclaimer />
    </div>
  );
}
