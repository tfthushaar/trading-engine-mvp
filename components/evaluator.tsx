"use client";
import type { ReactNode } from "react";
import { Empty, ErrorBox, Field, Meter, SourceTag, Spinner } from "@/components/ui";
import { rate } from "@/lib/format";

export function EvaluatorView({ form, setForm, ev, onRun, symbolField }: { form: any; setForm: (f: any) => void; ev: any; onRun: () => void; symbolField?: ReactNode }) {
  const r = ev.data;
  return (
    <div className="grid gap-3 lg:grid-cols-[260px_1fr]">
      <form className="space-y-2" onSubmit={(e) => (e.preventDefault(), onRun())}>
        {symbolField}
        {(["entry", "stop", "target"] as const).map((k) => (
          <Field key={k} label={k === "stop" ? "Stop loss" : k === "entry" ? "Entry" : "Target"}><input className="input num" inputMode="decimal" value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} /></Field>
        ))}
        <button className="btn btn-primary w-full" disabled={ev.running}>{ev.running ? <Spinner /> : null}Evaluate setup</button>
        <p className="faint text-[10.5px]">Direction is inferred from the target. Scores risk/reward, trend, momentum, stop placement versus ATR, target realism, entry proximity and agreement with the neural ensemble.</p>
      </form>
      <div className="min-w-0">
        <ErrorBox error={ev.error} />
        {!r && !ev.error && <Empty title="Plan a trade">Enter an entry, stop and target to grade the setup from 0 to 100.</Empty>}
        {r && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-4">
              <div className="grid h-14 w-14 place-items-center rounded-xl bg-inv text-[26px] font-bold text-inv-fg">{r.grade}</div>
              <div><div className="eyebrow">Score</div><div className="num text-[20px] font-semibold">{r.score}/100</div></div>
              <div><div className="eyebrow">Direction</div><div className="font-semibold capitalize">{r.direction}</div></div>
              <div><div className="eyebrow">Reward : risk</div><div className="num font-semibold">{r.risk_reward.ratio.toFixed(2)} : 1</div></div>
              <div><div className="eyebrow">Break-even win rate</div><div className="num font-semibold">{rate(r.risk_reward.breakeven_win_rate)}</div></div>
              <div><div className="eyebrow">Stop distance</div><div className="num font-semibold">{r.context.stop_atr} ATR</div></div>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-1">
                {r.components.map((c: any) => (
                  <div key={c.name} className="flex items-center gap-2 text-[12px]"><span className="w-28 truncate capitalize">{c.name}</span><Meter value={c.score} max={100} /><span className="num w-8 text-right">{Math.round(c.score)}</span><span className="faint num w-8 text-right">{Math.round(c.weight * 100)}%</span></div>
                ))}
              </div>
              <div className="space-y-1.5 text-[12px]">
                {r.signals.map((s: string, i: number) => <div key={`s${i}`} className="flex gap-1.5"><span className="font-bold">+</span>{s}</div>)}
                {r.warnings.map((s: string, i: number) => <div key={`w${i}`} className="muted flex gap-1.5"><span className="font-bold">!</span>{s}</div>)}
              </div>
            </div>
            {r.assessment && <div className="rounded-lg bg-bg-2 px-2.5 py-2 text-[12.5px]"><div className="mb-1 flex justify-between"><span className="eyebrow">Coach</span><SourceTag source={r.assessment.source} note={r.assessment.note} /></div>{r.assessment.text}</div>}
          </div>
        )}
      </div>
    </div>
  );
}

