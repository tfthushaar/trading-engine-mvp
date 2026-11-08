"use client";
import {
  AreaSeries, CandlestickSeries, ColorType, createChart, createSeriesMarkers, CrosshairMode, HistogramSeries, LineSeries, LineStyle,
  type IChartApi, type ISeriesApi, type SeriesMarker, type Time, type UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";
import { compact, price as fmtPrice } from "@/lib/format";
import { bollinger, ema, macd, rsi, sma, vwap, type Bar } from "@/lib/indicators";

export interface ModelPoint {
  t: number;
  p: number;
}
export interface TradeMarker {
  t: number;
  kind: "entry" | "exit";
}

function css(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
}

/**
 * TradingView-style chart (lightweight-charts by TradingView), styled monochrome.
 * Up candles hollow, down candles solid. Overlays and lower panes are toggled by `indicators`.
 */
export function PriceChart({
  bars, type = "candles", indicators = [], intraday = false, model, markers, height = 420, theme,
}: {
  bars: Bar[];
  type?: "candles" | "line" | "area";
  indicators?: string[];
  intraday?: boolean;
  model?: ModelPoint[];
  markers?: TradeMarker[];
  height?: number;
  theme?: string;
}) {
  const el = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const mainRef = useRef<ISeriesApi<any> | null>(null);
  const [legend, setLegend] = useState<{ o?: number; h?: number; l?: number; c?: number; v?: number; chg?: number; time?: string } | null>(null);
  const last = bars[bars.length - 1];

  const closes = useMemo(() => bars.map((b) => b.c), [bars]);

  useEffect(() => {
    if (!el.current || !bars.length) return;
    const fg = css("--fg");
    const fg2 = css("--fg-2");
    const fg3 = css("--fg-3");
    const line = css("--line");
    const bg = css("--panel");
    const chart = createChart(el.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: bg }, textColor: fg3, fontSize: 11, fontFamily: getComputedStyle(document.body).fontFamily, panes: { separatorColor: line, separatorHoverColor: line, enableResize: true } },
      grid: { vertLines: { color: line, style: LineStyle.Solid, visible: false }, horzLines: { color: line } },
      rightPriceScale: { borderColor: line, scaleMargins: { top: 0.08, bottom: 0.08 } },
      timeScale: { borderColor: line, timeVisible: intraday, secondsVisible: false, rightOffset: 3, minBarSpacing: 1 },
      crosshair: { mode: CrosshairMode.Normal, vertLine: { color: fg3, labelBackgroundColor: fg }, horzLine: { color: fg3, labelBackgroundColor: fg } },
      localization: { priceFormatter: (p: number) => fmtPrice(p) },
    });
    chartRef.current = chart;
    const t = (b: { t: number }) => b.t as UTCTimestamp;

    let main: ISeriesApi<any>;
    if (type === "candles") {
      main = chart.addSeries(CandlestickSeries, { upColor: bg, downColor: fg, borderUpColor: fg, borderDownColor: fg, wickUpColor: fg, wickDownColor: fg, priceLineColor: fg2 });
      main.setData(bars.map((b) => ({ time: t(b), open: b.o, high: b.h, low: b.l, close: b.c })));
    } else if (type === "area") {
      main = chart.addSeries(AreaSeries, { lineColor: fg, lineWidth: 2, topColor: css("--chart-fill"), bottomColor: "rgba(0,0,0,0)", priceLineColor: fg2 });
      main.setData(bars.map((b) => ({ time: t(b), value: b.c })));
    } else {
      main = chart.addSeries(LineSeries, { color: fg, lineWidth: 2, priceLineColor: fg2 });
      main.setData(bars.map((b) => ({ time: t(b), value: b.c })));
    }
    mainRef.current = main;

    const overlay = (vals: (number | null)[], color: string, style = LineStyle.Solid, width: 1 | 2 = 1) => {
      const s = chart.addSeries(LineSeries, { color, lineWidth: width, lineStyle: style, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
      s.setData(bars.map((b, i) => (vals[i] == null ? { time: t(b) } : { time: t(b), value: vals[i] as number })));
    };
    if (indicators.includes("sma20")) overlay(sma(closes, 20), fg2, LineStyle.Solid);
    if (indicators.includes("sma50")) overlay(sma(closes, 50), fg2, LineStyle.Dashed);
    if (indicators.includes("sma200")) overlay(sma(closes, 200), fg3, LineStyle.Solid, 2);
    if (indicators.includes("ema21")) overlay(ema(closes, 21), fg2, LineStyle.Dotted);
    if (indicators.includes("bb")) {
      const b = bollinger(closes);
      overlay(b.upper, fg3, LineStyle.Dashed);
      overlay(b.mid, fg3, LineStyle.Dotted);
      overlay(b.lower, fg3, LineStyle.Dashed);
    }
    if (indicators.includes("vwap") && intraday) overlay(vwap(bars), fg2, LineStyle.LargeDashed, 2);
    if (indicators.includes("volume")) {
      const v = chart.addSeries(HistogramSeries, { priceScaleId: "vol", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
      v.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
      v.setData(bars.map((b, i) => ({ time: t(b), value: b.v, color: i > 0 && b.c >= bars[i - 1].c ? css("--fg-4") : css("--fg-3") })));
    }
    let pane = 1;
    if (indicators.includes("rsi")) {
      const r = chart.addSeries(LineSeries, { color: fg, lineWidth: 1, priceLineVisible: false }, pane);
      r.setData(bars.map((b, i) => { const v = rsi(closes)[i]; return v == null ? { time: t(b) } : { time: t(b), value: v }; }));
      r.createPriceLine({ price: 70, color: fg3, lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: false });
      r.createPriceLine({ price: 30, color: fg3, lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: false });
      pane++;
    }
    if (indicators.includes("macd")) {
      const m = macd(closes);
      const h = chart.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false }, pane);
      h.setData(bars.map((b, i) => (m.hist[i] == null ? { time: t(b) } : { time: t(b), value: m.hist[i] as number, color: (m.hist[i] as number) >= 0 ? fg2 : css("--fg-4") })));
      const l = chart.addSeries(LineSeries, { color: fg, lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane);
      l.setData(bars.map((b, i) => (m.line[i] == null ? { time: t(b) } : { time: t(b), value: m.line[i] as number })));
      const s = chart.addSeries(LineSeries, { color: fg3, lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false }, pane);
      s.setData(bars.map((b, i) => (m.signal[i] == null ? { time: t(b) } : { time: t(b), value: m.signal[i] as number })));
      pane++;
    }
    if (indicators.includes("model") && model?.length) {
      const first = bars[0].t;
      const pts = model.filter((p) => p.t >= first);
      if (pts.length) {
        const s = chart.addSeries(AreaSeries, { lineColor: fg, lineWidth: 1, topColor: css("--chart-fill"), bottomColor: "rgba(0,0,0,0)", priceLineVisible: false, priceFormat: { type: "custom", formatter: (v: number) => v.toFixed(3) } }, pane);
        s.setData(pts.map((p) => ({ time: p.t as UTCTimestamp, value: p.p })));
        s.createPriceLine({ price: 0.5, color: fg3, lineStyle: LineStyle.Dotted, lineWidth: 1, axisLabelVisible: false, title: "0.50" });
        pane++;
      }
    }
    const panes = chart.panes();
    for (let i = 1; i < panes.length; i++) panes[i].setHeight(Math.round(height * 0.16));

    if (markers?.length) {
      const ms: SeriesMarker<Time>[] = markers.map((m) => ({
        time: m.t as UTCTimestamp, position: m.kind === "entry" ? "belowBar" : "aboveBar", shape: m.kind === "entry" ? "arrowUp" : "arrowDown", color: fg, size: 1,
      }));
      createSeriesMarkers(main, ms);
    }

    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData) return setLegend(null);
      const d: any = param.seriesData.get(main);
      if (!d) return setLegend(null);
      const idx = bars.findIndex((b) => b.t === (param.time as number));
      const b = bars[idx];
      const prev = idx > 0 ? bars[idx - 1].c : undefined;
      setLegend({
        o: b?.o, h: b?.h, l: b?.l, c: b?.c ?? d.value, v: b?.v,
        chg: prev ? ((b.c / prev - 1) * 100) : undefined,
        time: new Date((param.time as number) * 1000).toISOString().slice(0, intraday ? 16 : 10).replace("T", " "),
      });
    });
    chart.timeScale().fitContent();
    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [bars, type, indicators, intraday, model, markers, height, closes, theme]);

  const show = legend ?? (last ? { o: last.o, h: last.h, l: last.l, c: last.c, v: last.v } : null);
  return (
    <div className="relative">
      {show && (
        <div className="num pointer-events-none absolute left-2 top-1 z-10 flex flex-wrap gap-x-2.5 text-[11px]">
          {legend?.time && <span className="faint">{legend.time}</span>}
          <span><span className="faint">O</span> {fmtPrice(show.o)}</span>
          <span><span className="faint">H</span> {fmtPrice(show.h)}</span>
          <span><span className="faint">L</span> {fmtPrice(show.l)}</span>
          <span><span className="faint">C</span> <b>{fmtPrice(show.c)}</b></span>
          {show.v != null && <span><span className="faint">V</span> {compact(show.v)}</span>}
          {legend?.chg != null && <span className={legend.chg >= 0 ? "font-semibold" : "muted"}>{legend.chg >= 0 ? "+" : "−"}{Math.abs(legend.chg).toFixed(2)}%</span>}
        </div>
      )}
      <div ref={el} style={{ height }} />
    </div>
  );
}
