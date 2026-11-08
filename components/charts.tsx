"use client";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

/** Width of a container in CSS pixels, so SVG text renders at its true size at any card width. */
function useWidth<T extends HTMLElement>(fallback = 600): [React.RefObject<T | null>, number] {
  const ref = useRef<T | null>(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver((entries) => {
      const cw = Math.round(entries[0].contentRect.width);
      if (cw > 0) setW(cw);
    });
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

/* Monochrome SVG charts. Series are distinguished by tone and dash pattern, never by hue. */

export const TONES = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-1)", "var(--chart-2)", "var(--chart-3)"];
export const DASHES = ["", "", "", "4 3", "4 3", "1 3", "6 2 1 2"];

export interface Series {
  name: string;
  values: (number | null)[];
  tone?: string;
  dash?: string;
  width?: number;
  fill?: boolean;
}

function extent(series: Series[], extra: number[] = []) {
  let lo = Infinity;
  let hi = -Infinity;
  for (const s of series) for (const v of s.values) if (v != null && Number.isFinite(v)) (lo = Math.min(lo, v)), (hi = Math.max(hi, v));
  for (const v of extra) (lo = Math.min(lo, v)), (hi = Math.max(hi, v));
  if (!Number.isFinite(lo)) return [0, 1];
  if (lo === hi) return [lo - 1, hi + 1];
  const pad = (hi - lo) * 0.06;
  return [lo - pad, hi + pad];
}

function ticks(lo: number, hi: number, n = 4) {
  const step = (hi - lo) / n;
  return Array.from({ length: n + 1 }, (_, i) => lo + step * i);
}

export function LineChart({
  x, series, height = 200, yFormat = (v: number) => v.toFixed(2), xFormat = (v: string | number) => String(v), refLine, yDomain, legend = true, area,
}: {
  x: (string | number)[];
  series: Series[];
  height?: number;
  yFormat?: (v: number) => string;
  xFormat?: (v: string | number) => string;
  refLine?: { value: number; label?: string };
  yDomain?: [number, number];
  legend?: boolean;
  area?: { upper: (number | null)[]; lower: (number | null)[] };
}) {
  const ref = useRef<SVGSVGElement>(null);
  const [box, W] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const H = height;
  const L = 48;
  const R = 8;
  const T = 8;
  const B = 20;
  const n = x.length;
  const [lo, hi] = yDomain ?? extent(area ? [...series, { name: "u", values: area.upper }, { name: "l", values: area.lower }] : series, refLine ? [refLine.value] : []);
  const sx = (i: number) => L + (n <= 1 ? 0 : (i / (n - 1)) * (W - L - R));
  const sy = (v: number) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const path = (vals: (number | null)[]) => {
    let d = "";
    let pen = false;
    vals.forEach((v, i) => {
      if (v == null || !Number.isFinite(v)) return void (pen = false);
      d += `${pen ? "L" : "M"}${sx(i).toFixed(1)},${sy(v).toFixed(1)}`;
      pen = true;
    });
    return d;
  };
  const band = useMemo(() => {
    if (!area) return "";
    const up = area.upper.map((v, i) => (v == null ? null : `${sx(i).toFixed(1)},${sy(v).toFixed(1)}`)).filter(Boolean);
    const dn = area.lower.map((v, i) => (v == null ? null : `${sx(i).toFixed(1)},${sy(v).toFixed(1)}`)).filter(Boolean).reverse();
    return up.length ? `M${up.join("L")}L${dn.join("L")}Z` : "";
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [area, lo, hi, n, W]);
  const xt = n > 1 ? [0, Math.floor(n / 3), Math.floor((2 * n) / 3), n - 1] : [0];
  const onMove = (e: React.MouseEvent) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r || n < 2) return;
    const px = ((e.clientX - r.left) / r.width) * W;
    setHover(Math.max(0, Math.min(n - 1, Math.round(((px - L) / (W - L - R)) * (n - 1)))));
  };
  return (
    <div className="relative w-full" ref={box}>
      {legend && series.length > 1 && (
        <div className="mb-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px]">
          {series.map((s, i) => (
            <span key={s.name} className="inline-flex items-center gap-1.5">
              <svg width="16" height="6">
                <line x1="0" y1="3" x2="16" y2="3" stroke={s.tone ?? TONES[i]} strokeWidth={s.width ?? 1.6} strokeDasharray={s.dash ?? DASHES[i]} />
              </svg>
              <span className="muted">{s.name}</span>
              {hover != null && <span className="num font-medium">{s.values[hover] == null ? "--" : yFormat(s.values[hover] as number)}</span>}
            </span>
          ))}
        </div>
      )}
      <div className="relative" style={{ height: H }}>
      <svg ref={ref} width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="absolute left-0 top-0" onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
        {ticks(lo, hi).map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={sy(t)} y2={sy(t)} stroke="var(--line)" strokeWidth="1" />
            <text x={L - 6} y={sy(t) + 3} textAnchor="end" fontSize="10" fill="var(--fg-3)" style={{ fontVariantNumeric: "tabular-nums" }}>
              {yFormat(t)}
            </text>
          </g>
        ))}
        {band && <path d={band} fill="var(--chart-fill)" />}
        {refLine && <line x1={L} x2={W - R} y1={sy(refLine.value)} y2={sy(refLine.value)} stroke="var(--fg-3)" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />}
        {series.map((s, i) =>
          s.fill ? (
            <path key={`f${s.name}`} d={`${path(s.values)}L${sx(n - 1)},${H - B}L${sx(s.values.findIndex((v) => v != null))},${H - B}Z`} fill="var(--chart-fill)" />
          ) : null,
        )}
        {series.map((s, i) => (
          <path key={s.name} d={path(s.values)} fill="none" stroke={s.tone ?? TONES[i]} strokeWidth={s.width ?? 1.6} strokeDasharray={s.dash ?? DASHES[i]} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        ))}
        {xt.map((i) => (
          <text key={i} x={sx(i)} y={H - 5} textAnchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"} fontSize="10" fill="var(--fg-3)">
            {x[i] != null ? xFormat(x[i]) : ""}
          </text>
        ))}
        {hover != null && <line x1={sx(hover)} x2={sx(hover)} y1={T} y2={H - B} stroke="var(--fg-3)" vectorEffect="non-scaling-stroke" />}
      </svg>
      </div>
      {hover != null && (!legend || series.length === 1) && (
        <div className="pointer-events-none absolute right-1 top-0 rounded bg-panel px-1.5 text-[11px] shadow">
          <span className="faint">{xFormat(x[hover])}</span> <span className="num font-medium">{series[0].values[hover] == null ? "--" : yFormat(series[0].values[hover] as number)}</span>
        </div>
      )}
    </div>
  );
}

export function Sparkline({ values, width = 72, height = 22 }: { values: (number | null)[]; width?: number; height?: number }) {
  const v = values.filter((x): x is number => x != null && Number.isFinite(x));
  if (v.length < 2) return <span className="faint">--</span>;
  const lo = Math.min(...v);
  const hi = Math.max(...v);
  const d = v.map((y, i) => `${i ? "L" : "M"}${((i / (v.length - 1)) * width).toFixed(1)},${(height - 2 - ((y - lo) / (hi - lo || 1)) * (height - 4)).toFixed(1)}`).join("");
  return (
    <svg width={width} height={height} className="block">
      <path d={d} fill="none" stroke={v[v.length - 1] >= v[0] ? "var(--chart-1)" : "var(--chart-2)"} strokeWidth="1.3" strokeDasharray={v[v.length - 1] >= v[0] ? "" : "2 2"} />
    </svg>
  );
}

/** Horizontal bars diverging from zero (positive solid, negative hollow). */
export function DivergingBars({ rows, format = (v: number) => v.toFixed(2), labelWidth = 110 }: { rows: { label: ReactNode; value: number | null; key?: string; right?: ReactNode }[]; format?: (v: number) => string; labelWidth?: number }) {
  const max = Math.max(1e-9, ...rows.map((r) => Math.abs(r.value ?? 0)));
  return (
    <div className="space-y-1">
      {rows.map((r, i) => {
        const v = r.value ?? 0;
        const w = (Math.abs(v) / max) * 50;
        return (
          <div key={r.key ?? i} className="flex items-center gap-2 text-[12px]">
            <div className="truncate" style={{ width: labelWidth }}>{r.label}</div>
            <div className="relative h-3.5 flex-1">
              <div className="absolute left-1/2 top-0 h-full w-px bg-line-2" />
              {w >= 3 && <div
                className="absolute top-0.5 h-2.5 rounded-sm"
                style={{
                  left: v >= 0 ? "50%" : `${50 - w}%`,
                  width: `${w}%`,
                  background: v >= 0 ? "var(--fg)" : "transparent",
                  border: v < 0 ? "1px solid var(--fg-2)" : "none",
                }}
              />}
            </div>
            <div className="num w-14 text-right">{r.value == null ? "--" : format(v)}</div>
            {r.right}
          </div>
        );
      })}
    </div>
  );
}

export function Bars({ labels, values, height = 140, format = (v: number) => v.toFixed(2), refLine, yDomain }: { labels: string[]; values: number[]; height?: number; format?: (v: number) => string; refLine?: number; yDomain?: [number, number] }) {
  const [lo, hi] = yDomain ?? [Math.min(0, ...values, refLine ?? 0), Math.max(...values, refLine ?? 0) * 1.08 || 1];
  const [box, W] = useWidth<HTMLDivElement>(400);
  const H = height;
  const B = 16;
  const bw = (W / values.length) * 0.7;
  const sy = (v: number) => (1 - (v - lo) / (hi - lo || 1)) * (H - B - 12) + 12;
  return (
    <div ref={box} className="relative w-full" style={{ height: H }}>
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="absolute left-0 top-0">
      {values.map((v, i) => {
        const x = (i + 0.15) * (W / values.length);
        const y0 = sy(Math.max(lo, 0));
        const y = sy(v);
        return (
          <g key={i}>
            <rect x={x} y={Math.min(y, y0)} width={bw} height={Math.abs(y0 - y)} fill="var(--chart-1)" opacity={0.25 + 0.75 * ((v - lo) / (hi - lo || 1))} rx="2" />
            <text x={x + bw / 2} y={Math.min(y, y0) - 3} textAnchor="middle" fontSize="9.5" fill="var(--fg-2)">{format(v)}</text>
            <text x={x + bw / 2} y={H - 3} textAnchor="middle" fontSize="9.5" fill="var(--fg-3)">{labels[i]}</text>
          </g>
        );
      })}
      {refLine != null && <line x1="0" x2={W} y1={sy(refLine)} y2={sy(refLine)} stroke="var(--fg-2)" strokeDasharray="4 3" />}
    </svg>
    </div>
  );
}

/** Grayscale matrix heatmap (correlation, saliency, attention, confusion). */
export function Heatmap({ matrix, rowLabels, colLabels, min, max, format = (v: number) => v.toFixed(2), cell = 0, showValues = true, signed = false }: { matrix: number[][]; rowLabels?: string[]; colLabels?: string[]; min?: number; max?: number; format?: (v: number) => string; cell?: number; showValues?: boolean; signed?: boolean }) {
  const flat = matrix.flat();
  const lo = min ?? Math.min(...flat);
  const hi = max ?? Math.max(...flat);
  const cols = matrix[0]?.length ?? 0;
  return (
    <div className="overflow-x-auto">
      <div className="inline-grid min-w-full gap-px" style={{ gridTemplateColumns: `${rowLabels ? "auto " : ""}repeat(${cols}, minmax(${cell || 14}px, 1fr))` }}>
        {colLabels && (
          <>
            {rowLabels && <div />}
            {colLabels.map((c, j) => (
              <div key={j} className="faint truncate pb-0.5 text-center text-[9.5px]" title={c}>{c}</div>
            ))}
          </>
        )}
        {matrix.map((row, i) => (
          <div key={i} className="contents">
            {rowLabels && <div className="faint truncate pr-1.5 text-right text-[10px] leading-[18px]">{rowLabels[i]}</div>}
            {row.map((v, j) => {
              const t = signed ? Math.min(1, Math.abs(v) / Math.max(Math.abs(lo), Math.abs(hi), 1e-9)) : (v - lo) / (hi - lo || 1);
              const dark = t > 0.55;
              return (
                <div
                  key={j}
                  className="num flex items-center justify-center text-[9.5px]"
                  title={`${rowLabels?.[i] ?? i} / ${colLabels?.[j] ?? j}: ${format(v)}`}
                  style={{
                    minHeight: 18,
                    background: signed && v < 0 ? `color-mix(in srgb, var(--fg-2) ${Math.round(t * 70)}%, var(--bg-2))` : `color-mix(in srgb, var(--fg) ${Math.round(t * 88)}%, var(--bg-2))`,
                    color: dark ? "var(--bg)" : "var(--fg-2)",
                    outline: signed && v < 0 ? "1px dashed var(--line-2)" : undefined,
                  }}
                >
                  {showValues ? format(v) : ""}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

export function Histogram({ counts, edges, height = 110, format = (v: number) => v.toFixed(2), marker }: { counts: number[]; edges: number[]; height?: number; format?: (v: number) => string; marker?: number }) {
  const [box, W] = useWidth<HTMLDivElement>(400);
  const H = height;
  const max = Math.max(...counts, 1);
  const bw = W / counts.length;
  const lo = edges[0];
  const hi = edges[edges.length - 1];
  return (
    <div ref={box} className="relative w-full" style={{ height: H }}>
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="absolute left-0 top-0">
      {counts.map((c, i) => (
        <rect key={i} x={i * bw + 0.5} y={H - 14 - (c / max) * (H - 20)} width={bw - 1} height={(c / max) * (H - 20)} fill={edges[i + 1] <= 0 ? "var(--chart-3)" : "var(--chart-1)"} />
      ))}
      {marker != null && <line x1={((marker - lo) / (hi - lo)) * W} x2={((marker - lo) / (hi - lo)) * W} y1="0" y2={H - 14} stroke="var(--fg-2)" strokeDasharray="3 3" />}
      <text x="0" y={H - 2} fontSize="9.5" fill="var(--fg-3)">{format(lo)}</text>
      <text x={W} y={H - 2} fontSize="9.5" textAnchor="end" fill="var(--fg-3)">{format(hi)}</text>
    </svg>
    </div>
  );
}

export function Dots({ value, total = 4 }: { value: number; total?: number }) {
  return (
    <span className="inline-flex gap-0.5" title={`${value} of ${total}`}>
      {Array.from({ length: total }).map((_, i) => (
        <span key={i} className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: i < value ? "var(--fg)" : "var(--line-2)" }} />
      ))}
    </span>
  );
}
