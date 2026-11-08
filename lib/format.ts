const MINUS = "−";

export function num(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return "--";
  return v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits }).replace("-", MINUS);
}

export function price(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "--";
  const d = Math.abs(v) >= 1000 ? 2 : Math.abs(v) >= 1 ? 2 : 4;
  return num(v, d);
}

/** Signed percent from a percent value (1.23 -> "+1.23%"). */
export function pct(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return "--";
  const s = Math.abs(v).toFixed(digits);
  return `${v > 0 ? "+" : v < 0 ? MINUS : ""}${s}%`;
}

/** Signed percent from a fraction (0.0123 -> "+1.23%"). */
export function fpct(v: number | null | undefined, digits = 2): string {
  return v == null || !Number.isFinite(v) ? "--" : pct(v * 100, digits);
}

/** Unsigned percent from a fraction (0.55 -> "55.0%"). */
export function rate(v: number | null | undefined, digits = 1): string {
  return v == null || !Number.isFinite(v) ? "--" : `${(v * 100).toFixed(digits)}%`;
}

export function compact(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "--";
  return Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 }).format(v);
}

export function signClass(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v) || v === 0) return "muted";
  return v > 0 ? "font-semibold" : "muted";
}

export function ago(iso?: string | null): string {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return iso;
  const s = Math.round((Date.now() - t) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

export function downloadFile(name: string, content: string, type = "application/json") {
  const blob = new Blob([content], { type });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

export function toCSV(rows: Record<string, unknown>[]): string {
  if (!rows.length) return "";
  const cols = Object.keys(rows[0]);
  const esc = (v: unknown) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
}
