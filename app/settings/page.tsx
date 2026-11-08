"use client";
import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Card, Field, PageHeader, Seg, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { downloadFile } from "@/lib/format";
import { DEFAULT_LLM, KEYS, useStored, type LLMSettings, type Theme } from "@/lib/store";

const PROVIDERS = {
  groq: { label: "Groq", hint: "Fast open models such as openai/gpt-oss-120b", url: "https://console.groq.com/keys", model: "openai/gpt-oss-120b" },
  gemini: { label: "Google Gemini", hint: "Gemini via Google's OpenAI-compatible API", url: "https://aistudio.google.com/apikey", model: "gemini-flash-latest" },
  anthropic: { label: "Anthropic Claude", hint: "Claude via the official Anthropic SDK", url: "https://console.anthropic.com/settings/keys", model: "claude-opus-5-5" },
} as const;

export default function SettingsPage() {
  const [llm, setLlm] = useStored<LLMSettings>(KEYS.llm, DEFAULT_LLM);
  const [theme, setTheme] = useStored<Theme>(KEYS.theme, "system");
  const [show, setShow] = useState(false);
  const [test, setTest] = useState<{ running: boolean; result?: any; error?: string }>({ running: false });
  const p = PROVIDERS[llm.provider];
  const runTest = async () => {
    setTest({ running: true });
    try {
      const status = await api("/api/status");
      const probe = await api("/api/learn/explain", { body: { concept: "sharpe", level: "beginner" } });
      setTest({ running: false, result: { ...status.llm, probe_source: probe.source, note: probe.note } });
    } catch (e: any) {
      setTest({ running: false, error: e.message });
    }
  };
  return (
    <div className="max-w-4xl">
      <PageHeader title="Settings" subtitle="Everything here is stored in this browser. There are no accounts." />
      <div className="grid gap-3 md:grid-cols-2">
        <Card title="AI narration" className="md:col-span-2">
          <div className="space-y-3">
            <Seg value={llm.mode} onChange={(mode) => setLlm({ ...llm, mode })} options={[{ value: "shared", label: "Shared free tier" }, { value: "own", label: "My own API key" }]} />
            {llm.mode === "shared" ? (
              <p className="muted text-[12.5px]">The site's shared Groq key narrates briefings, explanations and the analyst. It is rate limited per visitor; when the shared quota is busy you still get data-driven summaries. Add your own key for unlimited use.</p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-[180px_1fr]">
                <Field label="Provider">
                  <select className="select" value={llm.provider} onChange={(e) => setLlm({ ...llm, provider: e.target.value as LLMSettings["provider"], model: "" })}>
                    {Object.entries(PROVIDERS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                  </select>
                </Field>
                <Field label="API key" hint={p.hint}>
                  <div className="flex gap-1">
                    <input className="input mono" type={show ? "text" : "password"} autoComplete="off" spellCheck={false} value={llm.key} placeholder="Paste your key" onChange={(e) => setLlm({ ...llm, key: e.target.value.trim() })} />
                    <button type="button" className="btn" onClick={() => setShow((s) => !s)}>{show ? <EyeOff size={13} /> : <Eye size={13} />}</button>
                    <a className="btn" href={p.url} target="_blank" rel="noreferrer">Get a key</a>
                  </div>
                </Field>
                <Field label="Model (optional)" className="sm:col-start-2" hint={`Default: ${p.model}`}>
                  <input className="input mono" value={llm.model} placeholder={p.model} onChange={(e) => setLlm({ ...llm, model: e.target.value })} />
                </Field>
              </div>
            )}
            <div className="flex flex-wrap items-center gap-2">
              <button className="btn" onClick={runTest} disabled={test.running}>{test.running && <Spinner />}Test connection</button>
              {test.result && <span className="text-[12px]">Using <b>{test.result.provider_label ?? "no provider"}</b> {test.result.model ? `(${test.result.model})` : ""} with the {test.result.key_source ?? "--"} key. Probe: {test.result.probe_source === "ai" ? "AI answered" : `fell back to data${test.result.note ? `: ${test.result.note}` : ""}`}.</span>}
              {test.error && <span className="text-[12px]">{test.error}</span>}
            </div>
            <p className="faint text-[11px]">Your key is kept in this browser's local storage and sent over HTTPS only with your own requests, in a request header that the server uses for that request and never stores or logs.</p>
          </div>
        </Card>
        <Card title="Appearance">
          <Seg value={theme} onChange={setTheme} options={[{ value: "system", label: "System" }, { value: "light", label: "Light" }, { value: "dark", label: "Dark" }]} />
        </Card>
        <Card title="Your data">
          <div className="flex flex-wrap gap-2">
            <button className="btn" onClick={() => downloadFile("trading-engine-data.json", JSON.stringify(Object.fromEntries(Object.values(KEYS).filter((k) => k !== KEYS.llm).map((k) => [k, JSON.parse(localStorage.getItem(k) || "null")])), null, 1))}>Export all</button>
            <button className="btn" onClick={() => {
              if (!confirm("Clear watchlists, portfolio, journal, experiments, chats and alerts from this browser?")) return;
              Object.values(KEYS).filter((k) => k !== KEYS.theme).forEach((k) => localStorage.removeItem(k));
              localStorage.removeItem("te.lab.config");
              localStorage.removeItem("te.arena.config");
              location.reload();
            }}>Clear all</button>
          </div>
          <p className="faint mt-2 text-[11px]">Watchlists, portfolio, journal, Lab experiments, conversations and alerts live only in this browser.</p>
        </Card>
        <Card title="About" className="md:col-span-2">
          <div className="muted space-y-1 text-[12px]">
            <p>Trading Engine is a market-intelligence product built around neural networks implemented from scratch in NumPy, a pretrained LSTM, GRU, TCN and Transformer ensemble, and rule-based baselines.</p>
            <p><a className="underline" href="/api/docs" target="_blank" rel="noreferrer">API reference</a> · Market data by Yahoo Finance · Charts by TradingView Lightweight Charts</p>
          </div>
        </Card>
      </div>
    </div>
  );
}
