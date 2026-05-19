"use client";
import clsx from "clsx";

interface Props {
  tickers: string[];
  matrix: number[][];
}

function getHeatColor(value: number): string {
  if (value >= 0.8)  return "bg-red-600 text-white";
  if (value >= 0.6)  return "bg-red-900/60 text-red-300";
  if (value >= 0.3)  return "bg-gray-800 text-gray-300";
  if (value >= -0.3) return "bg-gray-850 text-gray-400";
  if (value >= -0.6) return "bg-blue-900/60 text-blue-300";
  return "bg-blue-600 text-white";
}

export function CorrelationHeatmap({ tickers, matrix }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="text-xs min-w-full">
        <thead>
          <tr>
            <th className="p-1 text-gray-500" />
            {tickers.map((t) => (
              <th key={t} className="p-1 text-gray-400 font-semibold">{t}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tickers.map((rowTicker, ri) => (
            <tr key={rowTicker}>
              <td className="p-1 text-gray-400 font-semibold pr-2">{rowTicker}</td>
              {matrix[ri]?.map((val, ci) => (
                <td key={ci} className="p-0.5">
                  <div className={clsx("rounded p-1 text-center font-mono min-w-[40px]", getHeatColor(val))}>
                    {val?.toFixed(2)}
                  </div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
