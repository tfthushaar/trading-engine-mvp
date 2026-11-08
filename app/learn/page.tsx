"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Check } from "lucide-react";
import { Card, ErrorBox, Markdown, PageHeader, Seg, Skeleton, SourceTag, Spinner } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { getStored, KEYS, useStored } from "@/lib/store";

interface LearnState { level: string; viewed: Record<string, number> }

function Methodology() {
  return (
    <Card title="How Trading Engine works">
      <div className="prose-te grid max-w-none gap-x-8 lg:grid-cols-2">
        <div>
          <h2>1. Data</h2>
          <p>Daily (or hourly and weekly) OHLCV bars from Yahoo Finance, adjusted for splits and dividends. Each bar is turned into scale-free features: 1, 5 and 20-bar log returns, intraday range and body, a volume z-score, RSI, MACD histogram, distance from the 20 and 50-bar averages, realised volatility, ATR, Bollinger position, and optional market context (S&amp;P 500 return, VIX level).</p>
          <h2>2. Avoiding look-ahead bias</h2>
          <ul>
            <li>Features at bar t use only information available at the close of t.</li>
            <li>Splits are chronological (train, then validation, then test), never shuffled.</li>
            <li>Standardisation statistics are fitted on training rows only.</li>
            <li>An embargo removes samples whose forward-looking labels would overlap the next split.</li>
          </ul>
          <h2>3. Networks, written from scratch</h2>
          <p>Every layer is implemented in NumPy with a hand-written backward pass: dense layers, ReLU, GELU, dropout, layer normalisation, LSTM and GRU cells with backpropagation through time, causal dilated 1-D convolutions, sinusoidal positional encoding and multi-head self-attention. Optimisers are SGD with momentum, Adam and AdamW, with gradient clipping and a cosine schedule.</p>
          <p>Correctness is verified two ways: every layer and every full architecture passes numerical gradient checks, and the same architectures re-implemented in PyTorch produce identical outputs and gradients (to 1e-10) when given the same weights.</p>
          <h2>4. Architectures</h2>
          <ul>
            <li><b>Linear</b>: a single affine layer on the flattened window. The baseline every network must beat.</li>
            <li><b>MLP</b>: stacked dense layers. Strong but blind to time order.</li>
            <li><b>LSTM and GRU</b>: gated recurrent cells that carry memory across the window.</li>
            <li><b>TCN</b>: causal convolutions with dilations 1, 2, 4, 8 and residual connections.</li>
            <li><b>Transformer</b>: pre-norm encoder blocks with multi-head self-attention.</li>
          </ul>
        </div>
        <div>
          <h2>5. The pretrained ensemble</h2>
          <p>An LSTM, GRU, TCN and Transformer are trained offline in PyTorch on a panel of 48 liquid US stocks and ETFs (2012 to 2021), validated on 2022 to 2023, and tested on 2024 onwards. The weights are exported to the NumPy engine, which serves every signal on the site. The ensemble averages the four probabilities.</p>
          <h2>6. Reading a signal honestly</h2>
          <p>Daily equity direction is close to a coin flip with an upward drift. The test period rose 55% of the time, so a probability of 0.58 is a mild tilt, not a prediction. Signals are therefore labelled by confidence decile on held-out data: the top decile was followed by a rise 61% of the time, the bottom decile 53%. Uncertainty comes from Monte Carlo dropout and from disagreement between members.</p>
          <h2>7. Evaluation</h2>
          <p>Classification is scored with accuracy, balanced accuracy, ROC AUC, log loss, Brier score and calibration. Regression uses RMSE, directional accuracy and information coefficients. Every result is shown next to baselines (majority class, the training base rate, a linear model) and an out-of-sample backtest against buy-and-hold with transaction costs. Sharpe ratios are annualised from per-bar returns at the correct frequency.</p>
          <h2>8. Interpretability</h2>
          <p>Gradient-times-input saliency shows which features and which bars in the window moved the output; permutation importance shows how much the loss worsens when a feature is scrambled; attention maps show where a Transformer looks. Each symbol page shows the attribution for today's forecast.</p>
          <h2>9. Language models</h2>
          <p>Briefings, explanations and the analyst use a language model (Groq by default, or your own Groq, Gemini or Anthropic key) strictly to narrate the data and model output passed to it. They are instructed not to invent events. Without a key the product falls back to data-driven text.</p>
          <h2>10. Limitations</h2>
          <p>Results depend on one historical period, free data can be delayed or revised, and backtests ignore taxes, borrow costs and market impact. Nothing here is financial advice.</p>
        </div>
      </div>
    </Card>
  );
}

function LearnInner() {
  const sp = useSearchParams();
  const { data: cat, error } = useApi<any>("/api/learn/concepts", { staleMs: 86_400_000 });
  const [st, setSt] = useStored<LearnState>(KEYS.learn, { level: "intermediate", viewed: {} });
  const [tab, setTab] = useState<"concepts" | "method">("concepts");
  const [selected, setSelected] = useState<string | null>(sp.get("concept"));
  const [symbol, setSymbol] = useState("");
  const [q, setQ] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const expId = sp.get("experiment");
  const experiment = useMemo(() => {
    if (!expId) return null;
    const e = getStored<any[]>(KEYS.experiments, []).find((x) => x.id === expId);
    if (!e) return null;
    const r = e.result;
    return { arch: r.model.name, symbol: r.symbol, interval: r.interval, window: r.window, horizon: r.horizon, test_metrics: r.test.metrics, baselines: r.test.baselines, best_epoch: r.training.best_epoch, epochs_run: r.training.epochs_run, stopped: r.training.stopped };
  }, [expId]);
  const concepts: any[] = cat?.concepts ?? [];
  const groups = useMemo(() => {
    const g: Record<string, any[]> = {};
    for (const c of concepts) if (!q || c.title.toLowerCase().includes(q.toLowerCase())) (g[c.category] ??= []).push(c);
    return g;
  }, [concepts, q]);
  const next = concepts.find((c) => !st.viewed[c.id]);
  const latest = useRef(0);
  const explain = async (id: string, sym?: string, level = st.level) => {
    const ticket = ++latest.current; // a slower earlier answer must not replace a newer one
    setSelected(id);
    setLoading(true);
    setErr(null);
    setSt({ ...st, viewed: { ...st.viewed, [id]: Date.now() } });
    try {
      setResult(await api("/api/learn/explain", { body: { concept: id, level, symbol: sym || null, experiment: experiment && sp.get("concept") === id ? experiment : null } }).then((r) => (ticket === latest.current ? r : result)));
    } catch (e: any) {
      if (ticket === latest.current) setErr(e.message);
    } finally {
      if (ticket === latest.current) setLoading(false);
    }
  };
  useEffect(() => {
    if (selected && concepts.length && !result) explain(selected); // eslint-disable-line react-hooks/exhaustive-deps
  }, [concepts.length]);
  const meta = concepts.find((c) => c.id === selected);
  const progress = concepts.length ? Object.keys(st.viewed).filter((k) => concepts.some((c) => c.id === k)).length / concepts.length : 0;
  return (
    <div>
      <PageHeader
        title="Learn"
        subtitle="The deep-learning methods behind the product and the market concepts it uses, explained at your level."
        right={<><Seg value={tab} onChange={setTab} options={[{ value: "concepts", label: "Concepts" }, { value: "method", label: "How it works" }]} /><Seg value={st.level} onChange={(v) => { setSt({ ...st, level: v }); if (selected) explain(selected, symbol, v); }} options={["beginner", "intermediate", "advanced"].map((l) => ({ value: l, label: l[0].toUpperCase() + l.slice(1) }))} /></>}
      />
      <ErrorBox error={error} />
      {tab === "method" ? <Methodology /> : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[300px_1fr]">
          <Card title="Library" right={<span className="faint num text-[11px]">{Math.round(progress * 100)}% explored</span>} bodyClass="p-0">
            <div className="border-b border-line p-2"><input className="input" placeholder="Search concepts" value={q} onChange={(e) => setQ(e.target.value)} /></div>
            {next && <button className="flex w-full items-center justify-between border-b border-line bg-bg-2 px-3 py-2 text-left" onClick={() => explain(next.id)}><span><span className="eyebrow block">Suggested next</span><span className="font-medium">{next.title}</span></span></button>}
            <div className="max-h-[calc(100vh-300px)] overflow-y-auto">
              {!cat && <div className="p-3"><Skeleton h={300} /></div>}
              {Object.entries(groups).map(([g, items]) => (
                <div key={g}>
                  <div className="eyebrow px-3 pb-1 pt-2">{g}</div>
                  {items.map((c) => (
                    <button key={c.id} onClick={() => explain(c.id)} className={`flex w-full items-center justify-between px-3 py-1.5 text-left text-[12.5px] ${selected === c.id ? "bg-bg-2 font-semibold" : "hover:bg-bg-2"}`}>
                      {c.title}
                      {st.viewed[c.id] && <Check size={12} className="faint" />}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </Card>
          <Card
            title={meta ? <>{meta.title}<span className="faint font-normal">{meta.category}</span></> : "Pick a concept"}
            right={selected && (
              <form className="flex gap-1" onSubmit={(e) => (e.preventDefault(), explain(selected, symbol))}>
                <input className="input h-6 w-36 text-[12px]" placeholder="Live example: AAPL" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
                <button className="btn btn-sm">Explain</button>
              </form>
            )}
          >
            {!selected && <p className="muted text-[12.5px]">Choose a concept from the library. Add a symbol to ground the explanation in its current readings, or open a Lab run with "Explain this run".</p>}
            {meta && <p className="mb-2 rounded-lg bg-bg-2 px-2.5 py-2 text-[12.5px] leading-relaxed">{meta.summary}</p>}
            {experiment && sp.get("concept") === selected && <p className="faint mb-2 text-[11px]">Using your {experiment.arch} run on {experiment.symbol} as context.</p>}
            <ErrorBox error={err} />
            {loading && <div className="faint flex items-center gap-2 text-[12px]"><Spinner size={12} />Writing a {st.level} explanation</div>}
            {result && !loading && result.id === selected && (
              <>
                <div className="mb-1 flex justify-end"><SourceTag source={result.source === "ai" ? "ai" : "data"} note={result.note} /></div>
                <Markdown text={result.markdown} />
              </>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}

export default function LearnPage() {
  return (
    <Suspense fallback={null}>
      <LearnInner />
    </Suspense>
  );
}
