/* Indicator math for chart overlays (computed client-side so toggling never refetches). */

export interface Bar {
  t: number;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
}

export function sma(values: number[], n: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= n) sum -= values[i - n];
    if (i >= n - 1) out[i] = sum / n;
  }
  return out;
}

export function ema(values: number[], n: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  const k = 2 / (n + 1);
  let prev: number | null = null;
  for (let i = 0; i < values.length; i++) {
    if (i < n - 1) continue;
    if (prev == null) {
      let s = 0;
      for (let j = i - n + 1; j <= i; j++) s += values[j];
      prev = s / n;
    } else prev = values[i] * k + prev * (1 - k);
    out[i] = prev;
  }
  return out;
}

export function bollinger(values: number[], n = 20, k = 2) {
  const mid = sma(values, n);
  const upper: (number | null)[] = [];
  const lower: (number | null)[] = [];
  for (let i = 0; i < values.length; i++) {
    const m = mid[i];
    if (m == null) {
      upper.push(null);
      lower.push(null);
      continue;
    }
    let s = 0;
    for (let j = i - n + 1; j <= i; j++) s += (values[j] - m) ** 2;
    const sd = Math.sqrt(s / (n - 1));
    upper.push(m + k * sd);
    lower.push(m - k * sd);
  }
  return { mid, upper, lower };
}

export function rsi(values: number[], n = 14): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  let gain = 0;
  let loss = 0;
  for (let i = 1; i < values.length; i++) {
    const d = values[i] - values[i - 1];
    const g = Math.max(d, 0);
    const l = Math.max(-d, 0);
    if (i <= n) {
      gain += g / n;
      loss += l / n;
      if (i === n) out[i] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
    } else {
      gain = (gain * (n - 1) + g) / n;
      loss = (loss * (n - 1) + l) / n;
      out[i] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
    }
  }
  return out;
}

export function macd(values: number[], fast = 12, slow = 26, signal = 9) {
  const f = ema(values, fast);
  const s = ema(values, slow);
  const line = values.map((_, i) => (f[i] != null && s[i] != null ? (f[i] as number) - (s[i] as number) : null));
  const start = line.findIndex((v) => v != null);
  const sig: (number | null)[] = new Array(values.length).fill(null);
  if (start >= 0) {
    const e = ema(line.slice(start) as number[], signal);
    e.forEach((v, i) => (sig[start + i] = v));
  }
  const hist = line.map((v, i) => (v != null && sig[i] != null ? v - (sig[i] as number) : null));
  return { line, signal: sig, hist };
}

/** Session VWAP for intraday bars (resets each calendar day of the bar timestamps). */
export function vwap(bars: Bar[]): (number | null)[] {
  const out: (number | null)[] = [];
  let day = -1;
  let pv = 0;
  let vol = 0;
  for (const b of bars) {
    const d = Math.floor(b.t / 86400);
    if (d !== day) {
      day = d;
      pv = 0;
      vol = 0;
    }
    const tp = (b.h + b.l + b.c) / 3;
    pv += tp * b.v;
    vol += b.v;
    out.push(vol > 0 ? pv / vol : null);
  }
  return out;
}

export const INDICATORS = [
  { id: "sma20", label: "SMA 20", kind: "overlay" },
  { id: "sma50", label: "SMA 50", kind: "overlay" },
  { id: "sma200", label: "SMA 200", kind: "overlay" },
  { id: "ema21", label: "EMA 21", kind: "overlay" },
  { id: "bb", label: "Bollinger 20,2", kind: "overlay" },
  { id: "vwap", label: "VWAP", kind: "overlay" },
  { id: "volume", label: "Volume", kind: "overlay" },
  { id: "rsi", label: "RSI 14", kind: "pane" },
  { id: "macd", label: "MACD 12,26,9", kind: "pane" },
  { id: "model", label: "Neural P(up)", kind: "pane" },
] as const;
