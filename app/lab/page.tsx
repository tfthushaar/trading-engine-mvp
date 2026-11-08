"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Fragment, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Download, Play, RotateCcw, Square, Trash2 } from "lucide-react";
import { Bars, Heatmap, LineChart, TONES } from "@/components/charts";
import { Card, Disclaimer, Empty, ErrorBox, Field, PageHeader, Seg, SignalPill, Skeleton, Spinner, Stat } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { downloadFile, fpct, num, rate, toCSV } from "@/lib/format";
import { KEYS, useStored } from "@/lib/store";

interface Config {
  symbol: string;
  interval: string;
  period: string;
  task: "classification" | "regression";
  arch: string;
  arch_params: Record<string, number>;
  features: string[];
  window: number;
  horizon: number;
  threshold: number;
  cost_bps: number;
  long_short: boolean;
  train: Record<string, any>;
}
const DEFAULT_CONFIG: Config = {
  symbol: "SPY", interval: "1d", period: "10y", task: "classification", arch: "lstm", arch_params: {}, features: [], window: 30, horizon: 5,
  threshold: 0.5, cost_bps: 5, long_short: false,
  train: { epochs: 60, batch_size: 64, lr: 0.001, optimizer: "adamw", weight_decay: 0.0001, patience: 12, clip_norm: 1, schedule: "cosine", seed: 42, time_budget_s: 20 },
};
interface Experiment { id: string; at: number; config: Config; result: any }

/* ---------------------------------------------------------------------------------------------- */
function ConfigPanel({ cfg, setCfg, opts, compact = false }: { cfg: Config; setCfg: (c: Config) => void; opts: any; compact?: boolean }) {
  const arch = opts?.architectures?.[cfg.arch];
  const set = (patch: Partial<Config>) => setCfg({ ...cfg, ...patch });
  const setTrain = (k: string, v: any) => setCfg({ ...cfg, train: { ...cfg.train, [k]: v } });
  const features: string[] = cfg.features.length ? cfg.features : opts?.default_features ?? [];
  const periods: string[] = opts?.intervals?.[cfg.interval]?.periods ?? [];
  const n = (v: string) => (v === "" ? 0 : Number(v));
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <Field label="Symbol"><input className="input font-semibold uppercase" value={cfg.symbol} onChange={(e) => set({ symbol: e.target.value.toUpperCase() })} /></Field>
        <Field label="Task">
          <select className="select" value={cfg.task} onChange={(e) => set({ task: e.target.value as Config["task"] })}>
            <option value="classification">Direction (up / down)</option>
            <option value="regression">Return (magnitude)</option>
          </select>
        </Field>
        <Field label="Bar size">
          <Seg value={cfg.interval} onChange={(v) => set({ interval: v, period: opts?.intervals?.[v]?.periods?.[v === "1h" ? 4 : 2] ?? cfg.period })} options={Object.entries(opts?.intervals ?? { "1d": { label: "1 day" } }).map(([k, v]: any) => ({ value: k, label: v.label.replace("1 ", "") }))} />
        </Field>
        <Field label="History">
          <select className="select" value={periods.includes(cfg.period) ? cfg.period : ""} onChange={(e) => set({ period: e.target.value })}>
            {periods.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </Field>
        <Field label="Window (bars)" hint="Look-back fed to the network"><input className="input num" type="number" min={5} max={120} value={cfg.window} onChange={(e) => set({ window: n(e.target.value) })} /></Field>
        <Field label="Horizon (bars)" hint="How far ahead to predict"><input className="input num" type="number" min={1} max={20} value={cfg.horizon} onChange={(e) => set({ horizon: n(e.target.value) })} /></Field>
      </div>
      {!compact && (
        <div>
          <span className="label">Architecture</span>
          <div className="grid grid-cols-2 gap-1.5">
            {Object.entries(opts?.architectures ?? {}).map(([k, a]: any) => (
              <button key={k} type="button" onClick={() => set({ arch: k, arch_params: {} })} className={`rounded-lg border px-2 py-1.5 text-left ${cfg.arch === k ? "border-fg bg-bg-2" : "border-line hover:border-line-2"}`}>
                <div className="flex items-center justify-between text-[12px] font-semibold">{a.name}<span className="faint text-[10px] font-normal">{a.family}</span></div>
              </button>
            ))}
          </div>
          {arch && <p className="faint mt-1 text-[11px] leading-snug">{arch.summary}</p>}
        </div>
      )}
      {!compact && arch && Object.keys(arch.defaults).length > 0 && (
        <div className="grid grid-cols-3 gap-2">
          {Object.entries(arch.defaults).map(([k, d]: any) => (
            <Field key={k} label={k.replace("_", " ")} hint={`${arch.limits[k][0]} to ${arch.limits[k][1]}`}>
              <input className="input num" type="number" step={k === "dropout" ? 0.05 : 1} value={cfg.arch_params[k] ?? d} onChange={(e) => set({ arch_params: { ...cfg.arch_params, [k]: Number(e.target.value) } })} />
            </Field>
          ))}
        </div>
      )}
      <details className="rounded-lg border border-line" open={!compact}>
        <summary className="cursor-pointer px-2.5 py-1.5 text-[12px] font-medium">Input features ({features.length})</summary>
        <div className="flex flex-wrap gap-1 px-2.5 pb-2">
          {Object.entries(opts?.features ?? {}).map(([k, label]: any) => (
            <button key={k} type="button" className="chip" title={label} data-on={features.includes(k)} onClick={() => set({ features: features.includes(k) ? features.filter((f) => f !== k) : [...features, k] })}>{k}</button>
          ))}
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => set({ features: [] })}>Defaults</button>
        </div>
      </details>
      <details className="rounded-lg border border-line" open={!compact}>
        <summary className="cursor-pointer px-2.5 py-1.5 text-[12px] font-medium">Training</summary>
        <div className="grid grid-cols-3 gap-2 px-2.5 pb-2.5">
          <Field label="Epochs"><input className="input num" type="number" value={cfg.train.epochs} onChange={(e) => setTrain("epochs", n(e.target.value))} /></Field>
          <Field label="Batch"><input className="input num" type="number" value={cfg.train.batch_size} onChange={(e) => setTrain("batch_size", n(e.target.value))} /></Field>
          <Field label="Learning rate"><input className="input num" type="number" step="0.0001" value={cfg.train.lr} onChange={(e) => setTrain("lr", Number(e.target.value))} /></Field>
          <Field label="Optimizer"><select className="select" value={cfg.train.optimizer} onChange={(e) => setTrain("optimizer", e.target.value)}><option value="adamw">AdamW</option><option value="adam">Adam</option><option value="sgd">SGD + momentum</option></select></Field>
          <Field label="Weight decay"><input className="input num" type="number" step="0.0001" value={cfg.train.weight_decay} onChange={(e) => setTrain("weight_decay", Number(e.target.value))} /></Field>
          <Field label="Schedule"><select className="select" value={cfg.train.schedule} onChange={(e) => setTrain("schedule", e.target.value)}><option value="cosine">Cosine</option><option value="constant">Constant</option></select></Field>
          <Field label="Patience"><input className="input num" type="number" value={cfg.train.patience} onChange={(e) => setTrain("patience", n(e.target.value))} /></Field>
          <Field label="Clip norm"><input className="input num" type="number" step="0.1" value={cfg.train.clip_norm} onChange={(e) => setTrain("clip_norm", Number(e.target.value))} /></Field>
          <Field label="Seed"><input className="input num" type="number" value={cfg.train.seed} onChange={(e) => setTrain("seed", n(e.target.value))} /></Field>
          <Field label="Time budget (s)" className="col-span-3" hint="Training stops when the budget is used; the best epoch is kept."><input className="input num" type="number" min={2} max={50} value={cfg.train.time_budget_s} onChange={(e) => setTrain("time_budget_s", n(e.target.value))} /></Field>
        </div>
      </details>
      <details className="rounded-lg border border-line">
        <summary className="cursor-pointer px-2.5 py-1.5 text-[12px] font-medium">Backtest rule</summary>
        <div className="grid grid-cols-3 gap-2 px-2.5 pb-2.5">
          <Field label="Threshold"><input className="input num" type="number" step="0.01" min={0.5} max={0.7} value={cfg.threshold} onChange={(e) => set({ threshold: Number(e.target.value) })} /></Field>
          <Field label="Cost (bps)"><input className="input num" type="number" value={cfg.cost_bps} onChange={(e) => set({ cost_bps: Number(e.target.value) })} /></Field>
          <Field label="Shorts"><select className="select" value={cfg.long_short ? "1" : "0"} onChange={(e) => set({ long_short: e.target.value === "1" })}><option value="0">Long / flat</option><option value="1">Long / short</option></select></Field>
        </div>
      </details>
    </div>
  );
}

function payload(cfg: Config) {
  return { ...cfg, features: cfg.features.length ? cfg.features : null };
}

/* ---------------------------------------------------------------------------------------------- */
function Results({ r }: { r: any }) {
  const cls = r.task === "classification";
  const m = r.test.metrics;
  const b = r.test.baselines;
  const h = r.training.history;
  const bt = r.backtest;
  const f = r.forecast;
  const metricRows = cls
    ? [["Accuracy", "accuracy"], ["Balanced accuracy", "balanced_accuracy"], ["ROC AUC", "auc"], ["Log loss", "log_loss"], ["Brier score", "brier"], ["Precision (up)", "precision_up"], ["Predicted up rate", "predicted_up_rate"]]
    : [["Directional accuracy", "directional_accuracy"], ["Information coefficient", "ic"], ["Rank IC", "rank_ic"], ["RMSE", "rmse"], ["MAE", "mae"], ["R2 vs zero", "r2_vs_zero"]];
  const baseKeys = Object.keys(b);
  const better = (k: string) => (["log_loss", "brier", "rmse", "mae"].includes(k) ? -1 : 1);
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 rounded-[10px] border border-line bg-panel p-3 sm:grid-cols-3 xl:grid-cols-6">
        <Stat label={cls ? "Test accuracy" : "Directional acc."} value={rate(cls ? m.accuracy : m.directional_accuracy)} sub={cls ? `base rate ${rate(b.majority_class?.accuracy)}` : `IC ${num(m.ic, 3)}`} strong />
        <Stat label={cls ? "ROC AUC" : "R2 vs zero"} value={num(cls ? m.auc : m.r2_vs_zero, 3)} sub={b.linear ? `linear ${num(cls ? b.linear.auc : b.linear.r2_vs_zero, 3)}` : "0.5 = no skill"} />
        <Stat label="Strategy Sharpe" value={num(bt.metrics.model.sharpe)} sub={`buy and hold ${num(bt.metrics.buy_hold.sharpe)}`} />
        <Stat label="Strategy return" value={fpct(bt.metrics.model.total_return)} sub={`buy and hold ${fpct(bt.metrics.buy_hold.total_return)}`} />
        <Stat label="Parameters" value={r.model.summary.total_params.toLocaleString()} sub={`${r.model.name} · ${r.training.epochs_run} epochs`} />
        <Stat label={`Forecast ${f.horizon_bars} bars`} value={cls ? f.prob_up.toFixed(3) : fpct(f.expected_log_return)} sub={<><SignalPill signal={f.signal} /> {f.uncertainty ? `± ${f.uncertainty.std.toFixed(3)}` : ""}</>} />
      </div>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <Card title="Training curves" right={<span className="faint text-[11px]">best epoch {r.training.best_epoch} · stopped by {r.training.stopped.replace("_", " ")} · {r.training.seconds}s</span>}>
          <LineChart x={h.epoch} series={[{ name: "Train loss", values: h.train_loss }, { name: "Validation loss", values: h.val_loss, dash: "4 3" }]} height={170} yFormat={(v) => v.toFixed(4)} />
          <div className="mt-2 grid grid-cols-2 gap-3">
            <LineChart x={h.epoch} series={[{ name: cls ? "Train acc" : "Train dir.", values: h.train_metric }, { name: cls ? "Val acc" : "Val dir.", values: h.val_metric, dash: "4 3" }]} height={110} yFormat={(v) => v.toFixed(3)} />
            <LineChart x={h.epoch} series={[{ name: "Learning rate", values: h.lr }, { name: "Grad norm", values: h.grad_norm.map((g: number) => g * Math.max(...h.lr) / Math.max(...h.grad_norm, 1e-9)), dash: "1 3" }]} height={110} yFormat={(v) => v.toExponential(1)} />
          </div>
        </Card>
        <Card title="Test metrics vs baselines" right={<span className="faint text-[11px]">{r.data.splits.test.start} to {r.data.splits.test.end} · n={r.data.splits.test.n}</span>} bodyClass="p-0">
          <table className="tbl">
            <thead><tr><th>Metric</th><th className="r">{r.model.name}</th>{baseKeys.map((k) => <th key={k} className="r">{k.replace(/_/g, " ")}</th>)}</tr></thead>
            <tbody>
              {metricRows.map(([label, k]) => {
                const v = m[k];
                const best = baseKeys.every((bk) => b[bk][k] == null || v == null || (v - b[bk][k]) * better(k) >= 0);
                return (
                  <tr key={k}><td>{label}</td><td className={`r num ${best ? "font-semibold" : ""}`}>{num(v, 4)}</td>{baseKeys.map((bk) => <td key={bk} className="r num muted">{num(b[bk][k], 4)}</td>)}</tr>
                );
              })}
            </tbody>
          </table>
          {cls && (
            <div className="grid grid-cols-2 gap-3 border-t border-line p-3">
              <div>
                <div className="eyebrow mb-1">Confusion matrix</div>
                <Heatmap matrix={m.confusion} rowLabels={["actual down", "actual up"]} colLabels={["pred down", "pred up"]} format={(v) => String(Math.round(v))} />
              </div>
              <div>
                <div className="eyebrow mb-1">Calibration · ECE {num(r.test.calibration?.ece, 3)}</div>
                <Bars labels={r.test.calibration.bins.map((x: any) => x.mean_prob.toFixed(2))} values={r.test.calibration.bins.map((x: any) => x.frequency)} height={110} format={(v) => v.toFixed(2)} yDomain={[0, 1]} />
                <p className="faint text-[10.5px]">Observed up frequency per predicted-probability bin.</p>
              </div>
            </div>
          )}
        </Card>
        <Card title="Out-of-sample backtest" right={<span className="faint text-[11px]">{bt.rule} · {bt.cost_bps} bps</span>}>
          <LineChart x={bt.dates} series={[{ name: r.model.name, values: bt.equity.model, width: 2 }, ...(bt.equity.linear ? [{ name: "Linear baseline", values: bt.equity.linear, dash: "4 3" }] : []), { name: "Buy and hold", values: bt.equity.buy_hold, tone: TONES[2] }]} height={190} yFormat={(v) => v.toFixed(2)} xFormat={(d) => String(d).slice(0, 7)} />
          <table className="tbl mt-2">
            <thead><tr><th /><th className="r">Sharpe</th><th className="r">Return</th><th className="r">Max DD</th><th className="r">Vol</th><th className="r">Exposure</th></tr></thead>
            <tbody>
              {Object.entries(bt.metrics).map(([k, v]: any) => (
                <tr key={k}><td className="capitalize">{k.replace("_", " ")}</td><td className="r num">{num(v.sharpe)}</td><td className="r num">{fpct(v.total_return)}</td><td className="r num">{fpct(v.max_drawdown, 1)}</td><td className="r num">{fpct(v.ann_vol, 1)}</td><td className="r num">{rate(v.exposure, 0)}</td></tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card title="Predictions on the test window">
          <LineChart x={r.test.series.dates} series={[{ name: cls ? "P(up)" : "Predicted return", values: r.test.series.score, width: 1.4 }]} height={130} yFormat={(v) => (cls ? v.toFixed(2) : (v * 100).toFixed(1) + "%")} xFormat={(d) => String(d).slice(0, 7)} refLine={cls ? { value: 0.5 } : { value: 0 }} legend={false} />
          <LineChart x={r.test.series.dates} series={[{ name: "Close", values: r.test.series.close, tone: TONES[1] }]} height={90} yFormat={(v) => v.toFixed(0)} xFormat={(d) => String(d).slice(0, 7)} legend={false} />
        </Card>
        <Card title="Interpretability: saliency (gradient x input)" right={<span className="faint text-[11px]">rows = features, columns = bars back in the window</span>}>
          <Heatmap matrix={r.features.map((_: string, fi: number) => r.interpretability.saliency.map((row: number[]) => row[fi]))} rowLabels={r.features} colLabels={r.interpretability.saliency.map((_: any, i: number) => String(r.window - i))} min={0} max={1} showValues={false} cell={10} />
        </Card>
        <Card title="Feature importance" bodyClass="p-0">
          <table className="tbl">
            <thead><tr><th>Feature</th><th className="r" title="Increase in test loss when the feature is shuffled">Permutation</th><th className="r">Saliency share</th></tr></thead>
            <tbody>
              {r.interpretability.feature_importance.map((x: any) => (
                <tr key={x.feature}><td>{x.feature}</td><td className="r num">{x.permutation.toFixed(5)}</td><td className="r"><div className="ml-auto flex w-28 items-center gap-1.5"><div className="h-1.5 flex-1 rounded-full bg-bg-3"><div className="h-1.5 rounded-full bg-fg" style={{ width: `${x.saliency * 100 * 3}%`, maxWidth: "100%" }} /></div><span className="num w-9 text-right">{rate(x.saliency, 0)}</span></div></td></tr>
              ))}
            </tbody>
          </table>
        </Card>
        {r.interpretability.attention?.length > 0 && (
          <Card title="Self-attention maps" className="xl:col-span-2" right={<span className="faint text-[11px]">query time step (rows) attending to key time step (columns), averaged over heads and test samples</span>}>
            <div className="grid gap-3 md:grid-cols-2">
              {r.interpretability.attention.map((a: number[][], i: number) => (
                <div key={i}><div className="eyebrow mb-1">Layer {i + 1}</div><Heatmap matrix={a} showValues={false} cell={6} /></div>
              ))}
            </div>
          </Card>
        )}
        <Card title="Architecture" bodyClass="p-0">
          <table className="tbl">
            <thead><tr><th>Layer</th><th>Output</th><th className="r">Params</th></tr></thead>
            <tbody>
              {r.model.summary.layers.map((l: any, i: number) => (
                <tr key={i}><td className="mono max-w-[420px] truncate" title={l.layer}>{l.layer}</td><td className="mono">[{l.output.join(", ")}]</td><td className="r num">{l.params.toLocaleString()}</td></tr>
              ))}
              <tr><td className="font-semibold">Total</td><td /><td className="r num font-semibold">{r.model.summary.total_params.toLocaleString()}</td></tr>
            </tbody>
          </table>
        </Card>
        <Card title="Data and splits">
          <div className="space-y-2 text-[12px]">
            <div className="flex h-5 overflow-hidden rounded-md text-[10.5px] font-medium">
              {(["train", "val", "test"] as const).map((s, i) => (
                <div key={s} className="flex items-center justify-center" style={{ width: `${(r.data.splits[s].n / r.data.samples) * 100}%`, background: i === 0 ? "var(--fg)" : i === 1 ? "var(--fg-3)" : "var(--bg-3)", color: i < 2 ? "var(--bg)" : "var(--fg)" }}>{s}</div>
              ))}
            </div>
            <dl className="kv">
              {(["train", "val", "test"] as const).map((s) => (<Fragment key={s}><dt className="capitalize">{s}</dt><dd>{r.data.splits[s].start} to {r.data.splits[s].end} · n={r.data.splits[s].n}{cls ? ` · up ${rate(r.data.splits[s].up_rate)}` : ""}</dd></Fragment>))}
              <dt>Embargo</dt><dd>{r.data.embargo} samples between splits</dd>
              <dt>Bars</dt><dd>{r.interval} · {r.data.first_date} to {r.data.last_date}</dd>
              <dt>Receptive field</dt><dd>{r.model.receptive_field} bars</dd>
            </dl>
            <p className="faint text-[11px]">Scalers are fitted on training rows only; the embargo drops samples whose {r.horizon}-bar labels would overlap the next split.</p>
          </div>
        </Card>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------------------------------- */
function TrainTab({ opts, initialSymbol }: { opts: any; initialSymbol?: string }) {
  const [cfg, setCfg] = useStored<Config>("te.lab.config", DEFAULT_CONFIG);
  const [exps, setExps] = useStored<Experiment[]>(KEYS.experiments, []);
  const [current, setCurrent] = useState<Experiment | null>(null);
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const ctrl = useRef<AbortController | null>(null);
  useEffect(() => {
    if (initialSymbol) setCfg((c) => ({ ...c, symbol: initialSymbol }));
  }, [initialSymbol]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!current && exps[0]) setCurrent(exps[0]);
  }, [exps, current]);
  useEffect(() => {
    if (!running) return;
    const t0 = Date.now();
    const id = setInterval(() => setElapsed((Date.now() - t0) / 1000), 100);
    return () => clearInterval(id);
  }, [running]);
  const run = async () => {
    setRunning(true);
    setError(null);
    ctrl.current = new AbortController();
    try {
      const result = await api("/api/lab/train", { body: payload(cfg), signal: ctrl.current.signal });
      const e: Experiment = { id: Math.random().toString(36).slice(2, 10), at: Date.now(), config: cfg, result };
      setCurrent(e);
      setExps((prev) => [e, ...prev].slice(0, 12));
    } catch (e: any) {
      if (e?.name !== "AbortError") setError(e?.message || "Training failed");
    } finally {
      setRunning(false);
    }
  };
  return (
    <div className="grid grid-cols-1 gap-3 xl:grid-cols-[340px_1fr]">
      <div className="space-y-3">
        <Card title="Experiment" right={<button className="btn btn-sm btn-ghost" onClick={() => setCfg(DEFAULT_CONFIG)} title="Reset"><RotateCcw size={12} /></button>}>
          <ConfigPanel cfg={cfg} setCfg={setCfg} opts={opts} />
          <div className="mt-3 flex gap-2">
            {running ? (
              <button className="btn flex-1" onClick={() => ctrl.current?.abort()}><Square size={12} />Stop waiting ({elapsed.toFixed(1)}s)</button>
            ) : (
              <button className="btn btn-primary flex-1" onClick={run} disabled={!opts}><Play size={13} />Train {opts?.architectures?.[cfg.arch]?.name ?? ""}</button>
            )}
          </div>
          <p className="faint mt-1.5 text-[10.5px]">Trains on the server with the from-scratch NumPy engine. Results stay in this browser.</p>
        </Card>
        <Card title="History" bodyClass="p-0" right={exps.length > 0 && <button className="btn btn-sm btn-ghost" onClick={() => downloadFile("experiments.csv", toCSV(exps.map((e) => ({ when: new Date(e.at).toISOString(), symbol: e.result.symbol, interval: e.result.interval, arch: e.result.model.name, params: e.result.model.summary.total_params, window: e.result.window, horizon: e.result.horizon, accuracy: e.result.test.metrics.accuracy ?? e.result.test.metrics.directional_accuracy, auc: e.result.test.metrics.auc, sharpe: e.result.backtest.metrics.model.sharpe, buy_hold_sharpe: e.result.backtest.metrics.buy_hold.sharpe }))), "text/csv")}><Download size={12} /></button>}>
          {!exps.length ? <Empty title="No runs yet" /> : (
            <table className="tbl">
              <tbody>
                {exps.map((e) => (
                  <tr key={e.id} className={`cursor-pointer ${current?.id === e.id ? "bg-bg-2" : ""}`} onClick={() => setCurrent(e)}>
                    <td><div className="font-medium">{e.result.model.name} · {e.result.symbol}</div><div className="faint text-[10.5px]">{e.result.interval} · w{e.result.window} h{e.result.horizon} · {new Date(e.at).toLocaleTimeString()}</div></td>
                    <td className="r num">{rate(e.result.test.metrics.accuracy ?? e.result.test.metrics.directional_accuracy)}</td>
                    <td className="w-6"><button className="btn-ghost rounded p-1" onClick={(ev) => { ev.stopPropagation(); setExps(exps.filter((x) => x.id !== e.id)); if (current?.id === e.id) setCurrent(null); }}><Trash2 size={11} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
      <div className="min-w-0">
        <ErrorBox error={error} />
        {running && !current && <Skeleton h={500} />}
        {!running && !current && !error && <Card><Empty title="Train your first network">Pick a symbol, a bar size and an architecture, then press Train. You will see learning curves, out-of-sample metrics against baselines, a backtest, saliency maps and an MC-dropout forecast.</Empty></Card>}
        {current && (
          <div className={running ? "opacity-60" : ""}>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div className="text-[13px]"><b>{current.result.model.name}</b> on <Link href={`/symbol/${current.result.symbol}`} className="font-semibold underline">{current.result.symbol}</Link> <span className="faint">· {current.result.interval} bars · window {current.result.window} · horizon {current.result.horizon} · {current.result.task}</span></div>
              <div className="flex gap-1.5">
                <button className="btn btn-sm" onClick={() => setCfg(current.config)}>Load config</button>
                <button className="btn btn-sm" onClick={() => downloadFile(`experiment-${current.result.symbol}-${current.result.model.arch}.json`, JSON.stringify(current, null, 1))}><Download size={12} />JSON</button>
                <Link href={`/learn?concept=${current.result.model.arch === "cnn" ? "tcn" : current.result.model.arch === "transformer" ? "attention" : current.result.model.arch === "mlp" || current.result.model.arch === "linear" ? "neural_network" : current.result.model.arch}&experiment=${current.id}`} className="btn btn-sm">Explain this run</Link>
              </div>
            </div>
            <Results r={current.result} />
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------------------------------- */
function ArenaTab({ opts, initialSymbol }: { opts: any; initialSymbol?: string }) {
  const [cfg, setCfg] = useStored<Config>("te.arena.config", { ...DEFAULT_CONFIG, train: { ...DEFAULT_CONFIG.train, epochs: 40, time_budget_s: 12 } });
  const [archs, setArchs] = useState<string[]>(["linear", "mlp", "lstm", "gru", "cnn", "transformer"]);
  const [state, setState] = useState<Record<string, { status: string; result?: any; error?: string }>>({});
  const [rules, setRules] = useState<any>(null);
  const [running, setRunning] = useState(false);
  useEffect(() => {
    if (initialSymbol) setCfg((c) => ({ ...c, symbol: initialSymbol }));
  }, [initialSymbol]); // eslint-disable-line react-hooks/exhaustive-deps
  const run = async () => {
    setRunning(true);
    setRules(null);
    setState(Object.fromEntries(archs.map((a) => [a, { status: "queued" }])));
    const queue = [...archs];
    let first: any = null;
    const worker = async () => {
      while (queue.length) {
        const a = queue.shift()!;
        setState((s) => ({ ...s, [a]: { status: "training" } }));
        try {
          const result = await api("/api/lab/train", { body: { ...payload(cfg), arch: a, arch_params: {}, baseline: false } });
          first = first ?? result;
          setState((s) => ({ ...s, [a]: { status: "done", result } }));
        } catch (e: any) {
          setState((s) => ({ ...s, [a]: { status: "error", error: e?.message } }));
        }
      }
    };
    await Promise.all([worker(), worker(), worker()]);
    if (first) {
      const strategyPeriod = cfg.interval === "1h" ? "2y" : cfg.interval === "1wk" ? "max" : "max";
      try {
        const rr = await api("/api/strategies/compare", { body: { symbol: cfg.symbol, interval: cfg.interval, period: strategyPeriod, start: first.data.splits.test.start, end: first.data.splits.test.end, cost_bps: cfg.cost_bps } });
        setRules(rr);
      } catch {
        /* rules are optional context */
      }
    }
    setRunning(false);
  };
  const board = useMemo(() => {
    const rows: any[] = [];
    for (const a of archs) {
      const r = state[a]?.result;
      if (!r) continue;
      const m = r.test.metrics;
      rows.push({ kind: "Neural", name: r.model.name, params: r.model.summary.total_params, acc: m.accuracy ?? m.directional_accuracy, auc: m.auc, ...r.backtest.metrics.model, equity: r.backtest.equity.model, dates: r.backtest.dates });
    }
    if (rules) {
      for (const s of rules.strategies) rows.push({ kind: "Rule", name: s.name, ...s.metrics, trades: s.trades, equity: s.curve.equity, dates: s.curve.dates });
      rows.push({ kind: "Benchmark", name: "Buy and hold", ...rules.buy_hold.metrics, equity: rules.buy_hold.curve.equity, dates: rules.buy_hold.curve.dates });
    }
    return rows.sort((a, b) => (b.sharpe ?? -9) - (a.sharpe ?? -9));
  }, [state, rules, archs]);
  const first = Object.values(state).find((s) => s.result)?.result;
  return (
    <div className="grid grid-cols-1 gap-3 xl:grid-cols-[340px_1fr]">
      <Card title="Arena setup">
        <ConfigPanel cfg={cfg} setCfg={setCfg} opts={opts} compact />
        <div className="mt-3">
          <span className="label">Architectures</span>
          <div className="flex flex-wrap gap-1">
            {Object.entries(opts?.architectures ?? {}).map(([k, a]: any) => (
              <button key={k} className="chip" data-on={archs.includes(k)} onClick={() => setArchs(archs.includes(k) ? archs.filter((x) => x !== k) : [...archs, k])}>{a.name}</button>
            ))}
          </div>
        </div>
        <button className="btn btn-primary mt-3 w-full" onClick={run} disabled={running || !archs.length}>{running ? <Spinner /> : <Play size={13} />}Run arena</button>
        <p className="faint mt-1.5 text-[10.5px]">Every network trains on the same data and split; the five rule strategies and buy-and-hold are evaluated on the identical test window.</p>
      </Card>
      <div className="min-w-0 space-y-3">
        {Object.keys(state).length === 0 && <Card><Empty title="Networks versus rules">Run the arena to train several architectures side by side and rank them against classic rule strategies on the same out-of-sample period.</Empty></Card>}
        {Object.keys(state).length > 0 && (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {archs.map((a) => {
              const s = state[a];
              return (
                <div key={a} className="card px-2.5 py-2">
                  <div className="flex items-center justify-between text-[12px] font-semibold">{opts?.architectures?.[a]?.name}{s?.status === "training" && <Spinner size={12} />}</div>
                  <div className="faint text-[11px]">{s?.status === "done" ? `${rate(s.result.test.metrics.accuracy ?? s.result.test.metrics.directional_accuracy)} · ${s.result.training.seconds}s` : s?.status === "error" ? s.error : s?.status}</div>
                </div>
              );
            })}
          </div>
        )}
        {board.length > 0 && (
          <>
            <Card title="Leaderboard" right={first && <span className="faint text-[11px]">test window {first.data.splits.test.start} to {first.data.splits.test.end} · ranked by Sharpe</span>} bodyClass="p-0">
              <table className="tbl">
                <thead><tr><th>#</th><th>Model</th><th>Type</th><th className="r">Params</th><th className="r">Accuracy</th><th className="r">AUC</th><th className="r">Sharpe</th><th className="r">Return</th><th className="r">Max DD</th><th className="r">Exposure</th></tr></thead>
                <tbody>
                  {board.map((r, i) => (
                    <tr key={r.name}>
                      <td className="num">{i + 1}</td><td className="font-medium">{r.name}</td><td className="faint">{r.kind}</td><td className="r num">{r.params?.toLocaleString() ?? ""}</td>
                      <td className="r num">{r.acc != null ? rate(r.acc) : ""}</td><td className="r num">{r.auc != null ? num(r.auc, 3) : ""}</td>
                      <td className="r num font-semibold">{num(r.sharpe)}</td><td className="r num">{fpct(r.total_return)}</td><td className="r num">{fpct(r.max_drawdown, 1)}</td><td className="r num">{rate(r.exposure, 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
            <Card title="Equity on the test window">
              <LineChart
                x={board.find((r) => r.kind === "Neural")?.dates ?? board[0].dates}
                series={board.filter((r) => r.kind !== "Rule").slice(0, 6).map((r, i) => ({ name: r.name, values: r.equity, dash: r.kind === "Benchmark" ? "2 2" : undefined, width: i === 0 ? 2 : 1.4 }))}
                height={240}
                yFormat={(v) => v.toFixed(2)}
                xFormat={(d) => String(d).slice(0, 7)}
              />
            </Card>
          </>
        )}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------------------------------- */
function ModelTab() {
  const { data: c, error, reload } = useApi<any>("/api/models/card", { staleMs: 3_600_000 });
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!c) return <Skeleton h={500} />;
  const e = c.ensemble;
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 rounded-[10px] border border-line bg-panel p-3 sm:grid-cols-3 xl:grid-cols-6">
        <Stat label="Target" value={`${c.horizon}-day direction`} sub={`${c.window}-day window · ${c.features.length} features`} />
        <Stat label="Test accuracy" value={rate(e.test.accuracy)} sub={`base rate ${rate(e.test_up_rate)}`} strong />
        <Stat label="Test ROC AUC" value={num(e.test.auc, 3)} sub="0.5 = no skill" />
        <Stat label="Log loss" value={num(e.test.log_loss, 4)} sub={`base rate ${num(e.baseline_train_base_rate.log_loss, 4)}`} />
        <Stat label="Calibration ECE" value={num(c.calibration.ece, 3)} sub="lower is better" />
        <Stat label="Training samples" value={c.splits.train.n.toLocaleString()} sub={`${c.universe.length} symbols`} />
      </div>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <Card title="What followed each confidence decile (held-out test period)">
          <Bars labels={c.deciles.map((d: any) => `D${d.decile}`)} values={c.deciles.map((d: any) => d.up_frequency)} refLine={c.test_base_rate} format={(v) => (v * 100).toFixed(0)} height={170} yDomain={[0.45, Math.max(...c.deciles.map((d: any) => d.up_frequency)) + 0.03]} />
          <p className="faint text-[11px]">Share of 5-day windows that rose, by decile of ensemble P(up). Dashed line: base rate. {c.signal_rule}.</p>
          <table className="tbl mt-2">
            <thead><tr><th>Decile</th><th className="r">P(up) range</th><th className="r">n</th><th className="r">Up frequency</th><th className="r">Avg 5-day return</th></tr></thead>
            <tbody>{c.deciles.map((d: any) => <tr key={d.decile}><td>D{d.decile}</td><td className="r num">{d.lo.toFixed(3)} to {d.hi.toFixed(3)}</td><td className="r num">{d.n}</td><td className="r num">{rate(d.up_frequency)}</td><td className="r num">{fpct(d.mean_fwd_return)}</td></tr>)}</tbody>
          </table>
        </Card>
        <Card title="Portfolio backtest on the test period" right={<span className="faint text-[11px]">{c.backtest.rule}</span>}>
          <LineChart x={c.backtest.dates} series={[{ name: "Ensemble-timed", values: c.backtest.equity.model, width: 2 }, { name: "Equal-weight buy and hold", values: c.backtest.equity.buy_hold, dash: "4 3" }]} height={200} yFormat={(v) => v.toFixed(2)} xFormat={(d) => String(d).slice(0, 7)} />
          <table className="tbl mt-2">
            <thead><tr><th /><th className="r">Sharpe</th><th className="r">Return</th><th className="r">CAGR</th><th className="r">Vol</th><th className="r">Max DD</th></tr></thead>
            <tbody>{Object.entries(c.backtest.metrics).map(([k, v]: any) => <tr key={k}><td className="capitalize">{k.replace("_", " ")}</td><td className="r num">{num(v.sharpe)}</td><td className="r num">{fpct(v.total_return)}</td><td className="r num">{fpct(v.cagr)}</td><td className="r num">{fpct(v.ann_vol, 1)}</td><td className="r num">{fpct(v.max_drawdown, 1)}</td></tr>)}</tbody>
          </table>
        </Card>
        <Card title="Ensemble members" bodyClass="p-0" className="xl:col-span-2">
          <table className="tbl">
            <thead><tr><th>Member</th><th>Configuration</th><th className="r">Params</th><th className="r">Epochs</th><th className="r">Best val loss</th><th className="r">Test acc</th><th className="r">Test AUC</th><th className="r">Test log loss</th><th className="r" title="Max |P_numpy - P_torch| on test windows">NumPy vs PyTorch</th></tr></thead>
            <tbody>
              {c.members.map((m: any) => (
                <tr key={m.id}><td className="font-medium">{m.name}</td><td className="mono faint">{Object.entries(m.params).map(([k, v]) => `${k}=${v}`).join(" ")}</td><td className="r num">{m.n_params.toLocaleString()}</td><td className="r num">{m.epochs}</td><td className="r num">{m.best_val_loss.toFixed(4)}</td><td className="r num">{rate(m.test.accuracy)}</td><td className="r num">{num(m.test.auc, 3)}</td><td className="r num">{num(m.test.log_loss, 4)}</td><td className="r num">{m.parity_max_abs_diff.toExponential(1)}</td></tr>
              ))}
              <tr><td className="font-semibold">Ensemble</td><td className="faint">{e.method}</td><td /><td /><td /><td className="r num font-semibold">{rate(e.test.accuracy)}</td><td className="r num font-semibold">{num(e.test.auc, 3)}</td><td className="r num font-semibold">{num(e.test.log_loss, 4)}</td><td /></tr>
            </tbody>
          </table>
        </Card>
        <Card title="Training curves (PyTorch, offline)">
          <LineChart x={Array.from({ length: Math.max(...c.members.map((m: any) => m.history.length)) }, (_, i) => i + 1)} series={c.members.map((m: any, i: number) => ({ name: m.name, values: m.history.map((h: any) => h.val_loss), tone: TONES[i % 3], dash: i >= 2 ? "4 3" : "" }))} height={170} yFormat={(v) => v.toFixed(4)} />
          <p className="faint text-[11px]">Validation loss per epoch; early stopping keeps the best epoch. Validation covers 2022 to 2023, a regime shift from the training period.</p>
        </Card>
        <Card title="Data, splits and method">
          <dl className="kv text-[12px]">
            <dt>Version</dt><dd>{c.version} · trained {c.trained_at.slice(0, 10)}</dd>
            <dt>Target</dt><dd>{c.target}</dd>
            {(["train", "val", "test"] as const).map((s) => (<Fragment key={s}><dt className="capitalize">{s}</dt><dd>{c.splits[s].start} to {c.splits[s].end} · {c.splits[s].n.toLocaleString()}</dd></Fragment>))}
            <dt>Training</dt><dd>{c.training.framework} · {c.training.optimizer}</dd>
            <dt>Serving</dt><dd>From-scratch NumPy engine (no PyTorch at runtime)</dd>
          </dl>
          <div className="mt-2 flex flex-wrap gap-1">{c.features.map((f: string) => <span key={f} className="chip">{f}</span>)}</div>
          <div className="faint mt-2 text-[11px]">Universe: {c.universe.join(", ")}</div>
        </Card>
      </div>
      <Disclaimer>The ensemble's edge over the base rate is small and was measured on one historical period. Probabilities are tilts, not certainties.</Disclaimer>
    </div>
  );
}

/* ---------------------------------------------------------------------------------------------- */
function LabInner() {
  const sp = useSearchParams();
  const router = useRouter();
  const tab = (sp.get("tab") as "train" | "arena" | "model") || "train";
  const symbol = sp.get("symbol")?.toUpperCase() || undefined;
  const { data: opts, error } = useApi<any>("/api/lab/options", { staleMs: 3_600_000 });
  return (
    <div>
      <PageHeader
        title="Lab"
        subtitle="Neural networks written from scratch in NumPy, trained live on market data, then evaluated out of sample against baselines."
        right={<Seg value={tab} onChange={(t) => router.replace(`/lab?tab=${t}${symbol ? `&symbol=${symbol}` : ""}`)} options={[{ value: "train", label: "Train" }, { value: "arena", label: "Arena" }, { value: "model", label: "Model card" }]} />}
      />
      <ErrorBox error={error} />
      {tab === "train" && <TrainTab opts={opts} initialSymbol={symbol} />}
      {tab === "arena" && <ArenaTab opts={opts} initialSymbol={symbol} />}
      {tab === "model" && <ModelTab />}
      {tab !== "model" && <Disclaimer />}
    </div>
  );
}

export default function LabPage() {
  return (
    <Suspense fallback={<Skeleton h={400} />}>
      <LabInner />
    </Suspense>
  );
}
