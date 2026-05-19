"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { CorrelationHeatmap } from "@/components/charts/CorrelationHeatmap";
import { SectorPieChart } from "@/components/charts/SectorPieChart";

export default function PortfolioPage() {
  const { data: analysis, isLoading } = useQuery({
    queryKey: ["portfolio-analysis"],
    queryFn: () => api.get("/api/portfolio/analysis").then((r) => r.data),
  });

  const { data: risk } = useQuery({
    queryKey: ["portfolio-risk"],
    queryFn: () => api.get("/api/portfolio/risk").then((r) => r.data),
  });

  const { data: correlation } = useQuery({
    queryKey: ["portfolio-correlation"],
    queryFn: () => api.get("/api/portfolio/correlation").then((r) => r.data),
  });

  if (isLoading) return <div className="p-6 text-gray-400">Loading portfolio...</div>;
  if (!analysis || analysis.message) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-4">Portfolio Brain</h1>
        <div className="card text-center py-12">
          <p className="text-gray-400">No portfolio positions found.</p>
          <p className="text-sm text-gray-500 mt-1">Add your positions to get AI portfolio analysis.</p>
        </div>
      </div>
    );
  }

  const scoreColor = (analysis.health_score ?? 0) >= 70 ? "text-emerald-400" : (analysis.health_score ?? 0) >= 50 ? "text-yellow-400" : "text-red-400";

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <h1 className="text-2xl font-bold">Portfolio Brain</h1>

      {/* Score row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="card text-center">
          <div className={`stat-value ${scoreColor}`}>{analysis.health_score}</div>
          <div className="stat-label">Health Score</div>
        </div>
        <div className="card text-center">
          <div className="stat-value">${(analysis.total_value || 0).toLocaleString()}</div>
          <div className="stat-label">Portfolio Value</div>
        </div>
        <div className="card text-center">
          <div className="stat-value">{analysis.position_count}</div>
          <div className="stat-label">Positions</div>
        </div>
        {risk && (
          <div className="card text-center">
            <div className={`stat-value ${Math.abs(risk.beta_vs_spy - 1) < 0.2 ? "positive" : "text-yellow-400"}`}>
              {risk.beta_vs_spy?.toFixed(2)}
            </div>
            <div className="stat-label">Portfolio Beta</div>
          </div>
        )}
      </div>

      {/* AI Narrative */}
      {analysis.ai_narrative && (
        <div className="card border-l-4 border-blue-500">
          <div className="card-header">AI Portfolio Assessment</div>
          <p className="text-sm text-gray-300 leading-relaxed">{analysis.ai_narrative}</p>
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <div className="card-header">Sector Exposure</div>
          <SectorPieChart data={analysis.sector_weights} />
        </div>
        {correlation && correlation.matrix && (
          <div className="card">
            <div className="card-header">Correlation Matrix</div>
            <CorrelationHeatmap
              tickers={correlation.tickers}
              matrix={correlation.matrix}
            />
            {correlation.highest_correlation && (
              <div className={`mt-3 text-xs px-2 py-1 rounded ${
                correlation.highest_correlation.risk_level === "high" ? "bg-red-900/30 text-red-300" :
                correlation.highest_correlation.risk_level === "medium" ? "bg-yellow-900/30 text-yellow-300" :
                "bg-gray-800 text-gray-400"
              }`}>
                Highest correlation: {correlation.highest_correlation.pair.join(" ↔ ")} = {correlation.highest_correlation.correlation}
                {" "}({correlation.highest_correlation.risk_level} risk)
              </div>
            )}
          </div>
        )}
      </div>

      {/* Risk metrics */}
      {risk && (
        <div className="card">
          <div className="card-header">Risk Metrics</div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: "VaR (95%, 1-day)", value: `${risk.var_95_pct?.toFixed(2)}%`, color: "negative" },
              { label: "CVaR (95%)", value: `${risk.cvar_95_pct?.toFixed(2)}%`, color: "negative" },
              { label: "Max Drawdown", value: `${risk.max_drawdown_pct?.toFixed(2)}%`, color: "negative" },
              { label: "Annualized Vol", value: `${risk.annualized_volatility_pct?.toFixed(2)}%`, color: "" },
            ].map(({ label, value, color }) => (
              <div key={label}>
                <div className={`text-lg font-bold ${color}`}>{value}</div>
                <div className="stat-label">{label}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-gray-500 text-center">
        For educational purposes only. Not financial advice. Past performance is not indicative of future results.
      </p>
    </div>
  );
}
