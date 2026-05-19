"use client";
import clsx from "clsx";

interface SectorItem {
  sector: string;
  etf: string;
  change_pct: number;
}

interface Props {
  data: SectorItem[] | undefined;
}

function getColor(pct: number): string {
  if (pct >= 2)   return "bg-emerald-700 text-white";
  if (pct >= 0.5) return "bg-emerald-900/70 text-emerald-300";
  if (pct >= 0)   return "bg-emerald-950/50 text-emerald-500";
  if (pct >= -0.5)return "bg-red-950/50 text-red-500";
  if (pct >= -2)  return "bg-red-900/70 text-red-300";
  return "bg-red-700 text-white";
}

export function SectorHeatmap({ data }: Props) {
  return (
    <div className="card">
      <div className="card-header">Sector Heat Map</div>
      {!data ? (
        <div className="grid grid-cols-3 gap-2">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="h-16 bg-gray-800 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
          {data.map((item) => (
            <div
              key={item.sector}
              className={clsx("rounded-lg p-3 text-center", getColor(item.change_pct))}
            >
              <div className="text-xs font-semibold truncate">{item.sector}</div>
              <div className="text-sm font-bold mt-1">
                {item.change_pct >= 0 ? "+" : ""}{item.change_pct?.toFixed(2)}%
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
