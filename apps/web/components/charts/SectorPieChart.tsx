"use client";
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#14b8a6"];

interface Props {
  data: Record<string, number> | undefined;
}

export function SectorPieChart({ data }: Props) {
  if (!data) return <div className="h-40 bg-gray-800 animate-pulse rounded-lg" />;

  const chartData = Object.entries(data)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value: Math.round(value * 10) / 10 }))
    .sort((a, b) => b.value - a.value);

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie data={chartData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name} ${value}%`} labelLine={false}>
          {chartData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Pie>
        <Tooltip formatter={(v: any) => `${v}%`} contentStyle={{ background: "#111827", border: "1px solid #374151" }} />
      </PieChart>
    </ResponsiveContainer>
  );
}
