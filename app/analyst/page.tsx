"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowUp, MessageSquarePlus, Trash2 } from "lucide-react";
import { Disclaimer, Markdown, PageHeader, SourceTag, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { getStored, KEYS, useStored } from "@/lib/store";

interface Msg { role: "user" | "assistant"; content: string; agent?: string; symbols?: string[]; source?: string; note?: string | null; at: number }
interface Chat { id: string; title: string; messages: Msg[]; updated: number }

const SUGGESTIONS = [
  { agent: "Model", q: "What does the neural ensemble think about NVDA right now, and how reliable is that?" },
  { agent: "Market", q: "What is driving the market today and which sectors are leading?" },
  { agent: "News", q: "What is the latest news on TSLA and does it matter?" },
  { agent: "Trade review", q: "Review my AAPL trade: entry 340 stop 325 target 375" },
  { agent: "Strategy", q: "Which rule strategy has worked best on MSFT over the last two years?" },
  { agent: "Risk", q: "How should I size a position in AMD with a $25,000 account?" },
  { agent: "Portfolio", q: "Is my portfolio diversified enough?" },
  { agent: "Education", q: "Explain how an LSTM differs from a Transformer for time series." },
];

export default function AnalystPage() {
  const [chats, setChats] = useStored<Chat[]>(KEYS.chats, []);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const active = chats.find((c) => c.id === activeId) ?? null;
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [active?.messages.length, busy]);

  const send = async (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    const id = active?.id ?? Math.random().toString(36).slice(2, 10);
    const history = active?.messages ?? [];
    const userMsg: Msg = { role: "user", content: q, at: Date.now() };
    const upsert = (msgs: Msg[]) =>
      setChats((prev) => {
        const others = prev.filter((c) => c.id !== id);
        return [{ id, title: (prev.find((c) => c.id === id)?.title ?? q.slice(0, 60)), messages: msgs, updated: Date.now() }, ...others].slice(0, 40);
      });
    upsert([...history, userMsg]);
    setActiveId(id);
    setBusy(true);
    try {
      const r = await api("/api/analyst/chat", { body: { message: q, history: history.map((m) => ({ role: m.role, content: m.content })), portfolio: getStored(KEYS.portfolio, []) } });
      upsert([...history, userMsg, { role: "assistant", content: r.answer, agent: r.agent, symbols: r.symbols, source: r.source, note: r.note, at: Date.now() }]);
    } catch (e: any) {
      upsert([...history, userMsg, { role: "assistant", content: `Request failed: ${e.message}`, at: Date.now() }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader title="Analyst" subtitle="Ask in plain language. A router picks one of nine specialists, which gathers live data and model output before answering." right={active && <button className="btn lg:hidden" onClick={() => setActiveId(null)}><MessageSquarePlus size={13} />New chat</button>} />
      <div className="grid h-[calc(100vh-170px)] min-h-[480px] grid-cols-1 gap-3 lg:grid-cols-[240px_1fr]">
        <aside className="card hidden min-h-0 flex-col lg:flex">
          <div className="card-head"><span className="card-title">Conversations</span><button className="btn btn-sm btn-ghost" onClick={() => setActiveId(null)} title="New chat"><MessageSquarePlus size={13} /></button></div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {chats.length === 0 && <p className="faint px-3 py-3 text-[12px]">Your conversations are saved in this browser.</p>}
            {chats.map((c) => (
              <div key={c.id} className={`group flex items-center gap-1 border-b border-line px-3 py-1.5 ${c.id === activeId ? "bg-bg-2" : "hover:bg-bg-2"}`}>
                <button className="min-w-0 flex-1 truncate text-left text-[12px]" onClick={() => setActiveId(c.id)}>{c.title}</button>
                <button className="opacity-0 group-hover:opacity-100" onClick={() => { setChats(chats.filter((x) => x.id !== c.id)); if (activeId === c.id) setActiveId(null); }}><Trash2 size={11} /></button>
              </div>
            ))}
          </div>
        </aside>
        <section className="card flex min-h-0 flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3 sm:px-5">
            {!active?.messages.length ? (
              <div className="mx-auto max-w-3xl">
                <p className="muted mb-3 text-[12.5px]">Specialists: market, news, symbol, neural model, strategy, trade review, risk, portfolio and education. Answers cite the data they used.</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {SUGGESTIONS.map((s) => (
                    <button key={s.q} onClick={() => send(s.q)} className="rounded-lg border border-line px-3 py-2 text-left hover:border-line-2 hover:bg-bg-2">
                      <div className="eyebrow">{s.agent}</div>
                      <div className="text-[12.5px]">{s.q}</div>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="mx-auto max-w-3xl space-y-4">
                {active.messages.map((m, i) =>
                  m.role === "user" ? (
                    <div key={i} className="flex justify-end"><div className="max-w-[85%] rounded-2xl rounded-br-md bg-inv px-3 py-2 text-[13px] text-inv-fg">{m.content}</div></div>
                  ) : (
                    <div key={i} className="max-w-full">
                      <div className="mb-1 flex flex-wrap items-center gap-2 text-[11px]">
                        <span className="pill pill-soft">{(m.agent ?? "analyst").replace("_", " ")}</span>
                        {m.symbols?.map((s) => <Link key={s} href={`/symbol/${s}`} className="chip">{s}</Link>)}
                        <SourceTag source={m.source} note={m.note} />
                      </div>
                      <Markdown text={m.content} />
                    </div>
                  ),
                )}
                {busy && <div className="faint flex items-center gap-2 text-[12px]"><Spinner size={12} />Gathering data and writing an answer</div>}
                <div ref={end} />
              </div>
            )}
          </div>
          <form className="border-t border-line p-2" onSubmit={(e) => (e.preventDefault(), send(input))}>
            <div className="mx-auto flex max-w-3xl items-end gap-2">
              <textarea
                className="input min-h-[36px] flex-1 resize-none py-2"
                rows={1}
                placeholder="Ask about a symbol, the market, the neural model, a trade plan or a concept"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
              />
              <button className="btn btn-primary h-9 w-9 p-0" disabled={busy || !input.trim()} title="Send"><ArrowUp size={15} /></button>
            </div>
          </form>
        </section>
      </div>
      <Disclaimer />
    </div>
  );
}
