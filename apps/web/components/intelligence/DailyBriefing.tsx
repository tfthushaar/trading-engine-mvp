"use client";
import { AlertCircle } from "lucide-react";

interface Props {
  data: any;
  loading: boolean;
}

export function DailyBriefing({ data, loading }: Props) {
  return (
    <div className="card border-l-4 border-blue-500">
      <div className="flex items-center gap-2 mb-3">
        <AlertCircle size={16} className="text-blue-400" />
        <span className="card-header mb-0">
          AI Market Briefing — {data?.date ?? new Date().toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
        </span>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[80, 70, 90].map((w) => (
            <div key={w} className={`h-3 bg-gray-800 rounded animate-pulse`} style={{ width: `${w}%` }} />
          ))}
        </div>
      ) : data ? (
        <div className="space-y-3">
          <p className="text-sm text-gray-300 leading-relaxed line-clamp-4">{data.briefing}</p>
          {data.top_catalysts?.length > 0 && (
            <div>
              <div className="text-xs text-gray-500 font-semibold mb-1">TOP CATALYSTS</div>
              <ul className="space-y-1">
                {data.top_catalysts.map((c: string, i: number) => (
                  <li key={i} className="text-xs text-gray-300 flex gap-2">
                    <span className="text-blue-400">→</span> {c}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <p className="text-sm text-gray-500">Briefing unavailable. Check API connection.</p>
      )}
      {data?.disclaimer && (
        <p className="text-xs text-gray-600 mt-3">{data.disclaimer}</p>
      )}
    </div>
  );
}
