"use client";

interface Props {
  data: any;
}

export function NewsIntelligence({ data }: Props) {
  if (!data) return <div className="card text-gray-500 text-sm">Loading news intelligence...</div>;

  const toneColor = data.tone === "bullish" ? "badge-bullish" : data.tone === "bearish" ? "badge-bearish" : "badge-neutral";

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div className="card-header mb-0">News Intelligence</div>
        <div className="flex gap-2">
          <span className={toneColor}>{data.tone}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            data.severity === "critical" ? "bg-red-900/50 text-red-400" :
            data.severity === "high" ? "bg-orange-900/50 text-orange-400" :
            "badge-neutral"
          }`}>{data.severity}</span>
        </div>
      </div>

      <p className="text-sm text-gray-300 mb-3 leading-relaxed">{data.summary}</p>

      {data.articles?.length > 0 && (
        <div className="space-y-2">
          {data.articles.slice(0, 4).map((a: any, i: number) => (
            <a
              key={i}
              href={a.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block text-xs text-gray-400 hover:text-white transition-colors border-b border-gray-800 pb-1"
            >
              {a.title} <span className="text-gray-600">— {a.source}</span>
            </a>
          ))}
        </div>
      )}

      <p className="text-xs text-gray-600 mt-3">{data.disclaimer}</p>
    </div>
  );
}
