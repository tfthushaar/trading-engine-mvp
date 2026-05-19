"use client";
import { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";
import { Send, Cpu, User, ArrowRight } from "lucide-react";

interface Message { role: "user"|"assistant"; content: string; agent?: string; timestamp: string; }

const SUGGESTIONS = [
  "What is happening in the semiconductor sector today?",
  "Explain RSI and when it gives false signals",
  "How should I size positions for a $50k account?",
  "What does the current market regime mean for swing traders?",
];

export default function AIAnalystPage() {
  const [messages, setMessages] = useState<Message[]>([{
    role: "assistant",
    content: "I am your AI market analyst. Ask me about market trends, trade setups, risk management, or any trading concept you want to understand.",
    timestamp: new Date().toISOString(),
  }]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [convId, setConvId] = useState<string|null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  async function send(text: string) {
    if (!text.trim() || loading) return;
    setMessages(p => [...p, { role: "user", content: text, timestamp: new Date().toISOString() }]);
    setInput(""); setLoading(true);
    try {
      const r = await api.post("/api/agents/chat", { message: text, conversation_id: convId });
      if (r.data.conversation_id) setConvId(r.data.conversation_id);
      setMessages(p => [...p, { role: "assistant", content: r.data.response, agent: r.data.agent_used, timestamp: r.data.timestamp }]);
    } catch {
      setMessages(p => [...p, { role: "assistant", content: "Unable to process your request right now. Please try again.", timestamp: new Date().toISOString() }]);
    } finally { setLoading(false); }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 h-[calc(100vh-56px)] flex flex-col fade-in">
      <div className="mb-6">
        <h1 className="section-title">AI Analyst</h1>
        <p className="section-subtitle">Natural language market research — ask anything</p>
      </div>

      {messages.length === 1 && (
        <div className="grid grid-cols-2 gap-2 mb-6">
          {SUGGESTIONS.map(q => (
            <button key={q} onClick={() => send(q)} className="card-sm text-left text-xs text-[#999] hover:text-white hover:border-[#444] transition-all">
              <div className="flex items-start justify-between gap-2">
                <span className="leading-relaxed">{q}</span>
                <ArrowRight size={12} className="shrink-0 mt-0.5 text-[#555]" />
              </div>
            </button>
          ))}
        </div>
      )}

      <div className="flex-1 overflow-y-auto space-y-4 mb-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex gap-3 ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            {m.role === "assistant" && (
              <div className="w-7 h-7 bg-white rounded-lg flex items-center justify-center shrink-0 mt-0.5">
                <Cpu size={13} className="text-black" />
              </div>
            )}
            <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
              m.role === "user" ? "bg-white text-black rounded-tr-sm" : "bg-[#111] border border-[#2a2a2a] text-[#ddd] rounded-tl-sm"
            }`}>
              {m.role === "assistant" && m.agent && (
                <div className="text-[10px] text-[#555] mb-1.5 font-medium uppercase tracking-wider">{m.agent.replace(/_/g," ")}</div>
              )}
              {m.content}
            </div>
            {m.role === "user" && (
              <div className="w-7 h-7 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg flex items-center justify-center shrink-0 mt-0.5">
                <User size={13} />
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-7 h-7 bg-white rounded-lg flex items-center justify-center shrink-0">
              <Cpu size={13} className="text-black" />
            </div>
            <div className="card-sm flex items-center gap-1">
              {[0,150,300].map(d => <span key={d} className="w-1.5 h-1.5 bg-[#555] rounded-full animate-bounce" style={{animationDelay:`${d}ms`}} />)}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form className="flex gap-2" onSubmit={e => { e.preventDefault(); send(input); }}>
        <input
          value={input} onChange={e => setInput(e.target.value)}
          placeholder="Ask about markets, trades, or concepts..."
          className="input flex-1"
        />
        <button type="submit" disabled={loading || !input.trim()} className="btn-primary px-4 disabled:opacity-40">
          <Send size={15} />
        </button>
      </form>
      <p className="text-[10px] text-[#444] text-center mt-2">Educational purposes only — not financial advice</p>
    </div>
  );
}
