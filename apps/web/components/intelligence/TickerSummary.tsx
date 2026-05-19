"use client";

interface Props {
  data: any;
  loading: boolean;
}

export function TickerSummary({ data, loading }: Props) {
  return (
    <div className="card">
      <div className="card-header">AI Intelligence Summary</div>
      {loading ? (
        <div className="space-y-2">
          {[90, 75, 85, 60].map((w) => (
            <div key={w} className="h-3 bg-gray-800 rounded animate-pulse" style={{ width: `${w}%` }} />
          ))}
        </div>
      ) : data ? (
        <>
          <p className="text-sm text-gray-300 leading-relaxed">{data.summary}</p>
          <p className="text-xs text-gray-600 mt-3">{data.disclaimer}</p>
        </>
      ) : (
        <p className="text-sm text-gray-500">Summary unavailable.</p>
      )}
    </div>
  );
}
